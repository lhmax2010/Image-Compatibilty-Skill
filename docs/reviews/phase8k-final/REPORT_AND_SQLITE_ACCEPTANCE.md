# 统一报告、Chromium 与 SQLite

新版统一报告在本地 `.local-backups/phase8k-final/historical-final/`，JSON、Markdown 和 HTML 一致呈现历史 headless 静态和 LLVM headed 真实观察。结果保留 903,377 条静态 Finding 的原始计数、11,490 INCOMPATIBLE、860,294 Linking UNKNOWN、719/736 个已安装 RPM。实机精确回执报告在 `exact-device/`，保留独立的观察身份。

## Chromium

实际 Chromium 156.0.8078.79 通过 WebDriver 打开三个页面并展开详情。历史报告页面耗时 0.223 秒，精确回执 0.035 秒，合成缺失与恶意文本页面 0.029 秒。三页均完整加载且 JavaScript 异常为 0，导航后资源请求为 0。HTML 只链接本地小型统一 JSON 和 Markdown，没有请求约 5 GiB 的历史原始报告。合成回执包含可执行标签和事件属性文本，DOM 将其保留为文字，未创建脚本或事件属性。历史报告中的 Scope、计划、Loader、Policy 失败和清理，以及精确页面的绑定记录均通过实机浏览检查。

首次启动诊断为 Chromium POSIX singleton socket 路径过长。最终启动在工作区私有 tmpfs 通过短路径别名完成。原始版本、事件、耗时和报错保存在本地 `chromium-validation.json` 和 `chromium-smoke.stderr`。

## SQLite

真实全量 SQLite **NOT VERIFIED**。Phase 8K 原建库任务仍在同一独立目录的 `original findings and assessments` 阶段。只读状态检查未发现新的成功 `run.json` 或 `validation.json`，独立审计尚无可验证索引。现行资源门槛和监控保留，未重复建库、覆盖任何结果或终止旁路任务。具体采样随交付检查记录。本地原构建结束且成功后，已有监控器会启动独立全量对账。

最后一次验收采样已运行约 4013 秒，累计 CPU 143.88 秒。派生输出分配 2,251,853,824 B，可用空间 273,941,848,064 B。进程 RSS 峰值 259,149,824 B。构建进程仍有内核磁盘 I/O 等待，未观察到容量门槛触发。查询性能随成功索引一起验收。
