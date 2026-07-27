# 自适应转写路由

## 目标

针对当前电脑选择已经可用的最快后端，同时控制首次安装成本。不得因为发现了模型就默认运行缓慢的原版 Whisper CPU。

## 默认调用

```text
python scripts/transcribe_whisper.py <音频 WAV> <逐字稿 TXT> --project <当前项目目录> --language zh --model small --mode fast
```

默认使用 `small + fast`。`medium`、`turbo` 或 `accurate` 只在用户明确要求高精度，或者快速模式结果不足时使用。

## 自动优先级

1. NVIDIA 且 CUDA 后端通过验证：`faster-whisper` GPU `int8_float16`。
2. OpenAI Whisper 已能实际调用 CUDA：GPU FP16。
3. Apple Silicon 或 AMD 且已有匹配模型的 whisper.cpp：Metal、Vulkan 或 ROCm 路线。
4. `faster-whisper` CPU INT8。
5. 已有匹配模型的 whisper.cpp CPU。
6. 原版 Whisper CPU：只处理 60 秒以内音频，或用户明确允许 `--allow-slow` 时使用。

脚本会记录缺少 CUDA 运行库等确定性失败。后续视频自动跳过已失败后端；安装环境发生变化后传入 `--retry-failed-backends` 重新验证。

## 首次准备

先运行诊断：

```text
python scripts/setup_transcription.py --project <当前项目目录>
```

没有快速后端时，说明将创建独立环境、下载依赖和模型，并取得用户同意后运行：

```text
python scripts/setup_transcription.py --project <当前项目目录> --install --model small
```

该命令创建项目内的 `.video-decomposer-venv`，安装 `faster-whisper`，预下载模型，并实际验证 CPU INT8。不要安装到用户的系统 Python。

只有用户明确接受数 GB 的一次性下载，并且 NVIDIA 显卡与驱动适合时，才运行：

```text
python scripts/setup_transcription.py --project <当前项目目录> --install --prefer-gpu --model small
```

GPU 安装失败时保留已经可用的 CPU INT8，不循环重装大型依赖。

## 缓存和超时

- 转写缓存位于 `<项目>/.video-decomposer-cache/transcripts`，按音频内容、模型、语言和模式区分。
- 同一音频再次拆解时直接复用文本和分段时间，不重复推理。
- 默认每个后端最多运行 240 秒；超时或失败后尝试下一条已准备路线。
- 第一次下载模型应通过安装脚本完成，不要把模型下载时间混入日常转写超时。
- 缓存只保存转写证据，不改变最终报告保存规则。

## 配置边界

- 无独立显卡：使用 CPU INT8，不阻断完整视频拆解。
- NVIDIA：只有实际转写探针成功才标记 GPU 可用，不能只凭 `nvidia-smi` 下结论。
- Apple Silicon：优先使用已有 Metal 版 whisper.cpp；没有时使用 CPU INT8。
- AMD：优先使用已经准备好的 Vulkan 或 ROCm 版 whisper.cpp；没有时使用 CPU INT8。
- 只有逐字稿：跳过全部媒体转写依赖。
- 所有本地后端都不可用：说明缺少什么，取得同意后安装；用户不愿安装时改为接收逐字稿，不无限等待。
