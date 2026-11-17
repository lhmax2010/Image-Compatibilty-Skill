# PR #2 整改回归与证据

## 实际执行结果

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/time -v -o final-tests.time \
  python3 -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v \
  > final-tests.log 2>&1
node --check .agents/skills/tizen-image-compatibility/assets/enhanced-report.js
git diff --check
```

完整套件 **158 项，153 PASS、5 SKIP、0 FAIL/ERROR**。unittest 4.146 秒，命令 wall 4.56 秒，峰值 RSS 85224 KiB，退出码 0。相对审查基线 152 项新增 6 项测试方法；所有原有测试继续运行，未降低测试数量。

[完整日志](reports/review/v1.3-remediation/final-tests.log)、[计时](reports/review/v1.3-remediation/final-tests.time)、[旧代码复现](reports/review/v1.3-remediation/before-final-tests.log)。证据日志仅规范化本地路径前缀；日志中的 synthetic INCOMPATIBLE/quality gate FAIL 为测试预期输入，套件无失败。

新增 `test_report_review.py`：

| 测试 | 核验 |
|---|---|
| test_symbol_sizes_preserve_source_and_separate_code | FUNC/IFUNC/OBJECT/TLS/NOTYPE、多属性变化、版本/size/ID/证据/原始状态、ELF/包统计 |
| test_size_type_uncertainty_and_type_changes_are_observations | 缺失类型、不同类型、IFUNC/FUNC、TLS 分类 |
| test_package_roles_are_image_qualified_and_non_additive | 跨 Image、重叠角色、旧并集、原 roles、新 CSV/JSON 一致 |
| test_unknown_ownership_retains_observed_roles_without_credit | UNKNOWN 不变完整计数，保留 observed |
| test_invalid_consumer_paths_remain_unknown | NULL/空/异常路径与有效路径混合、完整和 observed 分离、全 Finding 保留 |
| test_evidence_collector_and_server_agree_on_symlink_boundary | 正常文件、前缀、路径穿越、越界 symlink，共享路径校验 |

旧套件中的分组守恒、原载荷/ID、source SHA、JSON/CSV/HTML、分页、安全、Ownership、Coverage Gates、Expected Test Manifest 回归全部通过。新尺寸 fixture 通过完整 build 的独立校验，原输入不修改。JS 语法与 Git whitespace 检查通过；本轮没有声称执行真实浏览器复核。

5 个 SKIP 与审查基线相同：

1. test_real_abidiff_embedded_and_split_layout_break：未设置 COMPAT_TEST_ABIDIFF。
2. test_real_clang_ast_and_arm：未设置 COMPAT_TEST_CLANG。
3. test_explicit_probes_exact_matrix_ids_with_simulated_receipts：所需 GCC/Clang 工具组合不可用。
4. test_real_arm_v6_v7_and_vfp_fixtures：实际 Clang ARM 编译器不可用。
5. test_real_hard_softfp_and_soft_pcs：实际 Clang 不可用。

## 真实索引只读审计

真实尺寸分类见 [real-size-audit.json](reports/review/v1.3-remediation/real-size-audit.json)。133638 代码尺寸 + 64 数据尺寸 = 原 133702，保留状态、未删除记录。

[real-integrity-audit.json](reports/review/v1.3-remediation/real-integrity-audit.json) 是本轮直接读取旧 SQLite 的结果：898342 Finding，状态直方图 12195 INCOMPATIBLE / 860110 UNKNOWN / 25726 COMPATIBLE / 311 IDENTICAL，Linking 855522，Unassigned 11111，Packages 722/736。mode=ro，索引 size/mtime 不变；没有写原 Package 结果或 Finding 载荷。该审计是既有真实数据复核，不是整改后派生报告验收，也没有重新对镜像归档执行全量哈希。

[scope-check.json](reports/review/v1.3-remediation/scope-check.json) 记录本轮源码指纹与 Git refs。现有 ELF/ABI/API/Linking 检测器未改，原 source results.json/findings.csv 未写，原报告未替换。当前 HEAD 仍为审查 SHA，main 和原 v1.2 分支保持不变。

上述结果记录整改开发阶段；其“HEAD 仍为审查 SHA”指提交前检查。PM 随后授权正常提交/推送，未授权合并或真实报告重建。

## 提交前重新验证

对同一组源码/测试 SHA256 再次执行上述完整 unittest 命令：**158 项，153 PASS、5 SKIP、0 FAIL/ERROR**，unittest 4.145 秒，命令 wall 4.52 秒，峰值 RSS 85480 KiB，退出码 0。五个 SKIP 名称和原因与上表一致。JS 语法与 Git diff whitespace 检查通过。

新日志：[publish-tests.log](reports/review/v1.3-remediation/publish-tests.log)、[publish-tests.time](reports/review/v1.3-remediation/publish-tests.time)。既有失败复现和只读真实数据审计记录保留原样；本次未重跑真实 Static、未重建真实增强报告。发布前文件清单、指纹和排除项见 [publication-check.json](reports/review/v1.3-remediation/publication-check.json)。

本轮结论：**四项代码整改回归通过，提交并更新 Draft PR #2，等待第二轮独立审查；真实派生报告仍未更新。**
