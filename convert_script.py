#!/usr/bin/env python3
"""
DII Podcast — HTML Script to Two-Speaker Markdown Converter

Reads a single-HOST HTML podcast script, sends it to Claude to rewrite it
as a natural MAYA / JAMES two-host dialogue, and saves the result as the
Markdown format consumed by generate_audio.py.

Usage:
    python convert_script.py --source source_mat/202603/DII_Podcast_Script_Mar15_2026.html --episode 1
    python convert_script.py --source source_mat/202604/DII_EP2.html --episode 2 --date 2026-04-05
"""

import argparse
import os
import re
import sys
from datetime import date
from html.parser import HTMLParser

import anthropic

# ── Persona notes fed to Claude ───────────────────────────────────────────────
SYSTEM_PROMPT = """You are a podcast script writer for "Digital Infrastructure Insider",
an executive briefing podcast on global digital infrastructure.

You will be given the full text of a single-host podcast script (labelled HOST).
Your job is to rewrite it as a natural, engaging two-host conversation between:

  MAYA CHEN  — Lead anchor. Sets the agenda, introduces segments, handles
               transitions, delivers key facts and headlines. Clear, authoritative.

  JAMES OKAFOR — Analytical co-host. Adds depth, context, and investor perspective.
                 Asks the question the listener is thinking. Occasionally challenges
                 or reframes a point. Measured, thoughtful.

Rules:
1. Preserve ALL substantive content — every fact, figure, company name, and
   conclusion from the original must appear in the output. Do not add new facts.
2. Split the HOST text naturally between the two voices. MAYA should speak roughly
   55-60% of the total words; JAMES 40-45%.
3. Each speaker turn must start on its own line formatted EXACTLY as:
       **MAYA:** [spoken text]
       **JAMES:** [spoken text]
4. Stage directions like [PAUSE], [CUE: music], [NOTE: ...] should be preserved
   on their own lines inside square brackets, unchanged.
5. Segment headers from the original (e.g. "COLD OPEN", "SEGMENT 1 — Geopolitics")
   should be kept as Markdown H2 headers (## heading) so the script stays readable.
6. Do NOT introduce opinions, jokes, or information not present in the original.
7. Write conversational spoken prose — not bullet points or lists.
8. The dialogue must flow naturally: JAMES often responds directly to what MAYA
   just said before adding new information.
9. Output ONLY the Markdown script — no preamble, no explanation."""

CONVERSION_PROMPT_TEMPLATE = """Please convert the following single-host podcast script into a
two-host MAYA / JAMES dialogue following the instructions in your system prompt.

--- ORIGINAL SCRIPT ---
{script_text}
--- END ORIGINAL SCRIPT ---

Output the complete converted Markdown script now:"""


# ── HTML parsing ──────────────────────────────────────────────────────────────

class ScriptHTMLParser(HTMLParser):
    """Extract structured text from the DII podcast HTML script format."""

    def __init__(self):
        super().__init__()
        self.segments = []          # list of dicts: {label, title, content}
        self._current_segment = None
        self._current_text = []
        self._in_script = False     # inside a .script-text div
        self._in_direction = False  # inside a .direction-text div
        self._in_segment_label = False
        self._in_segment_title = False
        self._in_pullquote = False
        self._in_ep_header = False
        self._skip_depth = 0        # for tags we want to skip entirely
        self._tag_stack = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = attrs_dict.get("class", "").split()

        self._tag_stack.append(tag)

        if "segment" in classes and "segment-closing" not in classes:
            # New segment
            self._flush_segment()
            self._current_segment = {"label": "", "title": "", "blocks": []}

        elif "segment-closing" in classes:
            self._flush_segment()
            self._current_segment = {"label": "CLOSING", "title": "Sign-Off", "blocks": []}

        elif "segment-label" in classes:
            self._in_segment_label = True

        elif "segment-title" in classes:
            self._in_segment_title = True

        elif "script-text" in classes:
            self._in_script = True
            self._current_text = []

        elif "direction-text" in classes:
            self._in_direction = True
            self._current_text = []

        elif "pullquote" in classes:
            self._in_pullquote = True
            self._current_text = []

        elif "ep-header" in classes:
            self._in_ep_header = True

        elif "legend" in classes or "masthead" in classes or "footer" in classes:
            # Skip these decorative blocks
            self._skip_depth = len(self._tag_stack)

    def handle_endtag(self, tag):
        if self._tag_stack:
            self._tag_stack.pop()

        # Clear skip once we've closed the skipped element (pop first, then compare)
        if self._skip_depth and len(self._tag_stack) < self._skip_depth:
            self._skip_depth = 0

        # End of a script-text div (div close)
        if tag == "div":
            if self._in_script:
                text = _clean(" ".join(self._current_text))
                if text and self._current_segment is not None:
                    self._current_segment["blocks"].append(("HOST", text))
                self._in_script = False
                self._current_text = []

            elif self._in_direction:
                text = _clean(" ".join(self._current_text))
                if text and self._current_segment is not None:
                    self._current_segment["blocks"].append(("DIRECTION", text))
                self._in_direction = False
                self._current_text = []

            elif self._in_pullquote:
                text = _clean(" ".join(self._current_text))
                if text and self._current_segment is not None:
                    self._current_segment["blocks"].append(("PULLQUOTE", text))
                self._in_pullquote = False
                self._current_text = []

            elif self._in_segment_label:
                self._in_segment_label = False

            elif self._in_segment_title:
                self._in_segment_title = False

        elif tag in ("p",):
            if self._in_script or self._in_pullquote:
                self._current_text.append("\n")

    def handle_data(self, data):
        if self._skip_depth:
            return

        text = data.strip()
        if not text:
            return

        if self._in_segment_label and self._current_segment is not None:
            self._current_segment["label"] = text

        elif self._in_segment_title and self._current_segment is not None:
            self._current_segment["title"] = text

        elif self._in_script or self._in_direction or self._in_pullquote:
            self._current_text.append(text)

    def _flush_segment(self):
        if self._current_segment is not None and self._current_segment.get("blocks"):
            self.segments.append(self._current_segment)
        self._current_segment = None

    def get_segments(self):
        self._flush_segment()
        return self.segments


def _clean(text: str) -> str:
    """Normalise whitespace."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def parse_html_script(path: str) -> str:
    """Parse the HTML file and return a clean plain-text script."""
    with open(path, encoding="utf-8") as f:
        html = f.read()

    parser = ScriptHTMLParser()
    parser.feed(html)
    segments = parser.get_segments()

    lines = []
    for seg in segments:
        label = seg.get("label", "")
        title = seg.get("title", "")
        heading = f"{label} — {title}" if label and title else label or title
        if heading:
            lines.append(f"\n## {heading}\n")

        for kind, text in seg.get("blocks", []):
            if kind == "HOST":
                lines.append(f"[HOST] {text}\n")
            elif kind == "DIRECTION":
                lines.append(f"[{text}]\n")
            elif kind == "PULLQUOTE":
                lines.append(f'[PULLQUOTE: "{text}"]\n')

    return "\n".join(lines)


# ── Claude API call ───────────────────────────────────────────────────────────

def convert_with_claude(script_text: str) -> str:
    """Send the plain-text script to Claude and return the two-speaker Markdown."""
    client = anthropic.Anthropic()

    prompt = CONVERSION_PROMPT_TEMPLATE.format(script_text=script_text)

    print("  Calling Claude (streaming)…")
    output_parts = []

    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=8192,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for event in stream:
            if event.type == "content_block_delta":
                if event.delta.type == "text_delta":
                    output_parts.append(event.delta.text)
                    print(event.delta.text, end="", flush=True)

    print()  # newline after streaming output
    return "".join(output_parts)


# ── Post-processing ───────────────────────────────────────────────────────────

def validate_output(text: str) -> None:
    """Warn if the output looks malformed."""
    maya_count = text.count("**MAYA:**")
    james_count = text.count("**JAMES:**")
    if maya_count == 0 or james_count == 0:
        print(
            f"WARNING: output has {maya_count} MAYA lines and {james_count} JAMES lines — "
            "may not have converted correctly.",
            file=sys.stderr,
        )
    else:
        print(f"  Validation: {maya_count} MAYA lines, {james_count} JAMES lines")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a single-HOST HTML podcast script to two-speaker Markdown."
    )
    parser.add_argument("--source", required=True, help="Path to the HTML script file")
    parser.add_argument("--episode", required=True, type=int, help="Episode number")
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Episode date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--output-dir",
        default="scripts",
        help="Directory to write the Markdown script (default: ./scripts)",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.source):
        sys.exit(f"Error: source file not found: {args.source}")

    output_filename = f"ep{args.episode}_{args.date}.md"
    os.makedirs(args.output_dir, exist_ok=True)
    output_path = os.path.join(args.output_dir, output_filename)

    # ── Step 1: Parse HTML ────────────────────────────────────────────────────
    print(f"Parsing HTML script: {args.source}")
    script_text = parse_html_script(args.source)
    word_count = len(script_text.split())
    print(f"  Extracted ~{word_count} words across {script_text.count('## ')} segments")

    # ── Step 2: Convert via Claude ────────────────────────────────────────────
    print("Converting to two-speaker dialogue via Claude…")
    converted = convert_with_claude(script_text)

    # ── Step 3: Validate & save ───────────────────────────────────────────────
    print("Validating output…")
    validate_output(converted)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# Digital Infrastructure Insider — Episode {args.episode}\n")
        f.write(f"# {args.date}\n\n")
        f.write(converted)

    print(f"\nDone! Script saved to: {output_path}")
    print(f"Next step: python generate_audio.py --script {output_path} --episode {args.episode}")


if __name__ == "__main__":
    main()
