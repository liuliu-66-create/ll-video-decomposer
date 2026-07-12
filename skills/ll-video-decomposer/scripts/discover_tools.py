#!/usr/bin/env python3
"""Discover video tools and cache their paths in the current project."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tool_paths import discover, write_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover ffmpeg, Whisper and yt-dlp.")
    parser.add_argument("--project", default=".", help="Project directory")
    parser.add_argument("--no-write", action="store_true", help="Do not save the discovered paths")
    args = parser.parse_args()
    data = discover(Path(args.project))
    if not args.no_write:
        write_config(data)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
