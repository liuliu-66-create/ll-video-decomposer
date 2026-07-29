from __future__ import annotations

import sys
import tempfile
import unittest
import wave
from pathlib import Path


sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1] / "codex" / "ll-video-decomposer" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import tool_paths
import transcribe_whisper


class TranscriptionRouterTests(unittest.TestCase):
    def tools(self) -> dict:
        python = str(Path("C:/fast/python.exe"))
        return {
            "hardware": {
                "nvidia_gpus": [{"name": "RTX", "memory_mb": 8192}],
                "apple_silicon": False,
                "amd_gpu": False,
            },
            "python_faster_whisper": python,
            "python_whisper": None,
            "python_backends": [
                {
                    "python": python,
                    "faster_whisper": True,
                    "ctranslate2_cuda": True,
                }
            ],
            "ffmpeg": None,
            "models": {"whisper_cpp": [], "openai_pt": []},
        }

    def test_nvidia_prefers_faster_whisper_cuda_then_cpu(self) -> None:
        candidates = transcribe_whisper.build_candidates(
            self.tools(),
            engine="auto",
            requested_device="auto",
            model="small",
            allow_slow=False,
            duration=240,
        )
        self.assertEqual(
            [(candidate["engine"], candidate["device"]) for candidate in candidates],
            [("faster-whisper", "cuda"), ("faster-whisper", "cpu")],
        )

    def test_long_audio_skips_original_whisper_cpu(self) -> None:
        tools = self.tools()
        tools["python_faster_whisper"] = None
        tools["python_whisper"] = str(Path("C:/slow/python.exe"))
        tools["python_backends"] = [{"python": tools["python_whisper"], "openai_whisper": True, "torch_cuda": False}]
        candidates = transcribe_whisper.build_candidates(
            tools,
            engine="auto",
            requested_device="auto",
            model="small",
            allow_slow=False,
            duration=240,
        )
        self.assertEqual(candidates, [])

    def test_apple_silicon_prefers_whisper_cpp_before_cpu(self) -> None:
        tools = self.tools()
        tools["hardware"] = {
            "nvidia_gpus": [],
            "apple_silicon": True,
            "amd_gpu": False,
        }
        tools["whisper_cpp"] = "/opt/whisper-cli"
        tools["ffmpeg"] = "/opt/ffmpeg"
        tools["models"]["whisper_cpp"] = ["/models/ggml-small.bin"]
        candidates = transcribe_whisper.build_candidates(
            tools,
            engine="auto",
            requested_device="auto",
            model="small",
            allow_slow=False,
            duration=240,
        )
        self.assertEqual(
            [(candidate["engine"], candidate["device"]) for candidate in candidates],
            [("whisper-cpp", "accelerated"), ("faster-whisper", "cpu")],
        )

    def test_allow_slow_enables_original_whisper_cpu(self) -> None:
        tools = self.tools()
        tools["python_faster_whisper"] = None
        tools["python_whisper"] = str(Path("C:/slow/python.exe"))
        tools["python_backends"] = [{"python": tools["python_whisper"], "openai_whisper": True, "torch_cuda": False}]
        candidates = transcribe_whisper.build_candidates(
            tools,
            engine="auto",
            requested_device="auto",
            model="small",
            allow_slow=True,
            duration=240,
        )
        self.assertEqual([(item["engine"], item["device"]) for item in candidates], [("openai-whisper", "cpu")])

    def test_cache_key_changes_with_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            audio = Path(temp_name) / "audio.wav"
            with wave.open(str(audio), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                output.writeframes(b"\0\0" * 160)
            fast = transcribe_whisper.audio_cache_key(audio, "small", "zh", "fast")
            accurate = transcribe_whisper.audio_cache_key(audio, "small", "zh", "accurate")
            self.assertNotEqual(fast, accurate)

    def test_cuda_library_error_is_persistent(self) -> None:
        self.assertTrue(
            transcribe_whisper.persistent_backend_failure(
                RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")
            )
        )
        self.assertFalse(transcribe_whisper.persistent_backend_failure(RuntimeError("temporary network failure")))

    def test_replacement_character_invalidates_cached_path(self) -> None:
        self.assertIsNone(tool_paths._cached("C:/Users/\ufffd/python.exe"))


if __name__ == "__main__":
    unittest.main()
