# 场景 7：报告保存

<!-- scenario: report-saving -->
<!-- route: single-video-report-template.md,multi-video-comparison-template.md -->
<!-- must: save-markdown-by-default -->
<!-- forbid: chat-only-without-request -->

## 用户输入

“拆解这个视频”，未说明报告保存方式。

## 已提供的证据

任一能够完成分析的单个或多个输入。

## 预期读取路线

按输入类型建立证据包，再根据输入数量读取对应报告模板。

## 必须出现的行为

默认在对话中给出主要结论，并在规则指定的位置保存完整 Markdown 报告。

## 禁止出现的行为

除非用户明确要求“只在对话中展示”或“不要保存文件”，不得只返回对话内容。

## 通过标准

报告文件存在、可读取且字段完整；用户明确拒绝保存时不创建文件。
