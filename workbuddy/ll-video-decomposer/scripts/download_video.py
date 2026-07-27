#!/usr/bin/env python3
"""Download one video using discovered yt-dlp, optionally with Chrome cookies."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from tool_paths import resolve_tool


def main() -> int:
    parser = argparse.ArgumentParser(description="Download one video for decomposition.")
    parser.add_argument("url")
    parser.add_argument("output_dir")
    parser.add_argument("--chrome-cookies", action="store_true", help="Completely close Chrome first.")
    args = parser.parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    yt_dlp = resolve_tool("yt_dlp", output_dir)
    if not yt_dlp:
        raise SystemExit("yt-dlp was not found after PATH, config, Python Scripts and limited-directory checks.")
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [yt_dlp, "--no-playlist", "--restrict-filenames", "--merge-output-format", "mp4", "--output", str(output_dir / "%(title).120s-%(id)s.%(ext)s"), "--print", "after_move:filepath"]
    if args.chrome_cookies:
        cmd.extend(["--cookies-from-browser", "chrome"])
    cmd.append(args.url)
    completed = subprocess.run(cmd, check=True, text=True, capture_output=True)
    if completed.stdout.strip():
        print(completed.stdout.strip().splitlines()[-1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
