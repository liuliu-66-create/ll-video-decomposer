# ll-video-decomposer

一个基于视频证据包的五层视频拆解 Skill。支持单视频深度拆解和多视频横向对比。**同时支持 Codex 和 WorkBuddy 双平台。**

输入完整视频时，Skill 会同时检查逐字稿、关键画面、镜头变化、字幕包装、人声和可以确认的 BGM，不再把视频只转换成逐字稿。输入只有音频或逐字稿时，会按实际证据降级，并明确标出无法判断的部分。

## 支持的平台

| 平台 | 触发方式 | 安装路径 |
| :--- | :--- | :--- |
| Codex | `$ll-video-decomposer` | Codex skills 目录 |
| WorkBuddy | 自然语言（"拆解这个视频" 等） | `~/.workbuddy/skills/ll-video-decomposer/` |

两个版本共享同一套 Python 脚本和参考文档，仅 SKILL.md 的 frontmatter 和触发机制不同。

## 安装

### 方式一：把仓库地址发给 Agent（推荐）

直接把仓库 URL 发给你的 Agent，它会自动识别平台、选择对应版本并安装：

```text
从 https://github.com/liuliu-66-create/ll-video-decomposer 安装这个 skill
```

Codex 和 WorkBuddy 都支持这种方式。Agent 会读取仓库根目录的 `install-manifest.json`，自动选择匹配当前平台的版本。

### 方式二：手动安装

#### Codex

将 `codex/ll-video-decomposer` 复制到 Codex skills 目录。

#### WorkBuddy

将 `workbuddy/ll-video-decomposer` 复制到 `~/.workbuddy/skills/` 目录：

```bash
git clone https://github.com/liuliu-66-create/ll-video-decomposer.git
cp -r ll-video-decomposer/workbuddy/ll-video-decomposer ~/.workbuddy/skills/
```

### 依赖安装

媒体处理按需使用 `yt-dlp`、`ffmpeg`、`ffprobe` 和 Whisper；Skill 不会静默安装依赖。

第一次处理完整视频前，先检查当前电脑：

```text
python scripts/setup_transcription.py --project <当前项目目录>
```

取得用户同意后，创建项目独立环境并安装轻量快速后端：

```text
python scripts/setup_transcription.py --project <当前项目目录> --install --model small
```

该环境位于当前项目的 `.video-decomposer-venv`，不会修改系统 Python。首次运行会下载依赖和模型。

只有用户明确接受数 GB 的一次性下载，并且希望启用 NVIDIA GPU 时，才使用：

```text
python scripts/setup_transcription.py --project <当前项目目录> --install --prefer-gpu --model small
```

GPU 安装或探针失败时会保留 CPU INT8 后端；确认缺少运行库的 GPU 路线会被缓存为不可用，后续自动跳过。

## 仓库结构

```text
ll-video-decomposer/
├── README.md                       <- 你正在看的这个
├── install-manifest.json           <- Agent 自动安装时读取的清单
├── AGENT_INSTALL.md                <- Agent 安装指南（备用，纯文本指令）
├── codex/
│   └── ll-video-decomposer/        <- Codex 完整版（含 agents/openai.yaml）
│       ├── SKILL.md
│       ├── agents/
│       │   └── openai.yaml
│       ├── scripts/                <- 9 个 Python 脚本
│       └── references/             <- 7 个参考文档
├── workbuddy/
│   └── ll-video-decomposer/        <- WorkBuddy 完整版
│       ├── SKILL.md                <- 含 agent_created: true
│       ├── scripts/                <- 9 个 Python 脚本（与 Codex 版相同）
│       └── references/             <- 7 个参考文档（与 Codex 版相同）
├── tests/
├── LICENSE
└── .gitignore
```

两个版本的 `scripts/` 和 `references/` 内容完全相同。区别仅在：
- **SKILL.md**：WorkBuddy 版多了 `agent_created: true` 字段和运行环境说明
- **agents/openai.yaml**：仅 Codex 版需要（`$skill` 触发配置），WorkBuddy 版不含此文件

## 支持的输入

- 本地视频：`.mp4`、`.mov`、`.mkv`、`.webm` 等
- 本地音频：`.wav`、`.mp3`、`.m4a` 等
- 逐字稿、字幕文件或直接粘贴的文本
- 一个或多个视频链接

## 五层输出

1. 整体定位：主题、受众、标签、痛点和分析价值
2. 爆款结构：黄金 3 秒、主体推进、结尾交付和转场
3. 内容价值与表达：信息、情绪、金句、人设和节奏
4. 视听语言：画面、镜头、字幕、包装、人声、BGM和视听协同
5. 创作策略：可套用框架、具体技巧、不可复制因素、风险和差异化

完整报告默认保存到视频所在目录。只有用户明确要求不保存时，才只在对话中展示。

## 自适应快速转写

Skill 会检查当前电脑并选择已经验证可用的最快路线：

1. NVIDIA 显卡可用时优先使用 `faster-whisper` GPU。
2. Apple Silicon 或 AMD 已配置 whisper.cpp 时使用对应加速。
3. 普通电脑使用 `faster-whisper` CPU INT8。
4. 原版 Whisper CPU 只处理短音频，长视频不会再默认进入十几分钟的慢路线。

默认使用 `small + fast`。高精度模型由用户主动选择，不把 `medium` 作为自动默认值。

转写结果按音频内容、模型、语言和模式缓存在当前项目的 `.video-decomposer-cache`。同一视频再次拆解时直接复用逐字稿和分段时间。

### 电脑要求

| 场景 | 最低建议 | 推荐配置 |
| :--- | :--- | :--- |
| 只有逐字稿 | 无额外媒体依赖 | 普通电脑 |
| 完整视频，CPU 转写 | 4 核 CPU、8GB 内存 | 6-8 核 CPU、16GB 内存 |
| NVIDIA 加速 | 4GB 显存可尝试 `small` | 8GB 显存 |
| Apple Silicon | 8GB 统一内存 | 16GB 统一内存 |

没有独立显卡也能完成拆解，只是转写速度取决于 CPU。完整视频还需要 FFmpeg 和 FFprobe；视频链接按需使用 yt-dlp。

## 视频链接的稳定顺序

1. 尝试直接下载。
2. 失败后，在 Chrome 登录并播放视频，再尝试已加载资源或缓存。
3. 需要读取 Chrome 登录状态时，完全退出 Chrome 后再试。
4. 仍然失败时，提供下载好的本地视频。

小红书可以先直接给链接。抖音建议先登录 Chrome 并播放一段。

## 使用示例

### Codex

```text
Use $ll-video-decomposer to analyze this video with content, visual, audio, and reusable strategy evidence.
```

```text
Use $ll-video-decomposer to compare these three videos and identify shared patterns, differences, and reusable methods.
```

### WorkBuddy

直接用自然语言描述需求即可，无需特定命令格式：

```text
拆解这个视频 https://www.xiaohongshu.com/explore/xxxxx
```

```text
帮我对比分析这三个视频的爆款结构
```

```text
分析这个视频的视听语言，提炼可复用的创作方法
```

## 维护与验证

提交版本前在仓库根目录运行：

```powershell
python -X utf8 scripts/validate_repository.py
python -X utf8 -m unittest discover -s tests -v
```

第一条命令检查两套安装内容、按需路由、本地链接、上下文预算、行为回归场景和不应进入安装包的运行产物。第二条命令运行转写路由与仓库结构测试。推送和提交合并请求时，GitHub 也会自动执行相同检查。

## License

MIT
