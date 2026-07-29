from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "ll-video-decomposer"
PLATFORMS = {
    "codex": ROOT / "codex" / SKILL_NAME,
    "workbuddy": ROOT / "workbuddy" / SKILL_NAME,
}
REQUIRED_SCRIPTS = {
    "clean_transcript.py",
    "discover_tools.py",
    "download_video.py",
    "extract_audio.py",
    "faster_whisper_runner.py",
    "sample_frames.py",
    "setup_transcription.py",
    "tool_paths.py",
    "transcribe_whisper.py",
}
REQUIRED_REFERENCES = {
    "audiovisual-analysis-guide.md",
    "evidence-and-confidence-rules.md",
    "multi-video-comparison-template.md",
    "single-video-report-template.md",
    "tool-discovery-workflow.md",
    "transcription-routing.md",
    "video-acquisition-workflow.md",
}
ROUTE_LABELS = {
    "直接粘贴逐字稿",
    "逐字稿文件",
    "本地音频",
    "本地完整视频",
    "视频链接",
    "单个输入",
    "两个及以上输入",
}
SCENARIO_HEADINGS = {
    "## 用户输入",
    "## 已提供的证据",
    "## 预期读取路线",
    "## 必须出现的行为",
    "## 禁止出现的行为",
    "## 通过标准",
}
EXPECTED_SCENARIOS = {
    "01-transcript-only.md": {
        "scenario": {"transcript-only"},
        "must": {"analyze-content", "state-visual-limit"},
        "forbid": {"invent-visuals", "invent-voice", "invent-bgm"},
    },
    "02-audio-only.md": {
        "scenario": {"audio-only"},
        "must": {"analyze-audio", "state-visual-limit"},
        "forbid": {"invent-visuals"},
    },
    "03-complete-video.md": {
        "scenario": {"complete-video"},
        "must": {"inspect-frames", "inspect-audio", "build-evidence-pack"},
        "forbid": {"transcript-only-audiovisual-analysis"},
    },
    "04-bgm-unknown.md": {
        "scenario": {"bgm-unknown"},
        "must": {"describe-verifiable-audio"},
        "forbid": {"guess-song", "guess-artist"},
    },
    "05-link-acquisition-failure.md": {
        "scenario": {"link-acquisition-failure"},
        "must": {"fixed-acquisition-fallback"},
        "forbid": {"infinite-retry", "repeat-same-link-request"},
    },
    "06-multi-video-comparison.md": {
        "scenario": {"multi-video-comparison"},
        "must": {"same-evidence-standard"},
        "forbid": {"surface-pattern-as-law"},
    },
    "07-report-saving.md": {
        "scenario": {"report-saving"},
        "must": {"save-markdown-by-default"},
        "forbid": {"chat-only-without-request"},
    },
    "08-backend-failure-and-cache.md": {
        "scenario": {"backend-failure-and-cache"},
        "must": {"fallback-after-verified-failure", "reuse-valid-cache", "report-actual-backend"},
        "forbid": {"detected-gpu-as-used-gpu"},
    },
}
PROHIBITED_DIR_NAMES = {
    ".video-decomposer-cache",
    ".video-decomposer-venv",
    "__pycache__",
}
PROHIBITED_SUFFIXES = {
    ".avi",
    ".bin",
    ".ggml",
    ".gguf",
    ".m4a",
    ".mkv",
    ".model",
    ".mov",
    ".mp3",
    ".mp4",
    ".onnx",
    ".pt",
    ".pyc",
    ".safetensors",
    ".srt",
    ".txt",
    ".wav",
    ".webm",
}


def error(scope: str, message: str) -> str:
    return f"[{scope}] {message}"


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def parse_frontmatter(path: Path) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    if not path.is_file():
        return {}, [error("metadata", f"缺少 {relative(path)}")]
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, [error("metadata", f"{relative(path)} 缺少 YAML 起始分隔线")]
    try:
        closing = lines.index("---", 1)
    except ValueError:
        return {}, [error("metadata", f"{relative(path)} 缺少 YAML 结束分隔线")]

    metadata: dict[str, str] = {}
    for line in lines[1:closing]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            errors.append(error("metadata", f"{relative(path)} 的元数据行无效：{line}"))
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata, errors


def estimate_tokens(text: str) -> int:
    cjk = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text))
    non_cjk = len(re.sub(r"[\s\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", "", text))
    return cjk + math.ceil(non_cjk / 4)


def validate_skill_metadata_and_budget() -> list[str]:
    errors: list[str] = []
    allowed_metadata = {
        "codex": {"name", "description"},
        "workbuddy": {"name", "description"},
    }
    for platform, skill_dir in PLATFORMS.items():
        skill_path = skill_dir / "SKILL.md"
        metadata, metadata_errors = parse_frontmatter(skill_path)
        errors.extend(metadata_errors)
        if metadata.get("name") != SKILL_NAME:
            errors.append(
                error("metadata", f"{relative(skill_path)} 的 name 必须是 {SKILL_NAME}")
            )
        if not metadata.get("description"):
            errors.append(error("metadata", f"{relative(skill_path)} 缺少 description"))
        unknown = set(metadata) - allowed_metadata[platform]
        if unknown:
            errors.append(
                error(
                    "metadata",
                    f"{relative(skill_path)} 包含不支持的字段：{', '.join(sorted(unknown))}",
                )
            )
        if skill_dir.name != metadata.get("name"):
            errors.append(
                error("metadata", f"{relative(skill_dir)} 与 Skill 名称不一致")
            )
        if not skill_path.is_file():
            continue
        text = skill_path.read_text(encoding="utf-8")
        line_count = len(text.splitlines())
        char_count = len(text)
        token_count = estimate_tokens(text)
        if line_count > 150:
            errors.append(error("budget", f"{relative(skill_path)} 为 {line_count} 行，超过 150 行"))
        if char_count > 5000:
            errors.append(error("budget", f"{relative(skill_path)} 为 {char_count} 字符，超过 5000 字符"))
        if token_count > 4500:
            errors.append(
                error("budget", f"{relative(skill_path)} 估算为 {token_count} Token，超过约 4500 Token")
            )
    return errors


def referenced_local_paths(skill_path: Path) -> set[Path]:
    text = skill_path.read_text(encoding="utf-8")
    paths: set[Path] = set()
    for target in re.findall(r"\]\(([^)]+)\)", text):
        clean = target.split("#", 1)[0].strip()
        if clean and "://" not in clean and not clean.startswith("#"):
            paths.add(skill_path.parent / clean)
    for target in re.findall(r"`((?:scripts|references|agents)/[^`\s|)]+)`", text):
        paths.add(skill_path.parent / target)
    return paths


def route_section(text: str) -> str | None:
    match = re.search(r"(?ms)^## 按需路由\s*$\n(.*?)(?=^## |\Z)", text)
    if not match:
        return None
    return "\n".join(line.rstrip() for line in match.group(1).strip().splitlines())


def validate_links_and_routes() -> list[str]:
    errors: list[str] = []
    route_sections: dict[str, str] = {}
    for platform, skill_dir in PLATFORMS.items():
        skill_path = skill_dir / "SKILL.md"
        if not skill_path.is_file():
            continue
        for target in sorted(referenced_local_paths(skill_path)):
            if not target.exists():
                try:
                    display = relative(target)
                except ValueError:
                    display = str(target)
                errors.append(
                    error("link", f"{relative(skill_path)} 引用的路径不存在：{display}")
                )
        text = skill_path.read_text(encoding="utf-8")
        section = route_section(text)
        if section is None:
            errors.append(error("route", f"{relative(skill_path)} 缺少“按需路由”章节"))
            continue
        route_sections[platform] = section
        for label in sorted(ROUTE_LABELS):
            if label not in section:
                errors.append(
                    error("route", f"{relative(skill_path)} 的路由表缺少：{label}")
                )
    if len(route_sections) == len(PLATFORMS):
        if route_sections["codex"] != route_sections["workbuddy"]:
            errors.append(error("route", "Codex 与 WorkBuddy 的“按需路由”章节不一致"))
    return errors


def validate_manifest_and_contents() -> list[str]:
    errors: list[str] = []
    manifest_path = ROOT / "install-manifest.json"
    if not manifest_path.is_file():
        return [error("manifest", "缺少 install-manifest.json")]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [error("manifest", f"install-manifest.json 无法读取：{exc}")]
    if manifest.get("name") != SKILL_NAME:
        errors.append(error("manifest", f"name 必须是 {SKILL_NAME}"))
    platform_entries = manifest.get("platforms")
    if not isinstance(platform_entries, dict):
        return errors + [error("manifest", "platforms 必须是对象")]
    for platform, expected_dir in PLATFORMS.items():
        entry = platform_entries.get(platform)
        if not isinstance(entry, dict):
            errors.append(error("manifest", f"缺少 platforms.{platform}"))
            continue
        declared = ROOT / str(entry.get("path", ""))
        if declared.resolve() != expected_dir.resolve():
            errors.append(
                error(
                    "manifest",
                    f"platforms.{platform}.path 应为 {relative(expected_dir)}",
                )
            )
        if not declared.is_dir():
            errors.append(error("manifest", f"声明目录不存在：{relative(declared)}"))
        trigger = entry.get("trigger")
        if not isinstance(trigger, str) or not trigger.strip():
            errors.append(error("manifest", f"platforms.{platform}.trigger 不能为空"))
        if platform == "codex" and trigger != f"${SKILL_NAME}":
            errors.append(
                error("manifest", f"Codex trigger 必须是 ${SKILL_NAME}")
            )

    for platform, skill_dir in PLATFORMS.items():
        scripts_dir = skill_dir / "scripts"
        references_dir = skill_dir / "references"
        actual_scripts = {path.name for path in scripts_dir.glob("*.py")} if scripts_dir.is_dir() else set()
        actual_references = {path.name for path in references_dir.glob("*.md")} if references_dir.is_dir() else set()
        if not (skill_dir / "SKILL.md").is_file():
            errors.append(error("structure", f"{relative(skill_dir)} 缺少 SKILL.md"))
        if actual_scripts != REQUIRED_SCRIPTS:
            errors.append(
                error(
                    "structure",
                    f"{platform} 脚本清单不符；缺少 {sorted(REQUIRED_SCRIPTS - actual_scripts)}，多出 {sorted(actual_scripts - REQUIRED_SCRIPTS)}",
                )
            )
        if actual_references != REQUIRED_REFERENCES:
            errors.append(
                error(
                    "structure",
                    f"{platform} 参考资料清单不符；缺少 {sorted(REQUIRED_REFERENCES - actual_references)}，多出 {sorted(actual_references - REQUIRED_REFERENCES)}",
                )
            )
    if not (PLATFORMS["codex"] / "agents" / "openai.yaml").is_file():
        errors.append(error("structure", "Codex 版本缺少 agents/openai.yaml"))
    return errors


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_shared_files() -> list[str]:
    errors: list[str] = []
    for folder in ("scripts", "references"):
        codex_dir = PLATFORMS["codex"] / folder
        workbuddy_dir = PLATFORMS["workbuddy"] / folder
        codex_files = {
            path.relative_to(codex_dir).as_posix(): path
            for path in codex_dir.rglob("*")
            if path.is_file()
        }
        workbuddy_files = {
            path.relative_to(workbuddy_dir).as_posix(): path
            for path in workbuddy_dir.rglob("*")
            if path.is_file()
        }
        missing_workbuddy = sorted(set(codex_files) - set(workbuddy_files))
        missing_codex = sorted(set(workbuddy_files) - set(codex_files))
        different = sorted(
            name
            for name in set(codex_files) & set(workbuddy_files)
            if file_digest(codex_files[name]) != file_digest(workbuddy_files[name])
        )
        if missing_workbuddy:
            errors.append(
                error("sync", f"WorkBuddy 的 {folder}/ 缺少：{', '.join(missing_workbuddy)}")
            )
        if missing_codex:
            errors.append(
                error("sync", f"Codex 的 {folder}/ 缺少：{', '.join(missing_codex)}")
            )
        if different:
            errors.append(
                error("sync", f"两个平台的 {folder}/ 内容不同：{', '.join(different)}")
            )
    return errors


def validate_install_artifacts() -> list[str]:
    errors: list[str] = []
    for platform, skill_dir in PLATFORMS.items():
        if not skill_dir.is_dir():
            continue
        for path in skill_dir.rglob("*"):
            if path.is_dir() and path.name.lower() in PROHIBITED_DIR_NAMES:
                errors.append(error("artifact", f"{platform} 安装内容包含目录：{relative(path)}"))
            if path.is_file() and path.suffix.lower() in PROHIBITED_SUFFIXES:
                errors.append(error("artifact", f"{platform} 安装内容包含文件：{relative(path)}"))
    return errors


def parse_scenario_markers(text: str) -> dict[str, set[str]]:
    markers: dict[str, set[str]] = {}
    for key, value in re.findall(
        r"<!--\s*(scenario|route|must|forbid):\s*([^>]+?)\s*-->",
        text,
        flags=re.IGNORECASE,
    ):
        markers.setdefault(key.lower(), set()).update(
            item.strip() for item in value.split(",") if item.strip()
        )
    return markers


def validate_scenarios() -> list[str]:
    errors: list[str] = []
    scenario_dir = ROOT / "tests" / "scenarios"
    if not scenario_dir.is_dir():
        return [error("scenario", "缺少 tests/scenarios/")]
    actual = {path.name for path in scenario_dir.glob("*.md")}
    expected = set(EXPECTED_SCENARIOS)
    if actual != expected:
        errors.append(
            error(
                "scenario",
                f"场景文件清单不符；缺少 {sorted(expected - actual)}，多出 {sorted(actual - expected)}",
            )
        )
    for filename, required_markers in EXPECTED_SCENARIOS.items():
        path = scenario_dir / filename
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for heading in sorted(SCENARIO_HEADINGS):
            if heading not in text:
                errors.append(error("scenario", f"{filename} 缺少章节：{heading}"))
        markers = parse_scenario_markers(text)
        if not markers.get("route"):
            errors.append(error("scenario", f"{filename} 缺少 route 标记"))
        for marker_type, expected_values in required_markers.items():
            missing = expected_values - markers.get(marker_type, set())
            if missing:
                errors.append(
                    error(
                        "scenario",
                        f"{filename} 的 {marker_type} 标记缺少：{', '.join(sorted(missing))}",
                    )
                )
    return errors


def collect_errors() -> list[str]:
    checks = (
        validate_skill_metadata_and_budget,
        validate_links_and_routes,
        validate_manifest_and_contents,
        validate_shared_files,
        validate_install_artifacts,
        validate_scenarios,
    )
    errors: list[str] = []
    for check in checks:
        errors.extend(check())
    return errors


def main() -> int:
    errors = collect_errors()
    if errors:
        print(f"Repository validation failed with {len(errors)} issue(s):")
        for item in errors:
            print(f"- {item}")
        return 1
    print(
        "Repository validation passed: metadata, budgets, routes, links, "
        "install contents, platform sync, artifacts, and 8 behavior scenarios are valid."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
