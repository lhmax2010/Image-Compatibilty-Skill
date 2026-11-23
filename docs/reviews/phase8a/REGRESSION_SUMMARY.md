# 回归测试

发布前以 Phase 8A 的 19 个代码、配置、测试和用户说明文件重跑全量测试。共 **237 项，232 PASS、0 FAIL、5 SKIP**，用时 **73.321 秒**。Phase 8A 实施时的独立全量运行同为 232 PASS、0 FAIL、5 SKIP，耗时 92.722 秒。

```bash
python3 -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v
```

发布前重跑在 Linux / Python 3.12.3 上执行。测试临时目录和 RPM `_tmppath` 都指向 workspace，RPM 集成用例使用宿主 `rpm` / `rpmbuild` 和合成包。 [脱敏 unittest 摘录](TEST_RESULTS.txt) · [代码身份](SOURCE_CHANGES.json)

| 未执行的可选用例 | 本机跳过原因 |
|---|---|
| `test_real_abidiff_embedded_and_split_layout_break` | 未配置 `COMPAT_TEST_ABIDIFF`，无法运行实际 libabigail 集成。 |
| `test_real_clang_ast_and_arm` | 未配置 `COMPAT_TEST_CLANG`，无法运行实际 Clang AST/ARM 集成。 |
| `test_explicit_probes_exact_matrix_ids_with_simulated_receipts` | 未提供所需的真实 GCC/Clang 工具组合。 |
| `test_real_arm_v6_v7_and_vfp_fixtures` | 缺实际 Clang ARM 编译器。 |
| `test_real_hard_softfp_and_soft_pcs` | 缺实际 Clang，无法生成配套 ARM PCS fixture。 |

新增的 9 项回归验证了 GNU 版本节点与普通 ABS 的区分、真实版本与函数删除、需求索引、静态 Linking 闭包、默认和兼容门禁、输入证据缺口以及磁盘余量。既有 Phase 7A、JSON/CSV、SQLite 构建与 Evidence 边界测试也通过。 [Phase 8A 测试](../../../.agents/skills/tizen-image-compatibility/tests/test_phase8a.py) · [Phase 7A 测试](../../../.agents/skills/tizen-image-compatibility/tests/test_static_fixes.py) · [增强报告测试](../../../.agents/skills/tizen-image-compatibility/tests/test_report_enhancement.py)

真实 SR 数据复核在独立运行中完成。SQLite 的全量空间预检和现场验收边界另列。 [真实报告对账](SR_BEFORE_AFTER.md) · [现场限制](KNOWN_LIMITATIONS.md)
