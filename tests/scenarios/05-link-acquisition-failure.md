# 场景 5：视频链接获取失败

<!-- scenario: link-acquisition-failure -->
<!-- route: evidence-and-confidence-rules.md,video-acquisition-workflow.md -->
<!-- must: fixed-acquisition-fallback -->
<!-- forbid: infinite-retry,repeat-same-link-request -->

## 用户输入

“拆解这个平台视频链接”，但直接下载失败。

## 已提供的证据

只有链接；可能存在已播放资源、登录状态或用户可提供的本地文件。

## 预期读取路线

先读取证据规则和视频获取流程；依次尝试直接下载、已播放资源或登录状态，最后请求本地视频或逐字稿；成功后进入相应输入路线。

## 必须出现的行为

按固定顺序降级，并在每一阶段说明当前缺少的证据。

## 禁止出现的行为

不得无限重试，不得反复要求用户更换或重发同一个链接。

## 通过标准

获取成功后转入本地视频路线；全部失败后只请求一种可用的本地替代输入。
