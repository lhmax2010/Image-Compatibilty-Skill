# Runtime Expected Plan 与回执对账

`runtime_workflow.py run` 在 SDB 准入及执行前写入 `runtime-expected-plan.json`。每个重复槽位独立记录 Test ID、Artifact、Manifest、Bundle、预期行为、绑定、目标 Scope、Profile、Build、enrollment 摘要和所需性。可选 `environment_id` 绑定到已准入的具体 Boot 环境。提供时在部署前验证。尚未接触目标的离线计划可以保留空值，实际身份由准入回执填充。

`runs[].artifacts` 支持原字符串和配置对象。对象示例为 `{"artifact_id":"version-present","repetitions":3,"required":true}`。可选项可用 `required:false` 和明确的 `skip_reason` 表示未满足的先决条件。授权中止、SDB 不可用和 fail-fast 保留完整计划及后续未执行项。

## 导入与最终选择

独立导入通过 `runtime_workflow.py report`。配置的 `expected_runtime_plan` 和 `reviewed_runtime_attempts` 分别提供独立保存的 `path` 与 `sha256`。Review Ledger 格式为 `tizen-compat-runtime-reviewed-attempts/v1`，其 `attempts` 按原始回执 SHA256 索引。每项含 `test_id`、`review_basis`，可用 `legacy:true` 标注经过人工复核的旧回执和 `eligible:false` 保留仅供溯源的历史尝试。审核者必须独立复核部署、实际输出、Loader、目标身份和清理记录，再固定 Ledger。文件 hash 仅证明所读字节的身份。无可信来源的导入可浏览，在验收计数中不授予成功。

字节一致的重复导入保留其来源引用，只计一次。Attempt ID 相同且载荷不同则隔离。不同 Attempt ID 的重试完整保留。存在多个可选结果时通过 `final_attempts` 将 Test ID 显式映射到最终回执 SHA256。无有效最终选项时保留 `NOT_VERIFIED`。计划无尝试为 `NOT_EXECUTED`。摘要、Profile、目标和环境身份错误均独立记录。回执的原始 claim 与对账状态分开。

| 实际历史账 | 数量 |
| --- | ---: |
| 必需预期测试 / 可选预期测试 | 31 / 1 |
| OBSERVED_SUCCESS | 24 |
| OBSERVED_EXPECTED_FAILURE | 6 |
| BEHAVIOR_MISMATCH | 1 |
| SKIP | 1 |
| 已复核的原始 Attempt ID | 44 |
| 已实际执行 / grant 前停止 | 42 / 2 |
| 最终验收 / 历史或诊断回执 | 31 / 13 |

Phase 8K 历史计划按当时冻结清单、计划请求、重复槽位和入场证据回建，属于追溯复核。独立检查了 602 处按尝试计的原始 Evidence 摘要引用、原始输出摘要、ARM 产物与部署、环境计划 ID，以及历史独立清理证明。历史 31 份最终回执逐字节与之前的选择相符。新增实机精确验证 1 次单独归档。未执行和不可信回执还通过合成正反例与 Chromium 夹具验证。

参见 [计划与对账实现](../../../.agents/skills/tizen-image-compatibility/scripts/compat/runtime_plan.py) 和 [编排入口](../../../.agents/skills/tizen-image-compatibility/scripts/runtime_workflow.py)。
