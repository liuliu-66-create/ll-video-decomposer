#!/usr/bin/env python3
"""Diagnose or install an isolated fast transcription environment."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import venv
import wave
from pathlib import Path

from tool_paths import discover, write_config


SCRIPT_DIR = Path(__file__).resolve().parent
RUNNER = SCRIPT_DIR / "faster_whisper_runner.py"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(command: list[str], timeout: int = 1200) -> None:
    print(" ".join(command), flush=True)
    subprocess.run(command, timeout=timeout, check=True)


def make_probe_audio(path: Path) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\0\0" * 16000)


def test_backend(python: Path, model: str, device: str, compute_type: str, timeout: int) -> dict:
    with tempfile.TemporaryDirectory(prefix="ll-video-setup-") as temp_name:
        temp_dir = Path(temp_name)
        audio = temp_dir / "probe.wav"
        output = temp_dir / "probe.txt"
        segments = temp_dir / "probe.segments.json"
        make_probe_audio(audio)
        command = [
            str(python),
            str(RUNNER),
            str(audio),
            str(output),
            "--segments-output",
            str(segments),
            "--model",
            model,
            "--device",
            device,
            "--compute-type",
            compute_type,
            "--beam-size",
            "1",
            "--cpu-threads",
            str(max(1, min(os.cpu_count() or 4, 12))),
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return {
            "ok": completed.returncode == 0,
            "device": device,
            "compute_type": compute_type,
            "stdout": completed.stdout.strip(),
            "error": completed.stderr.strip(),
        }


def write_backend_tests(project: Path, python: Path, tests: list[dict]) -> None:
    path = project / ".video-decomposer-cache" / "backend-status.json"
    try:
        status = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        status = {}
    for test in tests:
        key = f"faster-whisper:{test['device']}:{python}"
        status[key] = {
            "available": bool(test["ok"]),
            "engine": "faster-whisper",
            "device": test["device"],
            "reason": test["error"].splitlines()[-1][:500] if test["error"] else "",
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare the fastest safe transcription backend.")
    parser.add_argument("--project", default=".")
    parser.add_argument("--install", action="store_true", help="Create an isolated environment and install faster-whisper")
    parser.add_argument("--prefer-gpu", action="store_true", help="Also install a CUDA PyTorch runtime when NVIDIA is present")
    parser.add_argument("--model", default="small")
    parser.add_argument("--venv")
    parser.add_argument("--torch-index-url", default="https://download.pytorch.org/whl/cu128")
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    args = parser.parse_args()

    project = Path(args.project).expanduser().resolve()
    project.mkdir(parents=True, exist_ok=True)
    before = discover(project)
    hardware = before.get("hardware", {})
    recommendation = {
        "nvidia_detected": bool(hardware.get("nvidia_gpus")),
        "apple_silicon": bool(hardware.get("apple_silicon")),
        "recommended_engine": (
            "faster-whisper CUDA"
            if hardware.get("nvidia_gpus")
            else "whisper.cpp Metal"
            if hardware.get("apple_silicon")
            else "faster-whisper CPU int8"
        ),
        "install_required": not bool(before.get("python_faster_whisper")),
    }
    if not args.install:
        print(json.dumps({"hardware": hardware, "current": before, "recommendation": recommendation}, ensure_ascii=False, indent=2))
        return 0

    target_venv = Path(args.venv).expanduser().resolve() if args.venv else project / ".video-decomposer-venv"
    python = venv_python(target_venv)
    if not python.is_file():
        print(f"Creating isolated environment: {target_venv}", flush=True)
        venv.EnvBuilder(with_pip=True, clear=False).create(target_venv)
    run([str(python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], args.timeout_seconds)
    run([str(python), "-m", "pip", "install", "faster-whisper>=1.1,<2"], args.timeout_seconds)

    gpu_requested = args.prefer_gpu and bool(hardware.get("nvidia_gpus"))
    tests: list[dict] = []
    gpu_install_error: str | None = None
    if gpu_requested:
        tests.append(test_backend(python, args.model, "cuda", "int8_float16", args.timeout_seconds))
        if not tests[-1]["ok"]:
            try:
                run(
                    [
                        str(python),
                        "-m",
                        "pip",
                        "install",
                        "torch",
                        "--index-url",
                        args.torch_index_url,
                    ],
                    args.timeout_seconds,
                )
                tests.append(test_backend(python, args.model, "cuda", "int8_float16", args.timeout_seconds))
            except (OSError, subprocess.SubprocessError) as error:
                gpu_install_error = str(error)
                print(f"GPU runtime installation did not complete; continuing with CPU INT8: {error}", file=sys.stderr)
    if not any(test["ok"] and test["device"] == "cuda" for test in tests):
        tests.append(test_backend(python, args.model, "cpu", "int8", args.timeout_seconds))

    write_backend_tests(project, python, tests)
    after = discover(project, refresh=True)
    write_config(after)
    usable = any(test["ok"] for test in tests)
    print(
        json.dumps(
            {
                "installed": usable,
                "environment": str(target_venv),
                "python": str(python),
                "tests": tests,
                "selected": next((test for test in tests if test["ok"]), None),
                "gpu_install_error": gpu_install_error,
                "config_path": after.get("config_path"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not usable:
        raise SystemExit("The isolated environment was created, but neither the GPU nor CPU backend passed validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
