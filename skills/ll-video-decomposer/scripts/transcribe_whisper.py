#!/usr/bin/env python3
"""Transcribe audio using discovered OpenAI Whisper or whisper.cpp resources."""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
from pathlib import Path

from tool_paths import discover_and_cache


def run_openai_cli(command: list[str], audio: Path, output: Path, model: str, language: str | None, model_dir: Path | None) -> None:
    cmd = [*command, str(audio), "--model", model, "--task", "transcribe", "--output_format", "txt", "--output_dir", str(output.parent), "--fp16", "False"]
    if language:
        cmd.extend(["--language", language])
    if model_dir:
        cmd.extend(["--model_dir", str(model_dir)])
    subprocess.run(cmd, check=True)
    generated = output.parent / f"{audio.stem}.txt"
    if generated.resolve() != output.resolve():
        output.write_text(generated.read_text(encoding="utf-8-sig"), encoding="utf-8")


def run_whisper_cpp(ffmpeg: str, model_path: str, audio: Path, output: Path, language: str | None) -> None:
    def escaped(path: str) -> str:
        return path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    filter_value = f"whisper=model='{escaped(model_path)}':language={language or 'auto'}:destination='{escaped(str(output))}':format=text"
    subprocess.run([ffmpeg, "-y", "-i", str(audio), "-af", filter_value, "-f", "null", "-"], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe audio with discovered Whisper tools.")
    parser.add_argument("audio")
    parser.add_argument("output")
    parser.add_argument("--model", default="small")
    parser.add_argument("--language", default=None)
    args = parser.parse_args()
    audio = Path(args.audio).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not audio.is_file():
        raise SystemExit(f"Audio file does not exist: {audio}")
    output.parent.mkdir(parents=True, exist_ok=True)
    tools = discover_and_cache(audio.parent)
    pt_models = [Path(p) for p in tools.get("models", {}).get("openai_pt", [])]
    matching_pt = next((p for p in pt_models if p.stem == args.model), None)
    model_dir = matching_pt.parent if matching_pt else None
    errors: list[str] = []

    attempts: list[list[str]] = []
    if tools.get("whisper"):
        attempts.append([str(tools["whisper"])])
    if tools.get("python_whisper"):
        attempts.append([str(tools["python_whisper"]), "-m", "whisper"])
    for command in attempts:
        try:
            run_openai_cli(command, audio, output, args.model, args.language, model_dir)
            print(output)
            return 0
        except (OSError, subprocess.SubprocessError) as error:
            errors.append(f"{' '.join(command)}: {error}")

    if importlib.util.find_spec("whisper") is not None:
        try:
            import whisper  # type: ignore
            loaded = whisper.load_model(args.model, download_root=str(model_dir) if model_dir else None)
            result = loaded.transcribe(str(audio), language=args.language, fp16=False)
            output.write_text(str(result.get("text", "")).strip() + "\n", encoding="utf-8")
            print(output)
            return 0
        except Exception as error:  # noqa: BLE001
            errors.append(f"current Python package: {error}")

    ggml_models = tools.get("models", {}).get("whisper_cpp", [])
    if tools.get("ffmpeg") and ggml_models:
        try:
            run_whisper_cpp(str(tools["ffmpeg"]), str(ggml_models[0]), audio, output, args.language)
            print(output)
            return 0
        except (OSError, subprocess.SubprocessError) as error:
            errors.append(f"ffmpeg whisper.cpp: {error}")

    raise SystemExit("No usable transcription route succeeded after full discovery. " + " | ".join(errors))


if __name__ == "__main__":
    raise SystemExit(main())
