# 关键采集器门禁

执行状态、兼容性、验证覆盖分别记录。JSON 用 `execution.status` 和 `execution.collectors` 记执行事实，用 `quality_gate.execution_status` 记门禁，Markdown、HTML 和 CLI 同时显示两者。 `COMPLETE` 是当前 JSON 表示的成功状态，`NOT_EXECUTED` 表示无可执行数据源等情况，老 manifest 未记录执行事实时为 `UNKNOWN`。 [结果聚合与渲染](../../../.agents/skills/tizen-image-compatibility/scripts/compat/report.py#L16) · [RPM 采集](../../../.agents/skills/tizen-image-compatibility/scripts/compat/packages.py#L56)

| 情况 | 执行状态 | CI 行为 |
|---|---|---|
| 启用采集且成功 | COMPLETE | 按兼容性、strict 和最小覆盖率门槛判定 |
| 部分 ELF 采集失败 | PARTIAL | 保留失败对象与 UNKNOWN，继续应用已有阈值 |
| 一侧全部目标 ELF 采集失败，或已识别 RPM 数据库查询失败 | FAILED | 默认写完报告后退出 3 |
| 同一故障，显式 `ci.fail_on_collector_failure: false` | FAILED | 恢复原退出门槛。无 strict/覆盖或兼容门槛触发时可退出 0 |
| strict 或最低覆盖率阈值失败 | 保持执行事实 | 未触发更优先的采集门禁时退出 1 |
| 未达到 `--fail-on` 的不兼容 Finding | 保持执行事实 | 兼容门禁取配置的严重度，原始 INCOMPATIBLE 仍保留 |

退出码 2 继续用于无效输入或配置。可选 SDK、运行时适配器、普通调试工具缺失仍通过覆盖度表达。 [CLI 返回值](../../../.agents/skills/tizen-image-compatibility/scripts/tizen_compat.py) · [配置参考](../../../.agents/skills/tizen-image-compatibility/references/severity_rules.md)

真实负对照用同一输入，在只读隔离中让子进程无法打开 `/dev/null`。修复前退出 0，修复后退出 3。两次报告各有 12,642 条 UNKNOWN，后者仍无兼容性失败，两个 RPM 数量均为 null。正常重跑中，每侧 `toybox` 各有一个 ELF 解析未完成，RPM 采集成功，执行状态为 PARTIAL。 [机器证据摘录](SR_EVIDENCE_EXCERPTS.json)

确定性复现无需真实镜像。 `test_default_failed_collector_exit_and_legacy_override` 使用失败的受控读工具和已识别的临时 RPM 数据库路径，比较默认、旧退出行为、strict、最小覆盖率及 JSON/HTML/Markdown。 `test_partial_and_missing_optional_input_do_not_mask_compatibility_threshold` 比较 HIGH 和 CRITICAL 阈值。 [对应测试源码](../../../.agents/skills/tizen-image-compatibility/tests/test_phase8a.py#L109) · [测试结果](REGRESSION_SUMMARY.md)
