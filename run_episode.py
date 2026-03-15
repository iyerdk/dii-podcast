#!/usr/bin/env python3
"""
DII Podcast — Full Pipeline Orchestrator (Stage 5)

Runs all four stages in sequence for a single episode:

  Stage 2  convert_script.py   HTML source → two-speaker Markdown script
  Stage 1  generate_audio.py   Markdown script → normalised MP3
  Stage 3  generate_shownotes.py  Script → show notes JSON sidecar
  Stage 4  publish_rss.py      JSON + MP3 → RSS feed entry (+ optional upload)

Usage:
    # Minimal — just provide the source HTML and episode number
    python run_episode.py --source source_mat/202603/DII_Podcast_Script_Mar15_2026.html --episode 1

    # With upload to S3
    python run_episode.py \\
        --source source_mat/202603/DII_Podcast_Script_Mar15_2026.html \\
        --episode 1 \\
        --date 2026-03-15 \\
        --upload-to s3://my-podcast-bucket \\
        --base-url https://media.dii.podcast

    # Skip stages you've already run (re-run from audio onwards)
    python run_episode.py \\
        --source source_mat/202603/DII_Podcast_Script_Mar15_2026.html \\
        --episode 1 \\
        --skip-convert \\
        --skip-audio

Configuration via environment variables (or pass flags):
    ANTHROPIC_API_KEY   — required for Stages 2 and 3
    DII_BASE_URL        — base URL for MP3 hosting
    R2_ENDPOINT_URL     — required if uploading to Cloudflare R2
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import date
from pathlib import Path


# ── Helpers ───────────────────────────────────────────────────────────────────

def _header(text: str) -> None:
    bar = "─" * (len(text) + 4)
    print(f"\n┌{bar}┐")
    print(f"│  {text}  │")
    print(f"└{bar}┘")


def _run(cmd: list[str], label: str) -> None:
    """Run a subprocess, streaming its output. Exits on failure."""
    print(f"\n$ {' '.join(cmd)}\n")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        sys.exit(f"\nError: {label} failed (exit {result.returncode}). Stopping pipeline.")


def _check_file(path: str, label: str) -> None:
    if not os.path.isfile(path):
        sys.exit(f"Error: expected {label} at {path} but file not found.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the full DII podcast production pipeline for one episode."
    )
    parser.add_argument("--source", required=True, help="Path to the HTML source script")
    parser.add_argument("--episode", required=True, type=int, help="Episode number")
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Episode date YYYY-MM-DD (default: today)",
    )

    # Directories
    parser.add_argument("--scripts-dir", default="scripts", help="Where to write the Markdown script")
    parser.add_argument("--shownotes-dir", default="shownotes", help="Where to write the show notes JSON")
    parser.add_argument("--output-dir", default=".", help="Where to write the MP3")

    # Publishing
    parser.add_argument(
        "--base-url",
        default=os.environ.get("DII_BASE_URL", "https://media.dii.podcast"),
        help="Base URL where MP3 files are hosted (env: DII_BASE_URL)",
    )
    parser.add_argument(
        "--upload-to",
        default="local",
        help="Upload target: 'local' (default), 's3://bucket', or 'r2://bucket'",
    )
    parser.add_argument("--feed", default="feed.xml", help="Path to the RSS feed file")

    # Stage skip flags
    parser.add_argument("--skip-convert", action="store_true", help="Skip Stage 2 (HTML → Markdown)")
    parser.add_argument("--skip-audio", action="store_true", help="Skip Stage 1 (Markdown → MP3)")
    parser.add_argument("--skip-shownotes", action="store_true", help="Skip Stage 3 (show notes)")
    parser.add_argument("--skip-publish", action="store_true", help="Skip Stage 4 (RSS publish)")

    args = parser.parse_args()

    # Derived paths
    script_path = os.path.join(args.scripts_dir, f"ep{args.episode}_{args.date}.md")
    mp3_path = os.path.join(args.output_dir, f"DII_EP{args.episode}_{args.date}.mp3")
    shownotes_path = os.path.join(args.shownotes_dir, f"ep{args.episode}_{args.date}.json")

    py = sys.executable  # use same Python that's running this script

    t_start = time.time()

    print(f"\n{'='*60}")
    print(f"  DII Podcast Pipeline — Episode {args.episode} ({args.date})")
    print(f"{'='*60}")
    print(f"  Source:     {args.source}")
    print(f"  Script:     {script_path}")
    print(f"  MP3:        {mp3_path}")
    print(f"  Show notes: {shownotes_path}")
    print(f"  Feed:       {args.feed}")
    print(f"  Upload:     {args.upload_to}")

    # ── Stage 2: Convert HTML → Markdown ─────────────────────────────────────
    if not args.skip_convert:
        _header(f"Stage 2 — Convert HTML script (EP{args.episode})")
        _run([
            py, "convert_script.py",
            "--source", args.source,
            "--episode", str(args.episode),
            "--date", args.date,
            "--output-dir", args.scripts_dir,
        ], "Script conversion")
        _check_file(script_path, "converted Markdown script")
    else:
        print(f"\n[SKIP] Stage 2 — using existing script: {script_path}")
        _check_file(script_path, "converted Markdown script")

    # ── Stage 1: Generate Audio ───────────────────────────────────────────────
    if not args.skip_audio:
        _header(f"Stage 1 — Generate Audio (EP{args.episode})")
        _run([
            py, "generate_audio.py",
            "--script", script_path,
            "--episode", str(args.episode),
            "--date", args.date,
            "--output-dir", args.output_dir,
        ], "Audio generation")
        _check_file(mp3_path, "episode MP3")
    else:
        print(f"\n[SKIP] Stage 1 — using existing MP3: {mp3_path}")

    # ── Stage 3: Generate Show Notes ─────────────────────────────────────────
    if not args.skip_shownotes:
        _header(f"Stage 3 — Generate Show Notes (EP{args.episode})")
        _run([
            py, "generate_shownotes.py",
            "--script", script_path,
            "--episode", str(args.episode),
            "--date", args.date,
            "--output-dir", args.shownotes_dir,
        ], "Show notes generation")
        _check_file(shownotes_path, "show notes JSON")
    else:
        print(f"\n[SKIP] Stage 3 — using existing show notes: {shownotes_path}")
        _check_file(shownotes_path, "show notes JSON")

    # ── Stage 4: Publish RSS ──────────────────────────────────────────────────
    if not args.skip_publish:
        _header(f"Stage 4 — Publish RSS (EP{args.episode})")
        _run([
            py, "publish_rss.py",
            "--shownotes", shownotes_path,
            "--mp3", mp3_path,
            "--base-url", args.base_url,
            "--upload-to", args.upload_to,
            "--feed", args.feed,
        ], "RSS publishing")
    else:
        print(f"\n[SKIP] Stage 4 — RSS not updated")

    # ── Done ──────────────────────────────────────────────────────────────────
    elapsed = time.time() - t_start
    mins, secs = divmod(int(elapsed), 60)

    print(f"\n{'='*60}")
    print(f"  Pipeline complete in {mins}m {secs}s")
    print(f"{'='*60}")
    print(f"  MP3:        {os.path.abspath(mp3_path)}")
    print(f"  Show notes: {os.path.abspath(shownotes_path)}")
    print(f"  RSS feed:   {os.path.abspath(args.feed)}")
    if args.upload_to != "local":
        print(f"  Uploaded to: {args.upload_to}")


if __name__ == "__main__":
    main()
