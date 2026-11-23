# Phase 8A 独立评审交付

**验收结论：CONDITIONAL PASS。** SR VD → SR LLVM 的定向修复、全量自动化回归、真实静态报告对账通过。真实全量 SQLite 索引仍受存储限制。真实镜像的结果为 `INCOMPATIBLE`，验证覆盖为 `PARTIAL`。

对比使用 Tizen Unified 的 `tizen-headless-armv7l` Profile，VD 基线为 `tizen-unified-dev_20261119.012448`，LLVM 候选为 `tizen-unified-toolchain_20261120.082536`。使用同一对已核对的 Rootfs TAR，覆盖 `/` 和 `/opt`。 [来源、归档与分析输入 SHA256](SR_EVIDENCE_EXCERPTS.json)

| 项目 | 结果 | 评审入口 |
|---|---|---|
| GNU 版本节点 | `TC-1dc09eab2397194b` 消失。共移除 156 条标记误报，逐项确认两侧仍有对应版本定义。真实版本节点、函数和普通 ABS 导出删除用例通过。 | [版本修复规则和反例](GNU_VERSION_REVIEW.md) |
| 关键采集失败 | 相同故障负对照从退出 0 变为 3。兼容性保持 UNKNOWN，执行状态为 FAILED。 | [门禁、退出码与复现](COLLECTION_GATE_REVIEW.md) |
| Linking | 合成完整证据闭包可验证通过或缺失。真实 SR 仍有 860,300 条 UNKNOWN，完整覆盖为 0%。 | [原因分组与四个样本](LINKING_COVERAGE_REVIEW.md) |
| 输入范围 | 已恢复路径和内容可盘点，UID/GID/mode 与设备节点声明保留为归档元数据。xattr、ACL、Smack、file capabilities、硬链接关系和启动 ramdisk 明确标为未恢复。 | [输入证据代码](../../../.agents/skills/tizen-image-compatibility/scripts/compat/images.py#L63) · [测试与证据](REGRESSION_SUMMARY.md) |
| 数据对账 | 903,383 条新 Finding 在 JSON、CSV 的 ID、状态、严重度、维度上逐条一致，HTML 预览、719 条包评估和 4,086 个不同 Evidence 引用通过检查。VD/LLVM 的 RPM 数量分别为 719/736。归档及分析输入 SHA256 与历史一致。 | [真实数据对账](SR_BEFORE_AFTER.md) |
| 执行边界 | 真实静态运行约 191 秒。全量增强索引预检估计需要 12.29 GiB，主机当时约 2.26 GiB 可用。合成 SQLite、CSV 和 Evidence 回归通过。 | [资源与未验证项](KNOWN_LIMITATIONS.md) |

代码审查比较 `3336cdde5bb5c51daa0a6b5da36ca412f5279d9c` 与 [SOURCE_CHANGES.json](SOURCE_CHANGES.json) 中的 `code_commit`。19 个文件覆盖生产代码、配置、用户说明及 9 项回归，验收证据单独提交。 [生产代码与测试定位](REGRESSION_SUMMARY.md)

证据 JSON 只收录来自现场记录的选定字段、工具输出片段、虚拟镜像路径和 SHA256。公开发布目录用于获得同一输入。真实分析没有执行目标程序，历史报告和镜像保持只读。 [证据索引](SR_EVIDENCE_EXCERPTS.json)
