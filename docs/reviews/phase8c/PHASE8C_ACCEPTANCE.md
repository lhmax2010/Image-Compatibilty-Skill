# Phase 8C 验收

代码基线为 `6d207bf40397ff749e1abcdcc0246374632575da`。

| 验收项 | 证据 |
| --- | --- |
| Split Debuginfo | 两侧的 libc 和 ld-linux 分离调试对象退出运行时闭包，保留原始采集证据和 DWARF。六个假 Linking 观察已在说明中逐条列出。 [分类与回归](DEBUG_ELF_CLASSIFICATION.md) · [真实对账](COVERAGE_BEFORE_AFTER.md) |
| 静态证据 | 同版本符号、版本节点、加载器配置、缓存、inode 权限及 xattr 已定向复核。Getconf 的实际运行绑定仍保持 UNKNOWN。 [证据范围](STATIC_EVIDENCE_VALIDATION.md) |
| 真实派生索引 | 见 [SQLite 验收](SQLITE_ACCEPTANCE.md)。 |
| SDK 获取方案 | 固定到对应 Base/Unified 快照，核实工具、Rootstrap、头文件、crt 和链接时库的包元数据。 [调查](SDK_ROOTSTRAP_RESEARCH.md) |
| 设备和运行时 | 未取得与两个快照匹配且已授权的目标环境。 [Phase 8D 准入](REMAINING_GAPS.md) |

## 自动化回归

```bash
python3 -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v
git diff --check
```

共 249 项，244 PASS、5 SKIP、0 FAIL，较基线增加四项。已跳过的用例如下。

| 测试 | 原因 |
| --- | --- |
| test_real_abidiff_embedded_and_split_layout_break | 未提供 COMPAT_TEST_ABIDIFF 和 libabigail。 |
| test_real_clang_ast_and_arm | 未提供 COMPAT_TEST_CLANG 和 Clang。 |
| test_explicit_probes_exact_matrix_ids_with_simulated_receipts | 需要实际 GCC 与 Clang 配对。 |
| test_real_arm_v6_v7_and_vfp_fixtures | 需要可用的 ARM Clang。 |
| test_real_hard_softfp_and_soft_pcs | 需要可用的 Clang。 |

变更见 compat/elf.py、compat/core.py、compat/linker.py、compat/compare.py、compat/coverage.py 与 test_phase8c.py。 schema 1.2、报告 Finding 载荷和证据链接继续沿用既有契约。全量产物和日志仅保存在工作区本地。 [源代码与回归入口](../../../.agents/skills/tizen-image-compatibility/)

最终完整回归耗时 148.620 秒。验收结论为 **CONDITIONAL PASS**。静态正确性修复和真实 SR 对账通过，SQLite 全量复核等待稳定的工作卷，SDK 与 Runtime 需后续准入。 [真实对账](COVERAGE_BEFORE_AFTER.md) · [剩余条件](REMAINING_GAPS.md)
