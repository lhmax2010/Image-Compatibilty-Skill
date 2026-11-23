# GNU 符号版本正确性

原 Finding `TC-1dc09eab2397194b` 将 `/usr/lib/libavcodec.so.62.11.100` 中 `LIBAVCODEC_62` 的缺失判为不兼容。两侧 `.gnu.version_d` 都有该定义，且 `avcodec_version@@LIBAVCODEC_62` 都在导出符号中。只有 VD 动态符号表含同名零尺寸、零值的 `GLOBAL DEFAULT ABS OBJECT` 节点标记。证据包含两侧原始 `readelf` 文本的 SHA256 和关键行。 [真实 readelf 摘录和旧 Finding](SR_EVIDENCE_EXCERPTS.json)

`collect_elf` 核对动态符号表、版本定义和需求清单。与已验证的非 BASE 版本定义同名且符合该 GNU ld 标记形态的记录移至 `version_node_markers`。已验证的旧 manifest 在比较时按相同规则解读。原始 Evidence 保留。普通 ABS 符号继续参与导出比较，真正删除的版本定义由独立比较记录。未定义版本化符号的版本名和读到的索引用于关联 `.gnu.version_r` 中的需求文件。 [ELF 采集与分类](../../../.agents/skills/tizen-image-compatibility/scripts/compat/elf.py#L136) · [ABI 比较](../../../.agents/skills/tizen-image-compatibility/scripts/compat/compare.py#L49) · [GNU 版本表规范](https://refspecs.linuxfoundation.org/LSB_3.1.1/LSB-Core-generic/LSB-Core-generic/symversion.html)

| 正反例 | 回归用例 |
|---|---|
| 标记失去但版本定义与函数仍在。没有同名版本定义的普通 ABS 导出丢失仍报不兼容。 | `test_gnu_marker_change_with_retained_node_and_ordinary_abs` |
| 真实版本定义删除在完整采集时不兼容，采集不全时 UNKNOWN。 | `test_removed_version_uses_verdef_and_requires_complete_collection` |
| 保留节点而删除版本化函数时，仍能检测函数丢失。 | `test_retained_node_does_not_hide_a_removed_function` |
| 保留原始标记，需求索引不匹配时拒绝完整度信用。 | `test_readelf_keeps_marker_evidence_and_checks_version_requirement_index` |
| 闭包已证实时区分版本需求满足与缺失。 | `test_bounded_linking_scope_and_required_version` |

[完整回归源码](../../../.agents/skills/tizen-image-compatibility/tests/test_phase8a.py#L22) · [测试结果](REGRESSION_SUMMARY.md)

真实报告中移除的 156 条全部与两侧仍然存在的版本定义逐项核对。其它 11,490 条不兼容保留原评估，适用证据见 [SR 对账说明](SR_BEFORE_AFTER.md)。
