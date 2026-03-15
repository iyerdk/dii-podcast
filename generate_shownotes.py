#!/usr/bin/env python3
"""
DII Podcast — Show Notes Generator (Stage 3)

Reads a two-speaker Markdown script and produces a JSON sidecar file
containing all the metadata needed for publishing:
  - Episode title & description (plain text and HTML)
  - Short summary (2–3 sentences, for podcast apps)
  - Bullet-point show notes (5–8 key takeaways)
  - Chapter markers (timestamp stubs — populated after audio is generated)
  - Keywords / tags

Usage:
    python generate_shownotes.py --script scripts/ep1_2026-03-15.md --episode 1
    python generate_shownotes.py --script scripts/ep2_2026-03-22.md --episode 2 --date 2026-03-22
"""

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import anthropic

SYSTEM_PROMPT = """You are a podcast producer for "Digital Infrastructure Insider",
an executive briefing for global digital infrastructure leaders and investors.

Given a two-speaker podcast script, you produce structured metadata for publishing.
You return ONLY valid JSON — no markdown fences, no explanation, just the JSON object."""

SHOWNOTES_PROMPT = """Analyse this podcast script and return a JSON object with EXACTLY
these fields (no extras):

{{
  "title": "string — episode title, max 80 chars, punchy and specific",
  "subtitle": "string — one-sentence episode hook, max 120 chars",
  "summary": "string — 2–3 sentence plain-text summary for podcast apps",
  "description_html": "string — 3–4 paragraph HTML description for the show page. Use <p>, <strong>, <ul>/<li> tags only.",
  "takeaways": ["array of 5–8 bullet strings, each max 120 chars, no bullet symbols"],
  "chapters": [
    {{"title": "string", "description": "string — one sentence"}}
  ],
  "keywords": ["array of 8–12 lowercase keyword strings"],
  "guests": [],
  "episode_type": "full"
}}

For chapters: infer them from the segment headings in the script. Do NOT include timestamps
(those will be added after audio generation). One chapter per major segment.

Script:
---
{script}
---"""


def load_script(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def strip_stage_directions(text: str) -> str:
    """Remove [BRACKET] stage directions to reduce token count."""
    return re.sub(r"\[(?!PAUSE)[^\]]{0,80}\]", "", text)


def call_claude(script_text: str) -> dict:
    client = anthropic.Anthropic()

    # Trim stage directions to save tokens
    trimmed = strip_stage_directions(script_text)

    prompt = SHOWNOTES_PROMPT.format(script=trimmed)

    print("  Calling Claude for show notes…")
    parts = []

    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for event in stream:
            if (
                event.type == "content_block_delta"
                and event.delta.type == "text_delta"
            ):
                parts.append(event.delta.text)

    raw = "".join(parts).strip()

    # Strip accidental markdown fences if model added them
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"WARNING: could not parse Claude response as JSON: {e}", file=sys.stderr)
        print("Raw response:", raw[:500], file=sys.stderr)
        return {"_raw": raw}


def enrich_metadata(data: dict, episode: int, ep_date: str, script_path: str) -> dict:
    """Add fields Claude doesn't know (episode number, date, file references)."""
    data["episode_number"] = episode
    data["date"] = ep_date
    data["script_file"] = os.path.basename(script_path)
    data["audio_file"] = f"DII_EP{episode}_{ep_date}.mp3"
    data["show_name"] = "Digital Infrastructure Insider"
    data["show_url"] = "https://dii.podcast"  # placeholder — update in config
    data["author"] = "Digital Infrastructure Insider"
    # Chapter timestamps are stubs — fill in after audio duration is known
    for i, ch in enumerate(data.get("chapters", [])):
        ch.setdefault("start_seconds", None)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate show notes and metadata for a DII podcast episode."
    )
    parser.add_argument("--script", required=True, help="Path to the two-speaker Markdown script")
    parser.add_argument("--episode", required=True, type=int, help="Episode number")
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Episode date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--output-dir",
        default="shownotes",
        help="Directory to write the JSON sidecar (default: ./shownotes)",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.script):
        sys.exit(f"Error: script file not found: {args.script}")

    output_filename = f"ep{args.episode}_{args.date}.json"
    os.makedirs(args.output_dir, exist_ok=True)
    output_path = os.path.join(args.output_dir, output_filename)

    print(f"Loading script: {args.script}")
    script_text = load_script(args.script)
    word_count = len(script_text.split())
    print(f"  {word_count} words")

    print("Generating show notes via Claude…")
    data = call_claude(script_text)

    print("Enriching metadata…")
    data = enrich_metadata(data, args.episode, args.date, args.script)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nDone! Show notes saved to: {output_path}")

    # Print a quick summary
    if "title" in data:
        print(f"\n  Title:    {data['title']}")
        print(f"  Summary:  {data.get('summary', '')[:100]}…")
        print(f"  Chapters: {len(data.get('chapters', []))}")
        print(f"  Keywords: {', '.join(data.get('keywords', [])[:6])}")


if __name__ == "__main__":
    main()
