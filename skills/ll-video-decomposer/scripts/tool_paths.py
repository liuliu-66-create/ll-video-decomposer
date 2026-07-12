"""Discover and cache local video-processing tools without scanning whole drives."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


CONFIG_NAME = ".video-decomposer-tools.json"
TOOL_NAMES = {
    "ffmpeg": "ffmpeg.exe" if os.name == "nt" else "ffmpeg",
    "ffprobe": "ffprobe.exe" if os.name == "nt" else "ffprobe",
    "whisper": "whisper.exe" if os.name == "nt" else "whisper",
    "yt_dlp": "yt-dlp.exe" if os.name == "nt" else "yt-dlp",
    "whisper_cpp": "whisper-cli.exe" if os.name == "nt" else "whisper-cli",
}


def _is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def _existing(value: str | None) -> str | None:
    if not value:
        return None
    path = Path(value).expanduser()
    return str(path.resolve()) if _is_file(path) else None


def _cached(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        return None
    return str(path)


def find_config(start: Path) -> Path:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for directory in (current, *current.parents):
        candidate = directory / CONFIG_NAME
        if _is_file(candidate):
            return candidate
    return current / CONFIG_NAME


def load_config(start: Path) -> tuple[Path, dict]:
    path = find_config(start)
    if not _is_file(path):
        return path, {}
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return path, {}


def _common_roots(home: Path, project: Path) -> list[Path]:
    roots = [
        project,
        home / "tools",
        Path("C:/tools"),
        Path("C:/ffmpeg"),
        Path("C:/Program Files/ffmpeg"),
        Path("C:/Program Files (x86)/ffmpeg"),
        home / "AppData/Local/Programs/Python",
        home / "AppData/Roaming/Python",
        home / "miniconda3",
        home / "anaconda3",
        home / ".conda",
    ]
    return [root for root in roots if _is_dir(root)]


def _find_named(roots: list[Path], filename: str) -> list[str]:
    found: list[str] = []
    for root in roots:
        direct_candidates = [root / filename, root / "bin" / filename, root / "Scripts" / filename]
        for candidate in direct_candidates:
            if _is_file(candidate):
                found.append(str(candidate.resolve()))
        if "Python" in str(root) or root.name in {"tools", "ffmpeg", "miniconda3", "anaconda3", ".conda"}:
            try:
                found.extend(str(path.resolve()) for path in root.glob(f"**/{filename}") if _is_file(path))
            except OSError:
                pass
    return list(dict.fromkeys(found))


def _python_with_whisper(roots: list[Path]) -> str | None:
    candidates = [sys.executable]
    for root in roots:
        candidates.extend(str(path) for path in root.glob("Python*/python.exe"))
        candidates.extend(str(path) for path in root.glob("*/Scripts/python.exe"))
    for python in dict.fromkeys(candidates):
        path = _existing(python)
        if not path:
            continue
        try:
            result = subprocess.run(
                [path, "-c", "import importlib.util as i;raise SystemExit(0 if i.find_spec('whisper') else 1)"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8,
                check=False,
            )
            if result.returncode == 0:
                return path
        except (OSError, subprocess.SubprocessError):
            continue
    return None


def _model_inventory(home: Path, project: Path) -> dict[str, list[str]]:
    pt: list[str] = []
    ggml: list[str] = []
    for root in [home / ".cache/whisper", project, home / "tools", Path("C:/tools")]:
        if not _is_dir(root):
            continue
        try:
            pt.extend(str(path.resolve()) for path in root.glob("*.pt") if _is_file(path))
            ggml.extend(str(path.resolve()) for path in root.glob("**/ggml-*.bin") if _is_file(path))
        except OSError:
            pass
    return {"openai_pt": list(dict.fromkeys(pt)), "whisper_cpp": list(dict.fromkeys(ggml))}


def discover(start: Path | None = None) -> dict:
    project = (start or Path.cwd()).resolve()
    if project.is_file():
        project = project.parent
    home = Path.home()
    config_path, cached = load_config(project)
    roots = _common_roots(home, project)
    result: dict[str, object] = {"config_path": str(config_path)}

    for key, filename in TOOL_NAMES.items():
        cached_path = _cached(cached.get(key))
        path_hit = _existing(shutil.which(filename) or shutil.which(filename.removesuffix(".exe")))
        common_hits = _find_named(roots, filename)
        result[key] = cached_path or path_hit or (common_hits[0] if common_hits else None)

    cached_python = _cached(cached.get("python_whisper"))
    result["python_whisper"] = cached_python or _python_with_whisper(roots)
    result["models"] = _model_inventory(home, project)
    return result


def write_config(data: dict, path: Path | None = None) -> Path:
    target = path or Path(str(data["config_path"]))
    payload = {key: value for key, value in data.items() if key != "config_path"}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def discover_and_cache(start: Path | None = None) -> dict:
    data = discover(start)
    write_config(data)
    return data


def resolve_tool(key: str, start: Path | None = None) -> str | None:
    value = discover_and_cache(start).get(key)
    return str(value) if value else None
