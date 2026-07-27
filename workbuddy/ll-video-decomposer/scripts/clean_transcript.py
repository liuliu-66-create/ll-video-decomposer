#!/usr/bin/env python3
"""Remove common timestamp formats from transcripts."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


TIMESTAMP_PATTERNS = [
    re.compile(r"^\s*\[\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?\s*(?:-->|-)\s*\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?\]\s*"),
    re.compile(r"^\s*\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?\s*(?:-->|-)\s*\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?\s*"),
    re.compile(r"^\s*\[\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?\]\s*"),
    re.compile(r"^\s*\(\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?\)\s*"),
]


def clean_text(text: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        for pattern in TIMESTAMP_PATTERNS:
            line = pattern.sub("", line).strip()
        if line:
            cleaned_lines.append(line)
        elif cleaned_lines and cleaned_lines[-1] != "":
            cleaned_lines.append("")

    compact: list[str] = []
    previous_blank = False
    for line in cleaned_lines:
        is_blank = line == ""
        if is_blank and previous_blank:
            continue
        compact.append(line)
        previous_blank = is_blank

    return "\n".join(compact).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean transcript timestamps.")
    parser.add_argument("input", help="Input transcript path")
    parser.add_argument("output", nargs="?", help="Output transcript path; defaults to stdout")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise SystemExit(f"Input file does not exist: {input_path}")

    text = input_path.read_text(encoding="utf-8-sig")
    cleaned = clean_text(text)

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(cleaned, encoding="utf-8")
        print(output_path)
    else:
        print(cleaned, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
