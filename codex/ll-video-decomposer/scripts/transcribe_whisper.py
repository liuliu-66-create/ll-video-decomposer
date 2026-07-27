#!/usr/bin/env python3
"""Select the fastest available Whisper backend, transcribe, and cache the result."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

from tool_paths import discover_and_cache


SCRIPT_DIR = Path(__file__).resolve().parent
FASTER_RUNNER = SCRIPT_DIR / "faster_whisper_runner.py"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def audio_duration_seconds(audio: Path) -> float | None:
    try:
        with wave.open(str(audio), "rb") as source:
            return source.getnframes() / float(source.getframerate())
    except (wave.Error, OSError, ZeroDivisionError):
        return None


def audio_cache_key(audio: Path, model: str, language: str | None, mode: str) -> str:
    digest = hashlib.sha256()
    with audio.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    digest.update(f"\0{model}\0{language or 'auto'}\0{mode}\0v2".encode("utf-8"))
    return digest.hexdigest()


def backend_key(candidate: dict) -> str:
    executable = candidate.get("python") or candidate.get("binary") or candidate.get("ffmpeg") or ""
    return f"{candidate['engine']}:{candidate['device']}:{executable}"


def load_backend_status(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_backend_status(path: Path, status: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def persistent_backend_failure(error: Exception) -> bool:
    message = str(error).lower()
    signals = (
        "cublas",
        "cudnn",
        "cuda driver",
        "cuda failed",
        "not found or cannot be loaded",
        "requested cuda",
        "invalid device",
    )
    return any(signal in message for signal in signals)


def matching_probe(tools: dict, python: str | None) -> dict:
    if not python:
        return {}
    try:
        target = Path(python).resolve()
    except OSError:
        return {}
    for probe in tools.get("python_backends", []):
        value = probe.get("python")
        if not value:
            continue
        try:
            if Path(str(value)).resolve() == target:
                return probe
        except OSError:
            continue
    return {}


def matching_ggml_model(tools: dict, model: str) -> str | None:
    models = [str(value) for value in tools.get("models", {}).get("whisper_cpp", [])]
    exact = [value for value in models if Path(value).stem == f"ggml-{model}"]
    if exact:
        return exact[0]
    quantized = [value for value in models if Path(value).stem.startswith(f"ggml-{model}-")]
    return quantized[0] if quantized else None


def build_candidates(
    tools: dict,
    engine: str,
    requested_device: str,
    model: str,
    allow_slow: bool,
    duration: float | None,
) -> list[dict]:
    hardware = tools.get("hardware", {})
    has_nvidia = bool(hardware.get("nvidia_gpus"))
    apple_silicon = bool(hardware.get("apple_silicon"))
    has_amd = bool(hardware.get("amd_gpu"))
    faster_python = tools.get("python_faster_whisper")
    faster_probe = matching_probe(tools, str(faster_python) if faster_python else None)
    whisper_python = tools.get("python_whisper")
    whisper_probe = matching_probe(tools, str(whisper_python) if whisper_python else None)
    ggml_model = matching_ggml_model(tools, model)
    whisper_cpp_ready = bool(ggml_model and (tools.get("whisper_cpp") or tools.get("ffmpeg")))
    candidates: list[dict] = []

    def wanted(name: str) -> bool:
        return engine in {"auto", name}

    cuda_allowed = requested_device in {"auto", "cuda"}
    cpu_allowed = requested_device in {"auto", "cpu"}

    if wanted("faster-whisper") and faster_python and has_nvidia and cuda_allowed:
        candidates.append(
            {
                "engine": "faster-whisper",
                "device": "cuda",
                "compute_type": "int8_float16",
                "python": str(faster_python),
                "verified_cuda": bool(faster_probe.get("ctranslate2_cuda")),
            }
        )

    if wanted("openai-whisper") and whisper_python and cuda_allowed and whisper_probe.get("torch_cuda"):
        candidates.append(
            {
                "engine": "openai-whisper",
                "device": "cuda",
                "python": str(whisper_python),
                "command": [str(whisper_python), "-m", "whisper"],
            }
        )

    if wanted("whisper-cpp") and whisper_cpp_ready and (apple_silicon or has_amd or engine == "whisper-cpp"):
        candidates.append(
            {
                "engine": "whisper-cpp",
                "device": "accelerated" if apple_silicon else "auto",
                "binary": str(tools.get("whisper_cpp") or tools["ffmpeg"]),
                "whisper_cli": str(tools["whisper_cpp"]) if tools.get("whisper_cpp") else None,
                "ffmpeg": str(tools["ffmpeg"]) if tools.get("ffmpeg") else None,
                "model_path": ggml_model,
            }
        )

    if wanted("faster-whisper") and faster_python and cpu_allowed:
        candidates.append(
            {
                "engine": "faster-whisper",
                "device": "cpu",
                "compute_type": "int8",
                "python": str(faster_python),
            }
        )

    if wanted("whisper-cpp") and whisper_cpp_ready and not any(item["engine"] == "whisper-cpp" for item in candidates):
        candidates.append(
            {
                "engine": "whisper-cpp",
                "device": "auto",
                "binary": str(tools.get("whisper_cpp") or tools["ffmpeg"]),
                "whisper_cli": str(tools["whisper_cpp"]) if tools.get("whisper_cpp") else None,
                "ffmpeg": str(tools["ffmpeg"]) if tools.get("ffmpeg") else None,
                "model_path": ggml_model,
            }
        )

    slow_is_allowed = allow_slow or engine == "openai-whisper" or duration is None or duration <= 60
    if wanted("openai-whisper") and whisper_python and cpu_allowed and slow_is_allowed:
        candidates.append(
            {
                "engine": "openai-whisper",
                "device": "cpu",
                "python": str(whisper_python),
                "command": [str(whisper_python), "-m", "whisper"],
                "slow": True,
            }
        )
    elif wanted("openai-whisper") and tools.get("whisper") and cpu_allowed and slow_is_allowed:
        candidates.append(
            {
                "engine": "openai-whisper",
                "device": "cpu",
                "command": [str(tools["whisper"])],
                "slow": True,
            }
        )
    return candidates


def run_faster_whisper(
    candidate: dict,
    audio: Path,
    output: Path,
    segments_output: Path,
    model: str,
    language: str | None,
    beam_size: int,
    timeout: int,
) -> dict:
    cpu_threads = max(1, min(os.cpu_count() or 4, 12))
    command = [
        str(candidate["python"]),
        str(FASTER_RUNNER),
        str(audio),
        str(output),
        "--segments-output",
        str(segments_output),
        "--model",
        model,
        "--device",
        str(candidate["device"]),
        "--compute-type",
        str(candidate["compute_type"]),
        "--beam-size",
        str(beam_size),
        "--cpu-threads",
        str(cpu_threads),
    ]
    if language:
        command.extend(["--language", language])
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or f"exit {completed.returncode}")
    try:
        return json.loads(completed.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {}


def run_openai_whisper(
    candidate: dict,
    audio: Path,
    output: Path,
    model: str,
    language: str | None,
    model_dir: Path | None,
    timeout: int,
) -> dict:
    command = [
        *candidate["command"],
        str(audio),
        "--model",
        model,
        "--task",
        "transcribe",
        "--output_format",
        "txt",
        "--output_dir",
        str(output.parent),
        "--device",
        str(candidate["device"]),
        "--fp16",
        "True" if candidate["device"] == "cuda" else "False",
    ]
    if language:
        command.extend(["--language", language])
    if model_dir:
        command.extend(["--model_dir", str(model_dir)])
    completed = subprocess.run(command, timeout=timeout, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"exit {completed.returncode}")
    generated = output.parent / f"{audio.stem}.txt"
    if not generated.is_file():
        raise RuntimeError(f"expected output not created: {generated}")
    if generated.resolve() != output.resolve():
        shutil.copyfile(generated, output)
    return {}


def run_whisper_cpp(
    candidate: dict,
    audio: Path,
    output: Path,
    language: str | None,
    timeout: int,
) -> dict:
    if candidate.get("whisper_cli"):
        prefix = output.with_suffix("")
        command = [
            str(candidate["whisper_cli"]),
            "-m",
            str(candidate["model_path"]),
            "-f",
            str(audio),
            "-l",
            language or "auto",
            "-otxt",
            "-of",
            str(prefix),
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
        generated = Path(f"{prefix}.txt")
        if completed.returncode != 0 or not generated.is_file():
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or f"exit {completed.returncode}")
        if generated.resolve() != output.resolve():
            shutil.copyfile(generated, output)
        return {}

    def escaped(path: str) -> str:
        return path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")

    filter_value = (
        f"whisper=model='{escaped(str(candidate['model_path']))}':"
        f"language={language or 'auto'}:destination='{escaped(str(output))}':format=text"
    )
    completed = subprocess.run(
        [str(candidate["ffmpeg"]), "-hide_banner", "-y", "-i", str(audio), "-af", filter_value, "-f", "null", "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0 or not output.is_file():
        raise RuntimeError(completed.stderr.strip() or f"exit {completed.returncode}")
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe with the fastest available Whisper backend.")
    parser.add_argument("audio")
    parser.add_argument("output")
    parser.add_argument("--project", default=".", help="Project directory for tool discovery and cache")
    parser.add_argument("--model", default="small")
    parser.add_argument("--language", default=None)
    parser.add_argument("--mode", choices=("fast", "balanced", "accurate"), default="fast")
    parser.add_argument(
        "--engine",
        choices=("auto", "faster-whisper", "whisper-cpp", "openai-whisper"),
        default="auto",
    )
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--allow-slow", action="store_true", help="Allow original Whisper on CPU for long audio")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--cache-dir")
    parser.add_argument("--retry-failed-backends", action="store_true")
    parser.add_argument("--plan", action="store_true", help="Print the backend plan without transcribing")
    args = parser.parse_args()

    audio = Path(args.audio).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    project = Path(args.project).expanduser().resolve()
    if not audio.is_file():
        raise SystemExit(f"Audio file does not exist: {audio}")
    output.parent.mkdir(parents=True, exist_ok=True)
    duration = audio_duration_seconds(audio)
    tools = discover_and_cache(project)
    candidates = build_candidates(tools, args.engine, args.device, args.model, args.allow_slow, duration)
    backend_status_path = project / ".video-decomposer-cache" / "backend-status.json"
    backend_status = load_backend_status(backend_status_path)
    skipped_candidates: list[dict] = []
    if not args.retry_failed_backends:
        ready_candidates: list[dict] = []
        for candidate in candidates:
            status = backend_status.get(backend_key(candidate), {})
            if status.get("available") is False:
                skipped_candidates.append({**candidate, "skip_reason": status.get("reason", "previous validation failed")})
            else:
                ready_candidates.append(candidate)
        candidates = ready_candidates
    if args.plan:
        print(
            json.dumps(
                {
                    "duration_seconds": duration,
                    "hardware": tools.get("hardware"),
                    "candidates": candidates,
                    "skipped_candidates": skipped_candidates,
                    "slow_cpu_skipped": not args.allow_slow and duration is not None and duration > 60,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if not candidates:
        raise SystemExit(
            "No fast transcription backend is ready. Run "
            f"`python {SCRIPT_DIR / 'setup_transcription.py'} --project {project} --install --model {args.model}` "
            "after getting the user's permission. Use --allow-slow only when a slow original-Whisper CPU run is acceptable."
        )

    beam_size = {"fast": 1, "balanced": 3, "accurate": 5}[args.mode]
    cache_root = (
        Path(args.cache_dir).expanduser().resolve()
        if args.cache_dir
        else project / ".video-decomposer-cache" / "transcripts"
    )
    cache_key = audio_cache_key(audio, args.model, args.language, args.mode)
    cache_text = cache_root / f"{cache_key}.txt"
    cache_segments = cache_root / f"{cache_key}.segments.json"
    cache_metadata = cache_root / f"{cache_key}.meta.json"
    output_segments = output.with_suffix(".segments.json")
    if not args.no_cache and cache_text.is_file():
        shutil.copyfile(cache_text, output)
        if cache_segments.is_file():
            shutil.copyfile(cache_segments, output_segments)
        metadata = json.loads(cache_metadata.read_text(encoding="utf-8")) if cache_metadata.is_file() else {}
        metadata.update({"cached": True, "output": str(output)})
        print(json.dumps(metadata, ensure_ascii=False))
        return 0

    pt_models = [Path(path) for path in tools.get("models", {}).get("openai_pt", [])]
    matching_pt = next((path for path in pt_models if path.stem == args.model), None)
    model_dir = matching_pt.parent if matching_pt else None
    errors: list[str] = []
    for candidate in candidates:
        label = f"{candidate['engine']}:{candidate['device']}"
        print(f"Trying {label}", file=sys.stderr, flush=True)
        started = time.perf_counter()
        try:
            with tempfile.TemporaryDirectory(prefix="ll-video-transcribe-", dir=str(output.parent)) as temp_name:
                temp_dir = Path(temp_name)
                temp_output = temp_dir / "transcript.txt"
                temp_segments = temp_dir / "transcript.segments.json"
                if candidate["engine"] == "faster-whisper":
                    runner_metadata = run_faster_whisper(
                        candidate,
                        audio,
                        temp_output,
                        temp_segments,
                        args.model,
                        args.language,
                        beam_size,
                        args.timeout_seconds,
                    )
                elif candidate["engine"] == "openai-whisper":
                    runner_metadata = run_openai_whisper(
                        candidate,
                        audio,
                        temp_output,
                        args.model,
                        args.language,
                        model_dir,
                        args.timeout_seconds,
                    )
                else:
                    runner_metadata = run_whisper_cpp(
                        candidate,
                        audio,
                        temp_output,
                        args.language,
                        args.timeout_seconds,
                    )
                if not temp_output.is_file() or not temp_output.read_text(encoding="utf-8-sig").strip():
                    raise RuntimeError("backend completed without a readable transcript")
                shutil.copyfile(temp_output, output)
                if temp_segments.is_file():
                    shutil.copyfile(temp_segments, output_segments)
                elapsed = time.perf_counter() - started
                metadata = {
                    "cached": False,
                    "engine": candidate["engine"],
                    "device": candidate["device"],
                    "model": args.model,
                    "mode": args.mode,
                    "language": args.language,
                    "duration_seconds": duration,
                    "elapsed_seconds": round(elapsed, 3),
                    "output": str(output),
                    **runner_metadata,
                }
                backend_status[backend_key(candidate)] = {
                    "available": True,
                    "engine": candidate["engine"],
                    "device": candidate["device"],
                }
                write_backend_status(backend_status_path, backend_status)
                if not args.no_cache:
                    cache_root.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(output, cache_text)
                    if output_segments.is_file():
                        shutil.copyfile(output_segments, cache_segments)
                    cache_metadata.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(json.dumps(metadata, ensure_ascii=False))
                return 0
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            errors.append(f"{label}: {error}")
            print(f"{label} failed: {error}", file=sys.stderr, flush=True)
            if persistent_backend_failure(error):
                backend_status[backend_key(candidate)] = {
                    "available": False,
                    "engine": candidate["engine"],
                    "device": candidate["device"],
                    "reason": str(error).splitlines()[-1][:500],
                }
                write_backend_status(backend_status_path, backend_status)

    raise SystemExit(
        "All prepared transcription routes failed. "
        + " | ".join(errors)
        + f" | Re-run `{SCRIPT_DIR / 'setup_transcription.py'} --project {project} --install --model {args.model}` "
        "after getting the user's permission."
    )


if __name__ == "__main__":
    raise SystemExit(main())
