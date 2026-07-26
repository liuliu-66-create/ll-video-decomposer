# 本地工具发现与缓存

在提示用户安装之前，严格按以下顺序检查：

1. 读取当前项目或父目录中的 `.video-decomposer-tools.json`。
2. 检查系统 PATH 中的 `ffmpeg`、`ffprobe`、`whisper`、`yt-dlp`、`whisper-cli`。
3. 检查 Windows 常见位置：Python `Scripts`、用户 `tools`、`C:\tools`、FFmpeg、Program Files、conda 和 miniconda。
4. 检查项目独立环境和多个 Python 环境能否 `import faster_whisper` 或 `import whisper`；不能只检查当前 Python。
5. 检查 FFmpeg 是否具备 Whisper 滤镜，并确认是否存在可用的 `ggml-*.bin` 模型。
6. 检查操作系统、CPU、内存、NVIDIA 显卡、Apple Silicon 和可识别的 AMD 显卡。
7. 只在用户目录、当前项目和常见工具目录进行有限扫描，不扫描整个磁盘。
8. 把成功发现的路径、后端能力、硬件和模型清单写入 `.video-decomposer-tools.json`，以后优先复用。

如果配置中的工具路径存在，但当前受限环境返回“拒绝访问”，应把它判断为“工具已发现，但执行需要权限”，不能重新表述为“没有安装”。取得必要权限后直接复用配置路径，不要重新扫描。

运行：

```text
python scripts/discover_tools.py --project <当前项目目录>
```

安装或切换环境后运行 `--refresh`，重新探测 Python 后端：

```text
python scripts/discover_tools.py --project <当前项目目录> --refresh
```

不要只因为 `Get-Command whisper` 没有结果就说“没有 Whisper”。应说明当前检查进度，并继续完成剩余层级。

发现硬件不等于后端已经可用。NVIDIA 显卡必须通过实际 CUDA 探针；缺少 `cublas`、`cuDNN` 或驱动不兼容时，记录失败并改用 CPU INT8。完整路由和安装边界见 [transcription-routing.md](transcription-routing.md)。
