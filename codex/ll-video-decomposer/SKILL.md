---
name: ll-video-decomposer
description: 专业分析一个或多个视频，从本地视频或音频、视频链接、逐字稿生成有证据的五层拆解报告。完整视频同时检查内容、开头、结构、画面镜头、字幕包装、人声、BGM和创作策略；多视频执行横向对比。用户要求拆解视频、分析爆款视频、比较多个视频、还原钩子与结构、分析视听语言、提炼可复用方法与不可复制因素时使用。
---

# LL Video Decomposer

帮助视频创作者看懂视频为什么有效、如何推进、视听元素承担什么作用，以及哪些方法可以复用。

## 核心原则

- 把完整视频整理成逐字稿、关键帧、音轨和基本信息组成的“视频证据包”，不得只凭逐字稿生成视听结论。
- 使用用户提供的视频、平台信息和数据；没有的信息标为“未提供”，不要猜测。
- 区分直接证据、合理推断和无法判断，尤其不要猜歌曲名、流量数据和幕后原因。
- 区分结构规律与作者身份、粉丝基础、独家资源、热点时效、视觉素材和平台环境。
- 即使不建议模仿，也完成当前证据支持的全部分析，不为凑结论而硬夸。

## 识别输入与模式

先判断输入数量和类型：

- 一条视频、音频或逐字稿：执行单视频深度拆解。
- 两条及以上：执行多视频横向对比。
- 视频链接：先获得本地媒体，再按视频处理。

开始处理前读取 [references/evidence-and-confidence-rules.md](references/evidence-and-confidence-rules.md)，明确当前输入可以支持哪些结论。

## 媒体处理

处理本地媒体或链接前：

1. 读取 [references/tool-discovery-workflow.md](references/tool-discovery-workflow.md)。
2. 读取 [references/transcription-routing.md](references/transcription-routing.md)。
3. 运行 `scripts/discover_tools.py --project <当前项目目录>`。
4. 优先验证并复用已有配置。不能只查 PATH 或当前 Python。
5. 完整排查仍缺少快速后端时，先运行 `scripts/setup_transcription.py --project <当前项目目录>` 诊断；说明下载体积、为什么需要和准备执行的安装命令，取得用户同意后再安装。

按输入类型处理：

### 完整视频

1. 保留原视频，不要把它降级成只有逐字稿的输入。
2. 运行 `scripts/sample_frames.py <视频> <证据目录>`，获得媒体信息、总览图、开头密集帧、正文代表帧、转场帧和结尾帧。
3. 读取 [references/audiovisual-analysis-guide.md](references/audiovisual-analysis-guide.md)，实际检查总览图与关键帧。
4. 使用 `scripts/extract_audio.py` 生成 16 kHz 单声道 WAV，再运行 `scripts/transcribe_whisper.py <WAV> <TXT> --project <当前项目目录> --model small --mode fast`；中文优先传入 `--language zh`。默认让脚本选择最快可用后端，不自动使用 `medium`，也不对长音频静默启用原版 Whisper CPU。
5. 结合视频、关键帧、音轨和逐字稿形成证据包。只有实际读取过的模态才能写入报告。

证据目录优先放在临时工作目录；只有用户要求保留核对材料时，才与报告一起长期保存。

### 只有音频

直接转写并分析内容、人声、节奏和可以确认的 BGM。没有画面时，明确不分析镜头、字幕和视觉包装。

### 逐字稿

文件型逐字稿使用 `scripts/clean_transcript.py` 清理时间戳。用户直接粘贴文本时，在分析中等价清理。只分析内容、结构与表达，不补写视听结论。

### 视频链接

读取 [references/video-acquisition-workflow.md](references/video-acquisition-workflow.md)，按稳定性阶梯获得本地视频。失败时走固定降级路径，不要求用户反复更换链接。

## 生成报告

### 单视频

读取 [references/single-video-report-template.md](references/single-video-report-template.md)，用两列 Markdown 表格完成五层报告：

1. 整体定位
2. 爆款结构
3. 内容价值与表达
4. 视听语言
5. 创作策略

### 多视频

读取 [references/multi-video-comparison-template.md](references/multi-video-comparison-template.md)。对每条视频使用相同证据标准，再总结共同模式、核心差异、效果边界和三条可执行启示。

## 保存与输出

- 默认在对话中展示主要结论，并保存完整 Markdown 报告。
- 单个本地视频保存为视频同目录下的 `<视频文件名>_report.md`。
- 链接输入以下载后的视频文件确定目录和文件名。
- 逐字稿文件保存到逐字稿所在目录；直接粘贴文本且未指定位置时保存到当前工作目录。
- 多个文件位于同一目录时保存为该目录下的 `video-comparison-report.md`；来源分散时保存到当前工作目录。
- 只有用户明确说“只在对话中展示”或“不要保存文件”时，才不写报告。
- 默认不展示全部时间戳；结构、镜头或节奏结论需要证据时保留关键时间点。
- 原开头只引用分析所需的 3–5 句，不大段复制逐字稿。

## 交付检查

完成前确认：

- 报告能正常读取，五层字段完整。
- 完整视频确实检查过关键帧和音轨，没有只分析逐字稿。
- 转写记录了实际使用的后端、设备、模型、耗时和是否命中缓存；没有把“检测到显卡”误报为“显卡已加速”。
- 视听结论能对应到具体时间点或画面。
- 输入缺少某种模态时，相关字段明确写出限制。
- BGM未确认时没有猜歌曲名和艺术家。
- 报告解释了为什么有效、如何复用和模仿风险，不是逐字稿复述。
- 多视频报告使用同一尺度比较，没有把表面共性直接包装成爆款法则。

## 脚本

- `scripts/discover_tools.py`：分层发现本地工具和模型，并写入项目配置。
- `scripts/tool_paths.py`：统一读取配置、查找工具和缓存路径。
- `scripts/setup_transcription.py`：诊断电脑并在用户同意后创建独立快速转写环境。
- `scripts/faster_whisper_runner.py`：在选定设备上运行 faster-whisper 并输出带时间段的证据。
- `scripts/download_video.py`：使用 yt-dlp 直接下载，或在 Chrome 完全退出后读取登录状态下载。
- `scripts/sample_frames.py`：读取媒体信息，抽取开头、正文、转场和结尾关键帧，生成总览图与证据清单。
- `scripts/extract_audio.py`：从本地媒体提取 WAV。
- `scripts/transcribe_whisper.py`：按硬件和已验证后端自动路由、超时回退并缓存转写。
- `scripts/clean_transcript.py`：清理常见时间戳并整理空行。
