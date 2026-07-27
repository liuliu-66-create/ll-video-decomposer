"""Discover and cache local video-processing tools without scanning whole drives."""

from __future__ import annotations

import json
import os
import platform
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
    if "\ufffd" in value:
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
        project / ".video-decomposer-venv",
        project / ".venv",
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


def _python_candidates(roots: list[Path], project: Path) -> list[str]:
    candidates = [
        sys.executable,
        str(project / ".video-decomposer-venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")),
        str(project / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")),
    ]
    for root in roots:
        patterns = (
            ("Python*/python.exe", "*/Scripts/python.exe", "Scripts/python.exe")
            if os.name == "nt"
            else ("*/bin/python", "bin/python", "python")
        )
        for pattern in patterns:
            try:
                candidates.extend(str(path) for path in root.glob(pattern))
            except OSError:
                continue
    return list(dict.fromkeys(path for candidate in candidates if (path := _existing(candidate))))


def _probe_python(python: str) -> dict:
    script = r"""
import importlib.util
import json

result = {
    "python": __import__("sys").executable,
    "faster_whisper": bool(importlib.util.find_spec("faster_whisper")),
    "openai_whisper": bool(importlib.util.find_spec("whisper")),
    "torch_cuda": False,
    "ctranslate2_cuda": False,
    "ctranslate2_compute_types": [],
}
if importlib.util.find_spec("torch"):
    try:
        import torch
        result["torch_cuda"] = bool(torch.cuda.is_available())
        result["torch_version"] = str(torch.__version__)
    except Exception as error:
        result["torch_error"] = str(error)
if importlib.util.find_spec("ctranslate2"):
    try:
        import ctranslate2
        result["ctranslate2_version"] = str(ctranslate2.__version__)
        try:
            compute_types = sorted(ctranslate2.get_supported_compute_types("cuda"))
            result["ctranslate2_compute_types"] = compute_types
            result["ctranslate2_cuda"] = bool(compute_types)
        except Exception as error:
            result["ctranslate2_cuda_error"] = str(error)
    except Exception as error:
        result["ctranslate2_error"] = str(error)
print(json.dumps(result, ensure_ascii=True))
"""
    try:
        completed = subprocess.run(
            [python, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
        if completed.returncode == 0:
            return json.loads(completed.stdout.strip())
        return {"python": python, "error": completed.stderr.strip() or f"exit {completed.returncode}"}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        return {"python": python, "error": str(error)}


def _python_inventory(roots: list[Path], project: Path) -> list[dict]:
    return [_probe_python(python) for python in _python_candidates(roots, project)]


def _python_with_backend(inventory: list[dict], key: str) -> str | None:
    for probe in inventory:
        if probe.get(key) and probe.get("python"):
            return str(probe["python"])
    return None


def _nvidia_inventory() -> list[dict]:
    command = shutil.which("nvidia-smi")
    if not command:
        return []
    try:
        completed = subprocess.run(
            [
                command,
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if completed.returncode != 0:
        return []
    gpus: list[dict] = []
    for line in completed.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 3:
            continue
        try:
            memory_mb = int(parts[1])
        except ValueError:
            memory_mb = None
        gpus.append({"name": parts[0], "memory_mb": memory_mb, "driver": parts[2]})
    return gpus


def _memory_total_mb() -> int | None:
    try:
        if os.name == "nt":
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("length", ctypes.c_ulong),
                    ("memory_load", ctypes.c_ulong),
                    ("total_phys", ctypes.c_ulonglong),
                    ("avail_phys", ctypes.c_ulonglong),
                    ("total_page_file", ctypes.c_ulonglong),
                    ("avail_page_file", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong),
                    ("avail_virtual", ctypes.c_ulonglong),
                    ("avail_extended_virtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.length = ctypes.sizeof(MemoryStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return int(status.total_phys / (1024 * 1024))
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return int(pages * page_size / (1024 * 1024))
    except (AttributeError, OSError, ValueError):
        return None


def _display_adapters() -> list[str]:
    if os.name == "nt":
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if not powershell:
            return []
        try:
            completed = subprocess.run(
                [
                    powershell,
                    "-NoProfile",
                    "-Command",
                    "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
                check=False,
            )
            if completed.returncode == 0:
                return list(dict.fromkeys(line.strip() for line in completed.stdout.splitlines() if line.strip()))
        except (OSError, subprocess.SubprocessError):
            return []
    if platform.system() == "Linux":
        lspci = shutil.which("lspci")
        if lspci:
            try:
                completed = subprocess.run(
                    [lspci],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=8,
                    check=False,
                )
                return [
                    line.strip()
                    for line in completed.stdout.splitlines()
                    if any(label in line.lower() for label in ("vga", "3d controller", "display"))
                ]
            except (OSError, subprocess.SubprocessError):
                return []
    return []


def hardware_profile() -> dict:
    system = platform.system()
    machine = platform.machine()
    adapters = _display_adapters()
    return {
        "system": system,
        "machine": machine,
        "logical_cpus": os.cpu_count(),
        "memory_mb": _memory_total_mb(),
        "apple_silicon": system == "Darwin" and machine.lower() in {"arm64", "aarch64"},
        "nvidia_gpus": _nvidia_inventory(),
        "display_adapters": adapters,
        "amd_gpu": any("amd" in name.lower() or "radeon" in name.lower() for name in adapters),
    }


def _python_with_whisper(roots: list[Path], project: Path) -> str | None:
    candidates = _python_candidates(roots, project)
    for python in dict.fromkeys(candidates):
        try:
            result = subprocess.run(
                [python, "-c", "import importlib.util as i;raise SystemExit(0 if i.find_spec('whisper') else 1)"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8,
                check=False,
            )
            if result.returncode == 0:
                return python
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


def discover(start: Path | None = None, refresh: bool = False) -> dict:
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

    cached_inventory = cached.get("python_backends")
    if not refresh and isinstance(cached_inventory, list) and cached_inventory:
        python_inventory = [
            probe
            for probe in cached_inventory
            if isinstance(probe, dict)
            and isinstance(probe.get("python"), str)
            and "\ufffd" not in str(probe.get("python"))
        ]
    else:
        python_inventory = _python_inventory(roots, project)
    cached_python = _cached(cached.get("python_whisper"))
    cached_faster = _cached(cached.get("python_faster_whisper"))
    result["python_whisper"] = cached_python or _python_with_backend(python_inventory, "openai_whisper") or _python_with_whisper(roots, project)
    result["python_faster_whisper"] = cached_faster or _python_with_backend(python_inventory, "faster_whisper")
    result["python_backends"] = python_inventory
    cached_hardware = cached.get("hardware")
    result["hardware"] = cached_hardware if not refresh and isinstance(cached_hardware, dict) else hardware_profile()
    result["models"] = _model_inventory(home, project)
    return result


def write_config(data: dict, path: Path | None = None) -> Path:
    target = path or Path(str(data["config_path"]))
    payload = {key: value for key, value in data.items() if key != "config_path"}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def discover_and_cache(start: Path | None = None, refresh: bool = False) -> dict:
    data = discover(start, refresh=refresh)
    write_config(data)
    return data


def resolve_tool(key: str, start: Path | None = None) -> str | None:
    value = discover_and_cache(start).get(key)
    return str(value) if value else None
