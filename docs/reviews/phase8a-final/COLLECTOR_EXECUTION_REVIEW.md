# 采集执行完整性

修改前以两个小型 manifest 复现。两侧都有 `collector_execution`，baseline RPM 成功但 readelf 回执缺失，candidate 两项成功；旧聚合返回 `COMPLETE`。原因是它只汇总存在的状态。新聚合由启用维度展开两侧的预期回执。缺项在结果中显示为 `UNKNOWN`、`recorded=false` 和 `MISSING_RECEIPT`，原 manifest 不补写成功回执。 [预期采集器与回执校验](../../../.agents/skills/tizen-image-compatibility/scripts/compat/core.py) · [聚合及报告渲染](../../../.agents/skills/tizen-image-compatibility/scripts/compat/report.py)

| 启用范围内的结果 | 执行汇总 |
|---|---|
| 任一关键采集器明确失败 | FAILED |
| 有 PARTIAL，或 COMPLETE 同时有缺失、UNKNOWN 或适用任务未执行 | PARTIAL |
| 有 UNKNOWN，且无已完成或部分完成的适用任务 | UNKNOWN |
| 所有适用任务有 COMPLETE 回执 | COMPLETE |
| 仅有未执行、不适用，或相关维度全关 | NOT_EXECUTED |

`NO_ELF_OBJECTS` 仅在盘点已建立、没有目标时标为不适用。禁用采集器使用 `DISABLED`，仍提示适用任务未执行。运行时镜像找不到已识别 RPM 数据库使用 `RPM_DATABASE_NOT_FOUND`，安装数保持未知。包归档范围没有目标可报告不适用。真实数据库查询失败仍为 FAILED。旧 manifest 缺回执按 UNKNOWN 处理。 [采集回执](../../../.agents/skills/tizen-image-compatibility/scripts/compat/collect.py)

| CLI 情况 | 退出码 |
|---|---:|
| 关键 FAILED，默认 `ci.fail_on_collector_failure: true`，包括同时触发 strict 或 coverage | 3 |
| 关键 FAILED，显式关闭采集失败门禁，其余门禁也未触发 | 0 |
| 显式关闭采集失败门禁后，strict、`minimum_coverage` 或兼容性阈值触发 | 1 |
| PARTIAL 或 UNKNOWN，且既有门禁未触发 | 0 |
| 无效输入或配置 | 2 |

JSON、HTML、Markdown 均使用同一聚合结果。执行状态不改变镜像兼容性。真实 SR 正常运行返回 1，执行为 PARTIAL。相同子进程权限故障负对照返回 3、执行 FAILED、镜像 UNKNOWN；仍有 12,642 条 UNKNOWN，RPM 数量均为 null。 [现场对账](SR_REVALIDATION.md) · [回归 `test_execution_slots_distinguish_missing_and_nonapplicable`、`test_missing_receipt_renders_equally_in_json_markdown_and_html`、`test_cli_collector_failure_and_policy_combinations`](../../../.agents/skills/tizen-image-compatibility/tests/test_phase8a_final.py)
