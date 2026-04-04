#!/usr/bin/env python3
"""
Smoke test for the DII podcast audio pipeline.
Uses a 3-line sample script to verify the full pipeline works
(parse → TTS → stitch → ffmpeg post-process) before running full episodes.
"""

import os
import sys
import tempfile

SAMPLE_SCRIPT = """\
**MAYA:** Welcome to Digital Infrastructure Insider. I'm Maya Chen.
**JAMES:** And I'm James Okafor. Let's get into today's top story.
**MAYA:** The cloud cost optimisation market has reached a new milestone this quarter.
"""

OUTPUT_FILE = "test_output.mp3"


def run_test() -> None:
    # Write sample script to a temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, prefix="dii_test_"
    ) as f:
        f.write(SAMPLE_SCRIPT)
        sample_path = f.name

    try:
        print("=" * 60)
        print("DII Pipeline Smoke Test")
        print("=" * 60)

        # ── Step 1: parse ─────────────────────────────────────────
        print("\n[1/4] Parsing sample script...")
        from generate_audio import parse_script
        pairs = parse_script(sample_path)
        assert len(pairs) == 3, f"Expected 3 lines, got {len(pairs)}"
        assert pairs[0] == ("MAYA", "Welcome to Digital Infrastructure Insider. I'm Maya Chen.")
        assert pairs[1] == ("JAMES", "And I'm James Okafor. Let's get into today's top story.")
        assert pairs[2][0] == "MAYA"
        print(f"  OK — {len(pairs)} lines parsed correctly")

        # ── Step 2: TTS ───────────────────────────────────────────
        print("\n[2/4] Initialising Kokoro TTS...")
        try:
            from kokoro_onnx import Kokoro
        except ImportError:
            sys.exit("FAIL: kokoro-onnx not installed. Run: pip install kokoro-onnx")

        kokoro = Kokoro("kokoro-v1.0.int8.onnx", "voices-v1.0.bin")
        print("  OK — Kokoro loaded")

        # ── Step 3: stitch ────────────────────────────────────────
        print("\n[3/4] Generating and stitching segments...")
        from generate_audio import generate_segments, stitch_segments
        import soundfile as sf

        with tempfile.TemporaryDirectory(prefix="dii_test_tts_") as tmp_dir:
            segment_info = generate_segments(pairs, kokoro, tmp_dir)
            combined = stitch_segments(segment_info)
            combined_wav = os.path.join(tmp_dir, "combined.wav")
            sf.write(combined_wav, combined, 24000)

            duration = len(combined) / 24000
            assert duration > 3.0, f"Expected >3s audio, got {duration:.2f}s"
            print(f"  OK — combined audio: {duration:.1f}s")

            # ── Step 4: ffmpeg post-process ───────────────────────
            print("\n[4/4] Post-processing with ffmpeg...")
            from generate_audio import post_process
            post_process(combined_wav, OUTPUT_FILE, episode=0, ep_date="2025-01-01")

        assert os.path.isfile(OUTPUT_FILE), "MP3 file was not created"
        size_kb = os.path.getsize(OUTPUT_FILE) / 1024
        assert size_kb > 10, f"MP3 suspiciously small: {size_kb:.1f} KB"
        print(f"  OK — {OUTPUT_FILE} written ({size_kb:.1f} KB)")

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print(f"Listen to the sample: {os.path.abspath(OUTPUT_FILE)}")
        print("=" * 60)

    finally:
        os.unlink(sample_path)


if __name__ == "__main__":
    run_test()
