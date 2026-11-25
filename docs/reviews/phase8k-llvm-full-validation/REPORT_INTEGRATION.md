# 统一报告

`runtime_workflow.py report` 生成 `results.json`、`summary.md` 与 `index.html`。静态部分按维度和原始状态统计 Finding，按范围统计 Package 行，并保留静态源位置。编译链接记录包含工具身份、实际参数、退出码、产物摘要和证据。Runtime 章节保留每份原始回执及其 SHA256，包括退出码、stdout/stderr、Loader、版本、实际观察到的绑定和清理证据。HTML 对工具输出和报告字段作转义。

整体 formal compatibility 保持 UNKNOWN。静态范围标为 `SR_HEADLESS_STATIC`，设备回执使用自己的 `SR_HEADED_RUNTIME`。报告汇总读取原始静态 CSV，既有完整 Finding、Package 明细和 Evidence 继续通过原始报告引用复核。该路径避免将约 5 GiB 的静态 JSON 全文读入浏览器或 Python 内存。

独立阶段可用已有报告生成摘要，也可从两套镜像或静态 Manifest 启动现有静态分析。配置输出使用独立目录。见 [报告代码](../../../.agents/skills/tizen-image-compatibility/scripts/compat/runtime_summary.py) 和 [使用指南](USER_GUIDE.md)。

最终 `integrated-acceptance/` 三种格式已生成，JSON 与独立对账版本逐字节相同。独立检查了 31 份回执及其输出摘要、21 条编译链接记录、计数与 Profile。HTML 内容及链接经生成输出和合成转义测试核对；独立 Chromium 启动尝试超时，本轮不授予实际浏览器通过。
