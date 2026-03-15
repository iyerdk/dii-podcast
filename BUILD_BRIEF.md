# Build Brief: Digital Infrastructure Insider — Podcast Audio Pipeline
# Stage 1: Script → Dual-Voice MP3

## What we are building
A Python script that takes a two-speaker podcast script in Markdown format
and produces a finished, broadcast-ready MP3 using open-source tools only.

## Input format
Markdown files structured exactly like this:

    **MAYA:** Welcome to Digital Infrastructure Insider...
    **JAMES:** And I'm James Okafor...
    **MAYA:** Let's start with number one...

Speaker labels are always **MAYA:** or **JAMES:** in bold markdown.
Stage directions in [BRACKETS] should be skipped entirely.
Lines starting with # are headers — skip them.

## Output
A single normalised MP3 file named:
    DII_EP{episode_number}_{YYYY-MM-DD}.mp3

## Tools to use
- kokoro-onnx (pip install kokoro-onnx) — TTS engine, runs on CPU
- soundfile and numpy — audio array handling
- ffmpeg (system install) — normalisation, encoding, silence padding
- pydub — optional helper for audio segment stitching

## Voice assignments
- MAYA → Kokoro voice: "af_sarah" (clear, professional female)
- JAMES → Kokoro voice: "am_michael" (measured, analytical male)

## Processing steps to implement

1. PARSE the Markdown script file:
   - Extract speaker + text pairs as a list of tuples
   - e.g. [("MAYA", "Welcome to..."), ("JAMES", "And I'm James...")]
   - Skip headers, stage directions, production notes

2. GENERATE audio for each line:
   - Call Kokoro TTS for each (speaker, text) tuple
   - Use the correct voice per speaker
   - Save each line as a temporary WAV segment

3. STITCH segments:
   - Add 0.4 seconds silence between different speakers
   - Add 0.15 seconds silence between same-speaker consecutive lines
   - Concatenate all segments into one WAV file

4. POST-PROCESS with ffmpeg:
   - Normalise loudness to -16 LUFS (podcast standard)
   - Encode to MP3 at 128kbps
   - Add ID3 tags: title, episode number, date

5. CLEAN UP all temporary WAV files

## CLI interface
The script should be callable as:
    python generate_audio.py --script ep1_weekly_brief.md --episode 1
    python generate_audio.py --script ep2_deep_dive.md --episode 2

## Also create
- requirements.txt with all pip dependencies
- A README.md with setup instructions (including ffmpeg install for
  Mac, Linux, and Windows)
- A test with a short 3-line sample script to verify the pipeline works
  before processing full episodes

## Constraints
- Must run on CPU only — no GPU required
- No paid APIs — fully local and free
- Python 3.10+ compatible
- Should handle scripts up to 5,000 words without memory issues