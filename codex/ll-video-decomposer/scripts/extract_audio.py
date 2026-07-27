#!/usr/bin/env python3
"""Extract 16 kHz mono WAV audio using discovered ffmpeg."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from tool_paths import resolve_tool


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract WAV audio for transcription.")
    parser.add_argument("input")
    parser.add_argument("output")
    args = parser.parse_args()
    source = Path(args.input).expanduser().resolve()
    target = Path(args.output).expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Input file does not exist: {source}")
    ffmpeg = resolve_tool("ffmpeg", source.parent)
    if not ffmpeg:
        raise SystemExit("ffmpeg was not found after PATH, config, common-path and limited-directory checks.")
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg, "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", str(target)], check=True)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
