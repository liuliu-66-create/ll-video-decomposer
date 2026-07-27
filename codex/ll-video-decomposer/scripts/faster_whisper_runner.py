#!/usr/bin/env python3
"""Run faster-whisper in a selected Python environment."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _add_bundled_cuda_dlls() -> None:
    if os.name != "nt":
        return
    candidates = [
        Path(sys.prefix) / "Lib" / "site-packages" / "torch" / "lib",
        Path(sys.prefix) / "Lib" / "site-packages" / "nvidia" / "cublas" / "bin",
        Path(sys.prefix) / "Lib" / "site-packages" / "nvidia" / "cudnn" / "bin",
        Path(sys.prefix) / "Lib" / "site-packages" / "nvidia" / "cuda_runtime" / "bin",
    ]
    existing = [path for path in candidates if path.is_dir()]
    if not existing:
        return
    os.environ["PATH"] = os.pathsep.join([*(str(path) for path in existing), os.environ.get("PATH", "")])
    for path in existing:
        try:
            os.add_dll_directory(str(path))
        except (AttributeError, OSError):
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe with faster-whisper.")
    parser.add_argument("audio")
    parser.add_argument("output")
    parser.add_argument("--segments-output")
    parser.add_argument("--model", default="small")
    parser.add_argument("--language")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--beam-size", type=int, default=1)
    parser.add_argument("--cpu-threads", type=int, default=0)
    parser.add_argument("--no-vad", action="store_true")
    args = parser.parse_args()

    audio = Path(args.audio).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not audio.is_file():
        raise SystemExit(f"Audio file does not exist: {audio}")
    output.parent.mkdir(parents=True, exist_ok=True)
    segments_output = Path(args.segments_output).expanduser().resolve() if args.segments_output else output.with_suffix(".segments.json")
    segments_output.parent.mkdir(parents=True, exist_ok=True)

    _add_bundled_cuda_dlls()
    from faster_whisper import WhisperModel

    started = time.perf_counter()
    model = WhisperModel(
        args.model,
        device=args.device,
        compute_type=args.compute_type,
        cpu_threads=args.cpu_threads,
        num_workers=1,
    )
    segments, info = model.transcribe(
        str(audio),
        language=args.language,
        beam_size=args.beam_size,
        vad_filter=not args.no_vad,
        condition_on_previous_text=True,
    )
    collected: list[dict] = []
    text_parts: list[str] = []
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        text_parts.append(text)
        collected.append({"start": round(segment.start, 3), "end": round(segment.end, 3), "text": text})

    output.write_text("\n".join(text_parts).strip() + "\n", encoding="utf-8")
    elapsed = time.perf_counter() - started
    metadata = {
        "engine": "faster-whisper",
        "model": args.model,
        "device": args.device,
        "compute_type": args.compute_type,
        "language": getattr(info, "language", args.language),
        "language_probability": getattr(info, "language_probability", None),
        "duration_seconds": getattr(info, "duration", None),
        "elapsed_seconds": round(elapsed, 3),
        "segments": collected,
    }
    segments_output.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in metadata.items() if key != "segments"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
