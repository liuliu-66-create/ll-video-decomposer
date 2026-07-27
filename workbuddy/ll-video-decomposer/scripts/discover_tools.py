#!/usr/bin/env python3
"""Discover video tools and cache their paths in the current project."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tool_paths import discover, write_config


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover ffmpeg, Whisper and yt-dlp.")
    parser.add_argument("--project", default=".", help="Project directory")
    parser.add_argument("--no-write", action="store_true", help="Do not save the discovered paths")
    parser.add_argument("--refresh", action="store_true", help="Re-probe Python backends instead of using cache")
    args = parser.parse_args()
    data = discover(Path(args.project), refresh=args.refresh)
    if not args.no_write:
        write_config(data)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
