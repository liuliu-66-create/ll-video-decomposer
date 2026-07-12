---
name: ll-video-decomposer
description: 专业分析单条视频，从逐字稿文本、本地视频或音频、视频链接生成完整的五层视频拆解报告。用户要求拆解视频、分析爆款视频、还原开头钩子和内容结构、提炼表达技巧、识别可复用方法与不可复制因素时使用。
---

# LL Video Decomposer

帮助视频创作者系统看懂一条视频的选题、开头、结构、表达和成功边界。

## 分析原则

- 围绕视频为什么有效、如何推进、哪些方法能复用、哪些因素不能复制展开分析。
- 使用用户主动提供的视频、逐字稿、平台信息和数据，不额外索取与分析无关的私人资料。
- 把结构规律与作者身份、粉丝基础、独家资源、热点时效和平台环境分开判断。
- 默认完成一份独立、完整的五层拆解报告。

## 处理输入

把三类输入最终统一成逐字稿：

1. 对逐字稿文本或文件，直接清理后分析。
2. 对本地视频或音频，先提取音频，再转写。
3. 对视频链接，先读取 [references/video-acquisition-workflow.md](references/video-acquisition-workflow.md)，按稳定性阶梯获得本地媒体，再转写。

处理媒体前先读取 [references/tool-discovery-workflow.md](references/tool-discovery-workflow.md)，运行 `scripts/discover_tools.py --project <当前项目目录>`。不能只查 PATH，也不能只查当前 Python。只有完整排查仍找不到可用工具或模型时，才能说明缺少什么、为什么需要、准备执行什么安装命令，并先取得用户同意。不要静默安装依赖。

## 执行流程

1. 识别输入类型，记录用户提供的平台、作者、数据和时长；没有的信息标为“未提供”，不要猜测。
2. 对媒体或链接输入先完成工具发现并写入项目配置；已有配置时优先验证并复用。
3. 链接输入按下载工作流获得本地视频。失败时走固定降级路径，不让用户反复换链接。
4. 本地媒体使用 `scripts/extract_audio.py` 生成 16 kHz 单声道 WAV。
5. 音频使用 `scripts/transcribe_whisper.py` 转写；中文内容优先传入 `--language zh`。
6. 文件型逐字稿使用 `scripts/clean_transcript.py` 清理时间戳。用户直接粘贴文本时，在分析中等价清理，不强制落盘。
7. 读取 [references/five-layer-report-template.md](references/five-layer-report-template.md)，生成完整报告。
8. 默认在视频所在目录保存一份 Markdown 报告，文件名使用 `<视频文件名>_report.md`；链接输入先以下载后的视频文件为基准确定目录和文件名。
9. 检查保存后的报告可以正常读取，不是复述逐字稿，五层结论都有原视频依据，最终提炼可以直接指导同类内容分析与创作。

## 输出规则

- 默认同时在对话中输出主要结论，并在视频所在目录保存完整 Markdown 报告。
- 只有用户明确要求“只在对话中展示”或“不要保存文件”时，才不写报告文件。
- 输入只有逐字稿且没有视频目录时，把报告保存在逐字稿文件所在目录；用户直接粘贴文本时，先询问保存位置，未指定则保存在当前工作目录。
- 默认不展示时间戳；只有用户要求或节奏判断必须引用时才保留。
- 原开头只引用分析所需的 3–5 句，不大段复制逐字稿。
- 数据缺失时，只从结构和内容价值判断，不虚构表现数据。
- “延伸选题”需要由原视频的受众问题和选题公式自然推导，不作无依据的效果承诺。
- 最终用普通语言给出三个最值得带走的方法，避免“资产沉淀”“入库”等内部表达。

## 脚本

- `scripts/discover_tools.py`：分层发现本地工具和模型，并写入项目配置。
- `scripts/tool_paths.py`：供其他脚本统一读取配置、查找工具和缓存路径。
- `scripts/download_video.py`：使用 yt-dlp 直接下载，或在 Chrome 已完全退出后读取登录状态下载。
- `scripts/extract_audio.py`：从本地媒体提取 WAV。
- `scripts/transcribe_whisper.py`：使用已有 Whisper 命令或 Python 包转写。
- `scripts/clean_transcript.py`：清理常见时间戳并整理空行。
