---
name: ll-video-decomposer
description: 专业分析一个或多个视频，从本地视频或音频、视频链接、逐字稿生成有证据的五层拆解报告。完整视频同时检查内容、开头、结构、画面镜头、字幕包装、人声、BGM和创作策略；多视频执行横向对比。This skill should be used when the user asks to decompose/analyze videos, break down viral/爆款 videos, compare multiple videos, reverse-engineer hooks and structure, analyze audiovisual language, or extract reusable methods and non-replicable factors. 触发词：拆解视频、分析爆款视频、比较多个视频、还原钩子与结构、分析视听语言、提炼可复用方法与不可复制因素。
---

# LL Video Decomposer

帮助视频创作者看懂视频为什么有效、如何推进、视听元素承担什么作用，以及哪些方法可以复用。

## 运行环境（WorkBuddy）

使用 WorkBuddy 管理的 Python 绝对路径执行 Skill 目录下的脚本，不使用裸 `python`，也不额外设置 `PYTHONPATH`。脚本会发现 ffmpeg、ffprobe、yt-dlp 和 Whisper 后端；需要安装时在当前项目创建独立环境，不污染系统 Python。

## 核心原则

- 把完整视频整理成逐字稿、关键帧、音轨和基本信息组成的“视频证据包”，不得只凭逐字稿生成视听结论。
- 使用用户提供的视频、平台信息和数据；没有的信息标为“未提供”，不要猜测。
- 区分直接证据、合理推断和无法判断，尤其不要猜歌曲名、流量数据和幕后原因。
- 区分结构规律与作者身份、粉丝基础、独家资源、热点时效、视觉素材和平台环境。
- 即使不建议模仿，也完成当前证据支持的全部分析，不为凑结论而硬夸。

## 按需路由

先读取证据规则，再合并执行“输入类型”行与“输入数量”行；证据包完成后才读取报告模板。

| 当前输入或任务 | 必读资料 | 处理路线 |
| --- | --- | --- |
| 直接粘贴逐字稿 | [证据规则](references/evidence-and-confidence-rules.md) | 不运行媒体脚本；只分析内容、结构与表达，不分析画面、人声听感或 BGM |
| 逐字稿文件 | [证据规则](references/evidence-and-confidence-rules.md) | 按需运行 `scripts/clean_transcript.py`；不加载媒体工具或视听指南 |
| 本地音频 | [证据规则](references/evidence-and-confidence-rules.md)、[工具发现](references/tool-discovery-workflow.md)、[转写路由](references/transcription-routing.md) | 转写后只分析内容、人声、节奏与可确认的 BGM |
| 本地完整视频 | [证据规则](references/evidence-and-confidence-rules.md)、[工具发现](references/tool-discovery-workflow.md)、[转写路由](references/transcription-routing.md)、[视听指南](references/audiovisual-analysis-guide.md) | 抽帧、提取音频、转写并形成完整证据包 |
| 视频链接 | [证据规则](references/evidence-and-confidence-rules.md)、[视频获取](references/video-acquisition-workflow.md) | 按固定顺序获取媒体，成功后进入“本地完整视频”路线，失败后固定降级 |
| 单个输入 | [单视频模板](references/single-video-report-template.md) | 生成五层单视频报告 |
| 两个及以上输入 | [多视频模板](references/multi-video-comparison-template.md) | 对每条输入使用同一证据尺度后横向比较 |

- 不预先读取全部七份参考资料；只读取路由命中的资料。
- 脚本可直接执行时，不为执行而把整份脚本读入上下文。
- 链接输入只比本地完整视频多读取视频获取流程。

## 媒体执行

- 本地媒体先运行 `scripts/discover_tools.py --project <当前项目目录>`，验证并复用已有配置，不能只查 PATH 或当前 Python。
- 完整视频保留原文件：运行 `scripts/sample_frames.py <视频> <证据目录>` 并实际检查总览图与关键帧；运行 `scripts/extract_audio.py` 生成 16 kHz 单声道 WAV，再运行 `scripts/transcribe_whisper.py <WAV> <TXT> --project <当前项目目录> --model small --mode fast`，中文优先加 `--language zh`。
- 只有音频时直接转写；没有画面就明确不分析镜头、字幕和视觉包装。
- 逐字稿文件按需清理时间戳；直接粘贴文本时等价清理，不补写视听结论。
- 链接按视频获取流程依次尝试直接下载、已播放资源或登录状态、本地视频或逐字稿，不无限重试。
- 完整排查后仍缺快速后端时，先用 `scripts/setup_transcription.py --project <当前项目目录>` 诊断；说明下载体积、用途与安装命令，取得用户同意后才安装。
- 保持现有后端优先级、缓存和失败回退；不自动使用 `medium`，不对长音频静默启用原版 Whisper CPU。
- 证据目录优先使用临时目录；只有用户要求保留时才长期保存。

## 报告与保存

- 单视频用两列表格完成：整体定位、爆款结构、内容价值与表达、视听语言、创作策略。
- 多视频先按各自输入类型建立证据包，再用同一尺度总结共同模式、核心差异、效果边界和三条可执行启示。
- 默认在对话中展示主要结论，并保存完整 Markdown 报告。
- 单个本地视频保存为同目录 `<视频文件名>_report.md`；链接按下载后文件确定；逐字稿文件保存到其目录；直接粘贴文本保存到当前目录。
- 同目录多文件保存为 `video-comparison-report.md`；来源分散时保存到当前目录。
- 只有用户明确要求“只在对话中展示”或“不要保存文件”时才不写报告。
- 默认不展示全部时间戳；只保留支撑结构、镜头或节奏结论的关键时间点；原开头只引用必要的 3–5 句。

## 交付检查

- 报告可读取且五层完整；输入缺失的模态明确标注限制。
- 完整视频实际检查过关键帧和音轨，视听结论可对应时间点或画面。
- 转写记录真实后端、设备、模型、耗时和缓存状态，不把检测到显卡误报为显卡已加速。
- BGM 未确认时不猜歌曲名和艺术家。
- 报告解释为什么有效、如何复用和模仿风险，不复述逐字稿。
- 多视频使用同一尺度，不把表面共性包装成爆款法则。
