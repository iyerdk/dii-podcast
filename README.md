# Digital Infrastructure Insider — Podcast Production Pipeline

End-to-end automation from raw HTML source material to a published MP3 with RSS feed.

```
source_mat/
  └── 202603/DII_Podcast_Script_Mar15_2026.html
        │
        ▼  Stage 2: convert_script.py  (Claude API)
  scripts/ep1_2026-03-15.md
        │
        ▼  Stage 1: generate_audio.py  (Kokoro TTS + ffmpeg)
  DII_EP1_2026-03-15.mp3
        │
        ▼  Stage 3: generate_shownotes.py  (Claude API)
  shownotes/ep1_2026-03-15.json
        │
        ▼  Stage 4: publish_rss.py
  feed.xml  (+optional S3/R2 upload)
```

**One command runs everything:**
```bash
python run_episode.py --source source_mat/202603/DII_Podcast_Script_Mar15_2026.html --episode 1
```

---

## Requirements

- Python 3.10+
- ffmpeg (system package)
- `ANTHROPIC_API_KEY` environment variable (for script conversion + show notes)
- pip dependencies in `requirements.txt`

---

## Setup

### 1 — Install ffmpeg

**macOS**
```bash
brew install ffmpeg
```

**Linux (Debian / Ubuntu)**
```bash
sudo apt update && sudo apt install -y ffmpeg
```

**Windows**
1. Download from https://www.gyan.dev/ffmpeg/builds/ (ffmpeg-release-essentials.zip)
2. Extract and add the `bin/` folder to your `PATH`
3. Verify: `ffmpeg -version`

---

### 2 — Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

### 3 — Anthropic API key

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Used by `convert_script.py` (Stage 2) and `generate_shownotes.py` (Stage 3).

---

### 4 — Download Kokoro TTS model files

```bash
python - <<'EOF'
from kokoro_onnx import Kokoro
Kokoro.from_pretrained()   # downloads kokoro-v0_19.onnx + voices.json (~300 MB, once)
EOF
```

---

### 5 — Smoke test

Before running a full episode, verify the audio pipeline works:

```bash
python test_pipeline.py
# Creates test_output.mp3 (~5 seconds)
```

---

## Running an episode

### Full pipeline (one command)

```bash
python run_episode.py \
  --source source_mat/202603/DII_Podcast_Script_Mar15_2026.html \
  --episode 1 \
  --date 2026-03-15
```

### With upload to S3 or Cloudflare R2

```bash
# S3
python run_episode.py \
  --source source_mat/202603/DII_Podcast_Script_Mar15_2026.html \
  --episode 1 \
  --date 2026-03-15 \
  --upload-to s3://my-podcast-bucket \
  --base-url https://media.dii.podcast

# Cloudflare R2 (set R2_ENDPOINT_URL env var first)
export R2_ENDPOINT_URL="https://ACCOUNT_ID.r2.cloudflarestorage.com"
python run_episode.py \
  --source source_mat/202603/DII_Podcast_Script_Mar15_2026.html \
  --episode 1 \
  --upload-to r2://my-r2-bucket \
  --base-url https://media.dii.podcast
```

### Skip stages (re-run from a specific point)

```bash
# Already have the Markdown script — skip conversion, re-run audio onwards
python run_episode.py --source ... --episode 1 --skip-convert

# Already have MP3 + script — just regenerate show notes and republish
python run_episode.py --source ... --episode 1 --skip-convert --skip-audio
```

---

## Running stages individually

### Stage 2 — Convert HTML script → two-speaker Markdown

```bash
python convert_script.py \
  --source source_mat/202603/DII_Podcast_Script_Mar15_2026.html \
  --episode 1 \
  --date 2026-03-15
# Output: scripts/ep1_2026-03-15.md
```

### Stage 1 — Generate audio

```bash
python generate_audio.py \
  --script scripts/ep1_2026-03-15.md \
  --episode 1 \
  --date 2026-03-15
# Output: DII_EP1_2026-03-15.mp3
```

### Stage 3 — Generate show notes

```bash
python generate_shownotes.py \
  --script scripts/ep1_2026-03-15.md \
  --episode 1 \
  --date 2026-03-15
# Output: shownotes/ep1_2026-03-15.json
```

### Stage 4 — Publish to RSS feed

```bash
python publish_rss.py \
  --shownotes shownotes/ep1_2026-03-15.json \
  --mp3 DII_EP1_2026-03-15.mp3 \
  --base-url https://media.dii.podcast
# Output: feed.xml (created or updated)
```

---

## Source material format

Place HTML scripts in `source_mat/YYYYMM/`:

```
source_mat/
  202603/
    DII_Podcast_Script_Mar15_2026.html
  202604/
    DII_Podcast_Script_Apr05_2026.html
```

The HTML must follow the DII script format (segments with `.script-text`, `.direction-text`,
`.segment-label`, `.segment-title` CSS classes). `convert_script.py` parses this structure
automatically.

---

## Output files

| File | Description |
|---|---|
| `scripts/ep{N}_{date}.md` | Two-speaker Markdown script |
| `DII_EP{N}_{date}.mp3` | Broadcast-ready MP3 (−16 LUFS, 128 kbps) |
| `shownotes/ep{N}_{date}.json` | Show notes, chapters, keywords, HTML description |
| `feed.xml` | Podcast RSS feed (append-only, newest episode first) |

---

## Voice reference

| Speaker | Kokoro voice | Character |
|---|---|---|
| MAYA | `af_sarah` | Lead anchor — clear, authoritative |
| JAMES | `am_michael` | Analytical co-host — measured, thoughtful |

---

## Audio spec

| Parameter | Value |
|---|---|
| Loudness | −16 LUFS (podcast standard) |
| True peak | −1.5 dBTP |
| Bitrate | 128 kbps MP3 |
| Speaker gap | 0.4 s |
| Same-speaker gap | 0.15 s |

---

## Troubleshooting

**`ModuleNotFoundError: kokoro_onnx`** — run `pip install kokoro-onnx` inside your venv.

**`FileNotFoundError: kokoro-v0_19.onnx`** — run the model download step above.

**`ffmpeg: command not found`** — install ffmpeg and ensure it is on your `PATH`.

**`AuthenticationError`** — check `ANTHROPIC_API_KEY` is set and valid.

**Memory issues on long scripts** — the pipeline processes one line at a time; RAM usage
is bounded regardless of script length.

**RSS feed already has episode** — `publish_rss.py` skips duplicate GUIDs by default.
Delete the `<item>` from `feed.xml` manually if you need to re-publish.
