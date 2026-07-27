# Agent Installation Guide

This repository contains a dual-platform Skill. Read this file to determine which version to install.

## How to Detect Your Platform

| If you are... | Install from | Install to |
| :--- | :--- | :--- |
| **Codex** (OpenAI Codex CLI) | `codex/ll-video-decomposer/` | Codex skills directory |
| **WorkBuddy** | `workbuddy/ll-video-decomposer/` | `~/.workbuddy/skills/ll-video-decomposer/` |

## Quick Install (Shell)

### Codex

```bash
git clone https://github.com/liuliu-66-create/ll-video-decomposer.git
cp -r ll-video-decomposer/codex/ll-video-decomposer <your-codex-skills-dir>/
```

### WorkBuddy

```bash
git clone https://github.com/liuliu-66-create/ll-video-decomposer.git
cp -r ll-video-decomposer/workbuddy/ll-video-decomposer ~/.workbuddy/skills/
```

## What's Different Between the Two Versions?

| Item | Codex | WorkBuddy |
| :--- | :--- | :--- |
| `SKILL.md` frontmatter | Original | Adds `agent_created: true` and English trigger keywords |
| `SKILL.md` body | Original | Adds "运行环境 (WorkBuddy)" section |
| `agents/openai.yaml` | Present (Codex trigger config) | Not needed |
| `scripts/` | 9 Python scripts | Same 9 scripts (identical) |
| `references/` | 7 markdown docs | Same 7 docs (identical) |

## Post-Install

1. Ensure `ffmpeg`, `ffprobe`, and `yt-dlp` are available on PATH (or discoverable).
2. For transcription, the skill will auto-detect the fastest available Whisper backend.
3. First run on a full video: the skill may ask to install `faster-whisper` into a project-local venv.
