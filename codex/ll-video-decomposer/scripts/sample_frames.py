#!/usr/bin/env python3
"""Build a timestamped visual evidence pack from one local video."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from pathlib import Path

from tool_paths import resolve_tool


PTS_PATTERN = re.compile(r"pts_time:([0-9.]+)")


def _fraction(value: str | None) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    try:
        if "/" in value:
            numerator, denominator = value.split("/", 1)
            denominator_value = float(denominator)
            return float(numerator) / denominator_value if denominator_value else None
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _probe(ffprobe: str, source: Path) -> dict:
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(source),
        ],
        check=True,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    payload = json.loads(completed.stdout)
    streams = payload.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if not video:
        raise SystemExit(f"No video stream found: {source}")
    duration_value = payload.get("format", {}).get("duration") or video.get("duration")
    try:
        duration = float(duration_value)
    except (TypeError, ValueError):
        raise SystemExit(f"Could not determine video duration: {source}") from None
    return {
        "duration_seconds": duration,
        "width": video.get("width"),
        "height": video.get("height"),
        "fps": _fraction(video.get("avg_frame_rate") or video.get("r_frame_rate")),
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name") if audio else None,
        "audio_sample_rate": int(audio["sample_rate"]) if audio and str(audio.get("sample_rate", "")).isdigit() else None,
        "audio_channels": audio.get("channels") if audio else None,
        "has_audio": bool(audio),
    }


def _auto_interval(duration: float) -> float:
    if duration <= 60:
        return 5.0
    if duration <= 180:
        return 10.0
    if duration <= 600:
        return 15.0
    return max(30.0, duration / 40.0)


def _sequence(start: float, stop: float, step: float) -> list[float]:
    values: list[float] = []
    current = max(0.0, start)
    while current <= stop + 0.001:
        values.append(current)
        current += step
    return values


def _scene_times(ffmpeg: str, source: Path, threshold: float) -> tuple[list[float], str | None]:
    completed = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-i",
            str(source),
            "-vf",
            f"select='gt(scene,{threshold})',showinfo",
            "-an",
            "-f",
            "null",
            "-",
        ],
        check=False,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    times = [float(match.group(1)) for match in PTS_PATTERN.finditer(output)]
    error = None if completed.returncode == 0 else f"ffmpeg scene detection exited with {completed.returncode}"
    return times, error


def _merge_candidates(groups: list[tuple[str, list[float]]], duration: float) -> list[dict]:
    merged: list[dict] = []
    for label, values in groups:
        for raw_value in values:
            value = min(max(0.0, raw_value), max(0.0, duration - 0.05))
            existing = next((item for item in merged if abs(item["timestamp"] - value) < 0.3), None)
            if existing:
                if label not in existing["sources"]:
                    existing["sources"].append(label)
                continue
            merged.append({"timestamp": round(value, 3), "sources": [label]})
    return sorted(merged, key=lambda item: item["timestamp"])


def _evenly_pick(items: list[dict], count: int) -> list[dict]:
    if count <= 0:
        return []
    if len(items) <= count:
        return items
    if count == 1:
        return [items[len(items) // 2]]
    indexes = {round(index * (len(items) - 1) / (count - 1)) for index in range(count)}
    return [items[index] for index in sorted(indexes)]


def _interior_pick(items: list[dict], count: int) -> list[dict]:
    if count <= 0:
        return []
    if len(items) <= count:
        return items
    indexes = {
        round((index + 1) * (len(items) - 1) / (count + 1))
        for index in range(count)
    }
    return [items[index] for index in sorted(indexes)]


def _limit_candidates(items: list[dict], limit: int) -> list[dict]:
    if len(items) <= limit:
        return items
    selected = [items[0], items[-1]]
    edge_candidates = [
        item
        for item in items
        if item not in selected
        and ("opening" in item["sources"] or "ending" in item["sources"])
    ]
    edge_count = min(4, limit - len(selected), len(edge_candidates))
    selected.extend(_evenly_pick(edge_candidates, edge_count))
    opening_end = max(
        (item["timestamp"] for item in items if "opening" in item["sources"]),
        default=items[0]["timestamp"],
    )
    ending_start = min(
        (item["timestamp"] for item in items if "ending" in item["sources"]),
        default=items[-1]["timestamp"],
    )
    middle_candidates = [
        item
        for item in items
        if item not in selected
        and opening_end < item["timestamp"] < ending_start
    ]
    middle_count = min(limit - len(selected), len(middle_candidates))
    selected.extend(_interior_pick(middle_candidates, middle_count))
    remaining = [item for item in items if item not in selected]
    selected.extend(_evenly_pick(remaining, limit - len(selected)))
    unique = {item["timestamp"]: item for item in selected}
    return sorted(unique.values(), key=lambda item: item["timestamp"])


def _extract_frame(ffmpeg: str, source: Path, target: Path, timestamp: float, max_width: int) -> None:
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-vf",
            f"scale={max_width}:-2:force_original_aspect_ratio=decrease",
            "-q:v",
            "2",
            str(target),
        ],
        check=True,
    )


def _contact_sheet(
    ffmpeg: str,
    source: Path,
    target: Path,
    duration: float,
    count: int = 20,
) -> None:
    columns = 4
    rows = math.ceil(count / columns)
    fps = count / max(duration, 0.1)
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vf",
            f"fps={fps:.8f},scale=320:-2,tile={columns}x{rows}:padding=4:margin=4",
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(target),
        ],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract timestamped key frames and a contact sheet.")
    parser.add_argument("video", help="Local video path")
    parser.add_argument("output_dir", help="Directory for frames and evidence_manifest.json")
    parser.add_argument("--interval", type=float, default=None, help="Regular sampling interval in seconds")
    parser.add_argument("--opening-seconds", type=float, default=10.0)
    parser.add_argument("--opening-step", type=float, default=2.0)
    parser.add_argument("--ending-seconds", type=float, default=10.0)
    parser.add_argument("--ending-step", type=float, default=3.0)
    parser.add_argument("--scene-threshold", type=float, default=0.28)
    parser.add_argument("--no-scene-detection", action="store_true")
    parser.add_argument("--max-frames", type=int, default=80)
    parser.add_argument("--max-width", type=int, default=960)
    args = parser.parse_args()

    source = Path(args.video).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Input video does not exist: {source}")
    if args.max_frames < 8:
        raise SystemExit("--max-frames must be at least 8")
    if args.opening_step <= 0 or args.ending_step <= 0:
        raise SystemExit("Opening and ending steps must be positive")

    ffmpeg = resolve_tool("ffmpeg", source.parent)
    ffprobe = resolve_tool("ffprobe", source.parent)
    if not ffmpeg or not ffprobe:
        raise SystemExit("ffmpeg and ffprobe are required after full tool discovery.")

    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = _probe(ffprobe, source)
    duration = float(metadata["duration_seconds"])
    interval = args.interval or _auto_interval(duration)
    if interval <= 0:
        raise SystemExit("--interval must be positive")

    opening_stop = min(duration, args.opening_seconds)
    ending_start = max(0.0, duration - args.ending_seconds)
    scene_times: list[float] = []
    scene_error: str | None = None
    if not args.no_scene_detection:
        scene_times, scene_error = _scene_times(ffmpeg, source, args.scene_threshold)

    candidates = _merge_candidates(
        [
            ("opening", _sequence(0.0, opening_stop, args.opening_step)),
            ("interval", _sequence(0.0, duration, interval)),
            ("scene", scene_times),
            ("ending", _sequence(ending_start, duration, args.ending_step)),
        ],
        duration,
    )
    candidates = _limit_candidates(candidates, args.max_frames)

    frame_entries: list[dict] = []
    for index, candidate in enumerate(candidates, start=1):
        milliseconds = round(candidate["timestamp"] * 1000)
        target = output_dir / f"frame_{index:03d}_{milliseconds:09d}ms.jpg"
        _extract_frame(ffmpeg, source, target, candidate["timestamp"], args.max_width)
        frame_entries.append(
            {
                "timestamp_seconds": candidate["timestamp"],
                "sources": candidate["sources"],
                "file": str(target),
            }
        )

    contact_sheet = output_dir / "contact_sheet.jpg"
    _contact_sheet(ffmpeg, source, contact_sheet, duration)
    manifest = {
        "source": str(source),
        "metadata": metadata,
        "sampling": {
            "regular_interval_seconds": interval,
            "opening_seconds": args.opening_seconds,
            "opening_step_seconds": args.opening_step,
            "ending_seconds": args.ending_seconds,
            "ending_step_seconds": args.ending_step,
            "scene_detection": not args.no_scene_detection,
            "scene_threshold": args.scene_threshold,
            "scene_changes_found": len(scene_times),
            "scene_detection_error": scene_error,
        },
        "contact_sheet": str(contact_sheet),
        "frames": frame_entries,
    }
    manifest_path = output_dir / "evidence_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
