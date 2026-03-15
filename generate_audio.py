#!/usr/bin/env python3
"""
Digital Infrastructure Insider — Podcast Audio Pipeline
Converts a two-speaker Markdown script to a broadcast-ready MP3.
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

import numpy as np
import soundfile as sf

VOICES = {
    "MAYA": "af_sarah",
    "JAMES": "am_michael",
}

SILENCE_BETWEEN_SPEAKERS = 0.4   # seconds
SILENCE_SAME_SPEAKER = 0.15      # seconds
SAMPLE_RATE = 24000               # kokoro default
MODEL_FILE = "kokoro-v1.0.int8.onnx"
VOICES_FILE = "voices-v1.0.bin"


def parse_script(path: str) -> list[tuple[str, str]]:
    """Extract (speaker, text) pairs from a Markdown podcast script."""
    pattern = re.compile(r"^\*\*([A-Z]+):\*\*\s*(.+)")
    lines = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            # Skip headers
            if line.startswith("#"):
                continue
            # Skip stage directions (lines that are only [BRACKET] content)
            if re.fullmatch(r"\[.*\]", line):
                continue
            m = pattern.match(line)
            if m:
                speaker = m.group(1).upper()
                text = m.group(2).strip()
                # Strip inline stage directions like [pause]
                text = re.sub(r"\[.*?\]", "", text).strip()
                if speaker in VOICES and text:
                    lines.append((speaker, text))
    return lines


def make_silence(seconds: float, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    return np.zeros(int(seconds * sample_rate), dtype=np.float32)


def generate_segments(
    pairs: list[tuple[str, str]],
    kokoro,
    tmp_dir: str,
) -> list[str]:
    """Generate a WAV file per line and return list of paths."""
    paths = []
    for idx, (speaker, text) in enumerate(pairs):
        voice = VOICES[speaker]
        print(f"  [{idx+1}/{len(pairs)}] {speaker}: {text[:60]}{'...' if len(text) > 60 else ''}")

        # kokoro returns (samples, sample_rate) — samples is a numpy array
        samples, sr = kokoro.create(text, voice=voice, speed=1.0)
        samples = samples.astype(np.float32)

        wav_path = os.path.join(tmp_dir, f"seg_{idx:04d}.wav")
        sf.write(wav_path, samples, sr)
        paths.append((speaker, wav_path))

    return paths


def stitch_segments(segment_info: list[tuple[str, str]]) -> np.ndarray:
    """Concatenate segments with silence padding between them."""
    chunks = []
    prev_speaker = None

    for speaker, path in segment_info:
        audio, _ = sf.read(path, dtype="float32")

        if prev_speaker is not None:
            gap = (
                SILENCE_BETWEEN_SPEAKERS
                if speaker != prev_speaker
                else SILENCE_SAME_SPEAKER
            )
            chunks.append(make_silence(gap))

        chunks.append(audio)
        prev_speaker = speaker

    return np.concatenate(chunks)


def post_process(
    wav_path: str,
    output_path: str,
    episode: int,
    ep_date: str,
) -> None:
    """Normalise loudness and encode to MP3 via ffmpeg."""
    title = f"Digital Infrastructure Insider — Episode {episode}"
    cmd = [
        "ffmpeg", "-y",
        "-i", wav_path,
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-codec:a", "libmp3lame",
        "-b:a", "128k",
        "-metadata", f"title={title}",
        "-metadata", f"track={episode}",
        "-metadata", f"date={ep_date}",
        "-metadata", "artist=Digital Infrastructure Insider",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("ffmpeg stderr:", result.stderr, file=sys.stderr)
        raise RuntimeError("ffmpeg failed")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a podcast MP3 from a two-speaker Markdown script."
    )
    parser.add_argument("--script", required=True, help="Path to the Markdown script file")
    parser.add_argument("--episode", required=True, type=int, help="Episode number")
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Episode date (YYYY-MM-DD), defaults to today",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for the output MP3 (default: current directory)",
    )
    args = parser.parse_args()

    script_path = args.script
    if not os.path.isfile(script_path):
        sys.exit(f"Error: script file not found: {script_path}")

    # Lazy-import kokoro so missing-dependency errors are clear
    try:
        from kokoro_onnx import Kokoro
    except ImportError:
        sys.exit("Error: kokoro-onnx is not installed. Run: pip install kokoro-onnx")

    output_filename = f"DII_EP{args.episode}_{args.date}.mp3"
    output_path = os.path.join(args.output_dir, output_filename)

    print(f"Parsing script: {script_path}")
    pairs = parse_script(script_path)
    if not pairs:
        sys.exit("Error: no speaker lines found in script.")
    print(f"Found {len(pairs)} lines ({sum(1 for s,_ in pairs if s=='MAYA')} MAYA, "
          f"{sum(1 for s,_ in pairs if s=='JAMES')} JAMES)")

    print("Initialising Kokoro TTS...")
    kokoro = Kokoro(MODEL_FILE, VOICES_FILE)

    with tempfile.TemporaryDirectory(prefix="dii_tts_") as tmp_dir:
        print(f"Generating audio segments (tmp: {tmp_dir})...")
        segment_info = generate_segments(pairs, kokoro, tmp_dir)

        print("Stitching segments...")
        combined = stitch_segments(segment_info)

        combined_wav = os.path.join(tmp_dir, "combined.wav")
        sf.write(combined_wav, combined, SAMPLE_RATE)
        duration = len(combined) / SAMPLE_RATE
        print(f"Combined audio: {duration:.1f}s ({duration/60:.1f} min)")

        print("Post-processing with ffmpeg (loudnorm + MP3 encode)...")
        os.makedirs(args.output_dir, exist_ok=True)
        post_process(combined_wav, output_path, args.episode, args.date)

    print(f"\nDone! Output: {output_path}")


if __name__ == "__main__":
    main()
