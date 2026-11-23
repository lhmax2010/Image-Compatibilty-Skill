# Linking 覆盖和真实样本

860,300 条 Linking Finding 在修复前后均为 UNKNOWN，基线 2,054 个适用检查单元的完整覆盖率均为 0%。四个现场样本的 ID、状态和解析原因在重跑中均保持一致。 [样本字段、证据摘要和计数](SR_EVIDENCE_EXCERPTS.json)

| 解析原因 | 数量 | 可定位的真实样本 |
|---|---:|---|
| `unknown_symbol_scope` | 442,049 | `TC-063f63c2674b34ea`，`activation_dm.so` 导入 `pop_epc_event`，缺可证明的根进程和加载闭包。 |
| `unknown_symbol_semantics` | 314,185 | `TC-000be73b4a4e552a`，`/etc/alternatives/halt` 导入 `gethostname_malloc@SD_SHARED`，存在一个候选，但 `scope_proven=false`。 |
| `unknown_version_requirement` | 57,107 | `TC-1f8a019a1fcbc848`，`activation_dm.so` 记录 `libgcc_s.so.1:GCC_3.5`，该作用域内实际 Provider 未证明。 |
| `unknown_search_environment` | 43,789 | `TC-1164a6c8dfac4200`，`activation_dm.so` 的归档 mode 可见，xattr 和 file capabilities 缺源证据，正常安全上下文未验证。 |
| `unknown_loader_abi` | 1,486 | 目标加载 ABI 证据缺口。 |
| 依赖变化与覆盖提示 | 1,062 | 1,060 条 `DT_NEEDED` 变化和 2 条总体覆盖提示。 |
| `unknown_loader_feature` | 618 | 加载标志或行为超出静态模型。 |
| `missing_provider` | 2 | 静态未观察到 Provider，加载证据尚不足以下结论。 |
| `unknown_collection` | 2 | 两侧 `toybox` ELF 解析不完整。 |

Phase 8A 允许使用完整的路径盘点，并分别要求闭包参与者的解析、版本和导出证据。无关 ELF 解析失败不再阻断具有完整证据的局部搜索。位置解析失败仍保留歧义。原有 loader 模型、作用域、namespace、secure execution、SONAME 复用和多 Provider 边界继续生效。 [依赖闭包源码](../../../.agents/skills/tizen-image-compatibility/scripts/compat/linker.py#L34) · [覆盖计算](../../../.agents/skills/tizen-image-compatibility/scripts/compat/coverage.py#L75)

`test_bounded_linking_scope_and_required_version` 验证完整路径盘点下的通过和缺失，以及盘点缺口、独立命名空间下的 UNKNOWN。Phase 7A 的 `LoaderFixTests` 继续覆盖 SONAME 与权限上下文。 [新回归](../../../.agents/skills/tizen-image-compatibility/tests/test_phase8a.py#L88) · [既有回归](../../../.agents/skills/tizen-image-compatibility/tests/test_static_fixes.py#L264) · [测试结果](REGRESSION_SUMMARY.md)

复核真实样本时，在同一镜像方向按 Finding ID 搜索 SR 产出的 CSV 或 JSON。对照机器证据中的 `component`、`interface`、`resolution` 和对应原始证据文件名。 [重跑方法](SR_BEFORE_AFTER.md)
