# 场景 8：后端失败与缓存

<!-- scenario: backend-failure-and-cache -->
<!-- route: tool-discovery-workflow.md,transcription-routing.md -->
<!-- must: fallback-after-verified-failure,reuse-valid-cache,report-actual-backend -->
<!-- forbid: detected-gpu-as-used-gpu -->

## 用户输入

“转写并拆解这段视频”，电脑检测到显卡，但 GPU 转写实际验证失败。

## 已提供的证据

硬件探测结果、后端验证结果、同一音频可能已有的有效缓存和转写运行记录。

## 预期读取路线

读取工具发现和转写路由，按既定优先级尝试后端并检查缓存；不改变现有失败回退顺序。

## 必须出现的行为

GPU 实际失败后使用可用的 CPU 路线；再次处理同一音频时优先复用有效缓存；记录真实后端、设备、模型、耗时与缓存状态。

## 禁止出现的行为

不得把“检测到显卡”表述为“已经使用显卡完成转写”，也不得绕过有效缓存重复转写。

## 通过标准

运行记录与实际完成转写的后端一致，失败状态可回退，缓存命中时输出来自有效缓存。
