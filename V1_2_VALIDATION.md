# Tizen Image Compatibility Skill 1.2 — 实现与验证记录

本次在 `review/tizen-compatibility-correctness-1.1` 分支、HEAD `b5fe963efe4243e969638846fd5523e685dc3928` 基础上进行增量修改，保留原有模块和 CLI。未修改 main，未提交、推送、合并或重置。原有未跟踪的 `design.md`、`require.md` 保持原样。

初次附件在 6.7 节截断；本次已收到并核对补充的 6.7–11 节。下方原有 105 项测试/首轮压力数据作为历史记录保留，补充验收的最终结果见本文末尾。补充附件的最终回复格式第 10 项仍只包含数字 `10`，未提供该项内容；不推断额外要求。

## 实现范围

| 要求 | 修改与保守边界 | 证据 |
|---|---|---|
| M1 符号解析 | 保留依赖顺序、所有候选提供者、版本约束；未声明 startup scope、多个提供者、弱引用、IFUNC/GNU UNIQUE/PROTECTED、非 base namespace、未支持 flags/interposition 保持 UNKNOWN；保留证据充分的缺失符号/版本失败 | 原生 glibc 弱/强及顺序夹具、版本和外部 scope 回归 |
| M2 结果与完整度 | 每个义务列出必需检查；INCOMPATIBLE 可同时为 PARTIAL；只有 COMPLETE 获得完整覆盖计数；独立的 compatibility/coverage/strict 门禁原因，schema 1.2 | 失败与 UNKNOWN 并存、重复 finding、N/A 分母、实际 CLI 门禁测试 |
| M3 预期测试 | 执行前写 Expected Test Manifest；稳定 ID 绑定编译器、源码、SDK、来源和目的镜像；精确检查缺失/重复/意外 ID、阶段、哈希和原生参考；两个目的镜像均依赖完整 build 义务 | ID 集合、build ABI 前置条件、缺失 header、静态未执行、回执及交换 SDK 回归 |
| M4 ARMv7 | 配置的 SDK ABI 为主要证据，选定 loader/libc 为支持证据；区分明确冲突和不足；其他对象单独报告；base PCS 与 softfp 代码生成分开；保留 AArch64 | 真实 Clang hard/softfp/soft ET_REL 对象、主要 ABI、混合对象及 AArch64 回归 |
| 包清单 | 已安装 DB 和 RPM archive 分开；未知 DB 数量为 null；保留 NEVRA/epoch、依赖能力、文件清单及来源；不覆盖多版本 | 真实 rpmbuild、临时自建 RPM DB 与 archive 混合输入，源 DB 哈希不变 |
| 包归属与结论 | 文件清单索引、usrmerge/符号链接目标、多所有者、消费者/提供者/根消费者；显式 SDK 清单关联；包级 availability/metadata/ABI/API/linking/overall/completeness/coverage | 传递依赖失败归属、明确 SDK 归属、未归属接口、多版本及数据包 N/A 测试 |
| 包报告与规模 | 完整 JSON/package_results/packages.csv；Markdown 前 200 包，HTML 可过滤前 1000 包，逐字段预览最多 100 项；索引和流式 JSON/RPM XML | 格式/转义测试、2000 包清单回归、独立压力报告、超过 16 MiB 的 RPM 输出及损坏 XML 测试 |

参考实现与使用边界见 [correctness.md](.agents/skills/tizen-image-compatibility/references/correctness.md)、[execution.md](.agents/skills/tizen-image-compatibility/references/execution.md)、[packages.md](.agents/skills/tizen-image-compatibility/references/packages.md)、[schema 1.2](.agents/skills/tizen-image-compatibility/references/report_schema.md)。README 与 skill 指令已经同步，继续支持 Cline 按 SKILL.md 调用 Python CLI。

## 首轮复现与测试（历史记录）

修改前先验证分支/HEAD并阅读相关实现；原有 **69 项测试全部通过，无跳过**，记录见 [v12-baseline-tests.txt](.agents/skills/tizen-image-compatibility/tests/review/v12-baseline-tests.txt)。修改后 **105 项测试全部通过，无跳过**，包括 36 项新增测试。完整输出见 [v12-validation.txt](.agents/skills/tizen-image-compatibility/tests/review/v12-validation.txt)，新增测试见 [test_v12.py](.agents/skills/tizen-image-compatibility/tests/test_v12.py)。

[reproduce_v12.py](.agents/skills/tizen-image-compatibility/tests/review/reproduce_v12.py) 可使用 `COMPAT_SCRIPTS` 指定只读归档的旧版脚本。对同一合成输入：

| 观察 | 修改前 | 修改后 |
|---|---|---|
| 两个 eligible provider 导出同名符号 | COMPATIBLE | UNKNOWN，保留有序候选 |
| 一个已确认链接失败并存 UNKNOWN 检查 | verified=1、coverage=100% | incompatible=1、verified=0、coverage=0% |
| 一个无关 ARM 对象缺 ABI 属性 | 全 rootfs 前置条件 False | 明确配置主 ABI 时探针 COMPATIBLE；无关对象单独报告 |

原始输出：[before](.agents/skills/tizen-image-compatibility/tests/review/v12-before.txt)、[after](.agents/skills/tizen-image-compatibility/tests/review/v12-after.txt)。

```bash
SKILL=.agents/skills/tizen-image-compatibility
COMPAT_TEST_ABIDIFF=/tmp/tizen-correctness-tools/abidiff \
COMPAT_TEST_CLANG=/tmp/tizen-correctness-tools/clang \
python3 -m unittest discover -s "$SKILL/tests" -v
python3 -m compileall -q "$SKILL/scripts" "$SKILL/tests"
python3 /opt/nvme-home/linhao/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$SKILL"
git diff --check
```

本机使用实际 GCC/readelf/rpm/rpmbuild，以及前轮保留的 Clang 14.0.6、libabigail 2.4 临时解包 wrapper（来源和方法见 [1.1 验证记录](VALIDATION_RESULTS.md)）；上述 `/tmp` 工具不是仓库依赖。其他机器可配置等价工具路径；不提供时相应用例会明确跳过，不能据此声称运行了真实工具集成。

原生 glibc 测试只执行本测试自行编写/编译的宿主夹具，使用干净环境与独立工作目录，不是 OS sandbox。ARM 对象仅编译和读取，未执行。运行矩阵使用模拟适配器测试 harness；没有运行真实 Tizen payload、设备、QEMU 或生产传输适配器。RPM 集成只向临时自建数据库写入 `--justdb --noscripts --notriggers` 元数据，不向源镜像安装包。

## 首轮规模测量（历史记录）

```bash
python3 "$SKILL/tests/review/benchmark_v12.py" --packages 2000 --symbols 10 \
  --output /tmp/tizen-v12-scale-new
```

这是明确标记为 SYNTHETIC 的元数据夹具，不是实际 RPM 扫描或 Tizen 性能结果。两侧各 2000 包、每包 10 导出符号、共 20000 个刻意制造的符号缺失：

- 聚合构建约 **0.522 秒**，输出约 **1.617 秒**，峰值 RSS **121.2 MiB**（本机单次测量）。
- 完整 `results.json` **94,342,980 字节**，`packages.csv` **2000 行**；HTML **5,365,864 字节**，保留 1000 包展示上限。
- 所有包为 INCOMPATIBLE + PARTIAL；ABI 导出义务已确认失败，类型布局未验证，完整 ABI 覆盖 **50%**；100% 覆盖门禁正确失败。
- 流式 JSON 改动前同一夹具峰值约 568.5 MiB；流式写入避免额外构造完整 JSON 字符串。全量数据依然占用内存和磁盘，不承诺固定内存或任意规模性能。

指标原文：[v12-scale.json](.agents/skills/tizen-image-compatibility/tests/review/v12-scale.json)。本机完整压力产物位于 `/tmp/tizen-v12-scale-streamed/`，未将大体积报告加入仓库。RPM 输出另有超过 16 MiB 的合成 XML 回归，确认读取完整 raw evidence，而非被截断的 stdout 预览；原始 XML 损坏则清单为 UNKNOWN。

## 仍需真实产品证据

未收到真实 Tizen rootfs、匹配 SDK、debuginfo 和授权运行适配器，因此这次证明的是检查器行为，没有证明 ONEMAIN/ASAN 或 GCC/LLVM 产品镜像兼容。C++/ASAN/生成代码符号缺失仍需接口和消费者证据，不能由名字或导出总量直接豁免。

完整 glibc namespace/interposition/IFUNC 行为、包依赖求解、自动改名/拆包关系、穷尽 API 语义以及全部硬件/安全/性能维度仍不在离线证明范围内。没有 DB 的 runtime 镜像不能获得可靠包归属；缺少 SDK/dev 包关联时 API 不能升级为兼容。旧 schema 成功记录不会获得 1.2 完整覆盖信用。HTML 过滤只检索其展示子集；完整机器数据请使用 JSON/CSV。

## 补充验收：20 项必需回归逐项核对

以下简称均为实际测试模块：**V** = [test_v12.py](.agents/skills/tizen-image-compatibility/tests/test_v12.py)，**C** = [test_correctness.py](.agents/skills/tizen-image-compatibility/tests/test_correctness.py)，**A** = [test_acceptance.py](.agents/skills/tizen-image-compatibility/tests/test_acceptance.py)，**F** = [test_framework.py](.agents/skills/tizen-image-compatibility/tests/test_framework.py)。这些用例调用生产 collector/comparator/ownership/coverage/reconcile/report/CLI；断言不重新实现聚合算法。合成元数据、模拟回执与真实工具集成分别标注。

| # | 场景及精确测试函数 | 正/反行为与证据范围 |
|---|---|---|
| 1 | V.`LookupHardeningTests.test_multiple_providers_order_is_evidence_not_verification`; `.test_non_scope_and_unsupported_features`; `.test_native_glibc_weak_first_and_dependency_order` | 一个确定提供者可通过；两个提供者保留顺序并 UNKNOWN。自编原生 ELF 实际 glibc 顺序结果 11/22，未执行 Tizen ELF。 |
| 2 | V.`LookupHardeningTests.test_distinct_versions_wrong_requirement_provider`; C.`LoaderTests.test_requirements_bound_to_provider_not_any_library` | 正确版本/提供者可通过；错误依赖版本失败，导入不升级为成功。 |
| 3 | V.`LookupHardeningTests.test_non_scope_and_unsupported_features`; C.`LoaderTests.test_missing_and_unknown_environment` | 完整启动作用域与不完整环境、外部 scope、namespace/flags 分开。 |
| 4 | V.`CompletenessTests.test_confirmed_failure_and_unknown_are_independent`; `.test_gate_reasons_separate_failure_and_partial_coverage` | 已确认失败保持 INCOMPATIBLE，但缺失检查使完整覆盖为 0；兼容/覆盖门禁分开失败。 |
| 5 | V.`ExpectedManifestTests.test_exact_sets_reject_duplicates_missing_and_unexpected`; `.test_build_target_abi_is_mandatory_on_both_destinations` | 完整精确 ID/stage 集通过；缺失、重复、无关 ID、build ABI 缺证据阻止通过。 |
| 6 | C.`MatrixAndSemanticTests.test_receipt_hash_and_deployment_validation`; `.test_candidate_build_uses_its_own_reference`; `.test_own_reference_failure_cannot_pass_elsewhere` | 有效回执通过；错误环境/hash/部署或本源失败不通过。模拟 receipt 测 harness；编译部分使用真实 GCC，不冒充设备执行。 |
| 7 | V.`TargetAbiTests.test_primary_config_ignores_unrelated_missing_attributes_but_reports_mixed`; `.test_no_primary_unknown_wrong_object_and_aarch64`; `.test_real_hard_softfp_and_soft_pcs` | 主 ABI 合法、无关缺失、明确权威冲突、无权威信息分别验证；真实 Clang 三类 ARM 对象仅解析不执行。 |
| 8 | V.`PackageAnalysisTests.test_database_unavailable_not_empty_installed_inventory`; V.`PackageIntegrationTests.test_actual_installed_db_and_archive_remain_separate` | 缺失/空目录 DB 为 null/UNKNOWN；真实已建 DB 返回实际安装清单，目录中的 RPM 不算安装。 |
| 9 | A.`AcceptanceTests.test_count_reconciliation_rejects_mismatch_and_preserves_unknown`; V.`PackageIntegrationTests.test_actual_installed_db_and_archive_remain_separate` | 正确数量通过；篡改数量拒绝或降级。集成测试独立 `rpm -qa --qf` 和 `rpm -qal` 对账身份、数量和文件，比较源 DB 哈希。 |
| 10 | A.`AcceptanceTests.test_real_missing_public_library_package_and_direction`; V.`PackageAnalysisTests.test_consumer_provider_roles_and_unassigned_files` | 真实自编共享库解析关联到 RPM 夹具所有者；未归属 ELF/finding 仍可见；正反方向不同。 |
| 11 | V.`PackageIntegrationTests.test_explicit_sdk_package_ownership_retained`; V.`ExpectedManifestTests.test_missing_sdk_header_and_wrong_inventory_association`; A.`AcceptanceTests.test_sdk_elf_does_not_borrow_same_path_runtime_abi_evidence` | 明确 SDK-devel 所有者保留头文件失败；错误 SDK 源清单不能归属；同路径 runtime ABI 不能借给 SDK ELF。 |
| 12 | V.`PackageAnalysisTests.test_usrmerge_symlink_and_multiple_owners`; V.`PackageIntegrationTests.test_duplicate_exact_nevra_remains_ambiguous` | usrmerge 可解析，链接所有者与目标所有者分开；多个所有者/重复身份保留 UNKNOWN。 |
| 13 | A.`AcceptanceTests.test_real_missing_public_library_package_and_direction` | 库存在时可归属；路径消失保留 package/missing-interface 及 UNKNOWN，不假定不能被替代；完整 loader 上明确 DT_NEEDED 缺失另行确认失败。 |
| 14 | A.`AcceptanceTests.test_rename_split_removed_added_and_architecture_are_distinct_clues` | 一对一共享文件为可能改名/替代，多个包为可能拆包；无共享文件、独立新增、架构不同分别保留；不伪造确认的 lineage。 |
| 15 | A.`AcceptanceTests.test_runtime_only_break_keeps_api_unknown`; V.`PackageAnalysisTests.test_sdk_unassigned_not_guessed_from_runtime_path` | runtime ABI 破坏不抹掉 API UNKNOWN；无 SDK 所有权不能靠同路径猜测开发包。正面 SDK 证据见第 11 项。 |
| 16 | A.`AcceptanceTests.test_data_only_overall_is_not_a_compatibility_pass`; V.`PackageAnalysisTests.test_data_only_applicability_and_runtime_api_unknown` | 完整数据包无公开接口为 N/A；不完整清单为 UNKNOWN，不自动 COMPATIBLE。 |
| 17 | A.`AcceptanceTests.test_runtime_only_break_keeps_api_unknown`; V.`PackageAnalysisTests.test_package_break_preserved_with_layout_and_api_gaps` | ABI INCOMPATIBLE + API UNKNOWN → package/global INCOMPATIBLE、验证 PARTIAL；不获得完整 ABI 覆盖。 |
| 18 | A.`AcceptanceTests.test_cross_format_exact_records_and_corruption_detection`; V.`PackageAnalysisTests.test_all_package_report_formats_and_escaping` | 生产报告序列化后独立读取，精确比较 ID/status/归属及 HTML/Markdown 展示；删一条 CSV 行必须失败，危险字符串必须转义。 |
| 19 | A.`AcceptanceTests.test_v12_manifest_without_expected_metadata_cannot_reuse_pass`; `.test_unexpected_failure_and_legacy_matrix_failure_remain_visible`; V.`ManifestMigrationTests.test_schema_11_success_downgraded_failure_preserved`; F.`EndToEndTests.test_full_offline_cli_and_reuse` | 缺少新元数据不沿用成功；旧/意外失败仍可见；旧版迁移不冒充重执行。实际 CLI 复用保持方向和明确的未知项。 |
| 20 | V.`PackageIntegrationTests.test_indexed_many_packages_have_complete_machine_records`; A.`AcceptanceTests.test_cross_format_exact_records_and_corruption_detection`; `.test_benchmark_budget_rejects_time_memory_and_reference_regressions`；独立 `benchmark_v12.py` 运行 | 2000 包真实调用生产聚合；压力版本 2 共 22201 finding，含 2000 依赖关系、200 API 缺口、1 未归属 finding；完整 JSON/CSV 对账，性能回归/不等规模 reference 被拒绝。 |

另外：A.`test_two_root_consumers_keep_distinct_transitive_evidence` 验证同一中间库失败不会吞掉两个入口上下文；A.`test_duplicate_findings_are_audited_and_conflicts_rejected` 验证重复审计；A.`test_obligation_failure_without_finding_controls_global_status_and_gate` 验证无 finding 的失败义务不会被全局状态/门禁漏掉；A.`test_indexing_and_aggregation_are_deterministic_under_inventory_permutation` 验证顺序稳定；A.`test_sdk_and_rootfs_remain_readonly_during_real_compile_probes` 校验真实 GCC 头文件编译前后 SDK/rootfs 哈希。

安全边界的现有负例继续保留：C.`MatrixAndSemanticTests.test_direct_target_runner_forbidden`、F 的 TAR 路径/符号链接越界测试、输出目录保护、CLI source immutability，以及 runtime 授权/工具缺失回归。未使用 sudo、源镜像安装、分支切换、重置或生产目标执行。

## 补充验收最终执行记录

本轮修改前重跑 **105/105 通过、0 失败、0 跳过**：[基线日志](.agents/skills/tizen-image-compatibility/tests/review/v12-acceptance-baseline.txt)。新增 **15 项** AcceptanceTests，另增强原 RPM 集成用例的独立 source inventory 对账，保留原有测试。最终 **120/120 通过、0 失败、0 跳过**：测试计时 3.287 秒；整个命令 wall 3.37 秒、峰值 RSS 88,104 KiB，退出码 0。见 [最终测试日志](.agents/skills/tizen-image-compatibility/tests/review/v12-acceptance-validation.txt) 和 [命令计时](.agents/skills/tizen-image-compatibility/tests/review/v12-acceptance-suite-metrics.txt)。探索中两处测试断言失败及修正说明保留在 [探索日志](.agents/skills/tizen-image-compatibility/tests/review/v12-acceptance-exploratory.txt) 和审查发现文件中；不混计为最终结果。

最终套件的精确命令（在仓库根目录）：

```bash
/usr/bin/time -f 'exit_code=%x\nwall_seconds=%e\npeak_rss_kib=%M' \
  -o /tmp/tizen-acceptance-final-suite.metrics \
  env COMPAT_TEST_ABIDIFF=/tmp/tizen-correctness-tools/abidiff \
      COMPAT_TEST_CLANG=/tmp/tizen-correctness-tools/clang \
  python3 -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v \
  > /tmp/tizen-acceptance-final-suite.log 2>&1
```

### 独立压力检查

两次正式规模检查均调用生产 `build_results → coverage_report/analyze_packages → generate`，之后释放聚合结果，重新加载输出 JSON/CSV 验证精确集合。验证所有 baseline package 行及 candidate assessments、source count reconciliation、每条 ABI/API 归属、全部 provider/consumer 边、全局未归属 finding。JSON 和 CSV 的 finding ID 多重集合必须与输入完全相同，关联集合不得有丢失或悬空 ID。HTML 数据属性逐项对应前 1000 个包/finding，Markdown 前 200 行核对包名。该 JSON 读回本身也计入 wall/RSS；峰值比首轮只生成报告的测量高，不能直接拿两种负载做性能对比。

| 夹具规模 | 唯一 findings | 包 CSV 行 | 依赖边 | 构建 / 输出 / 独立核对（秒） | 总 wall（秒） | 峰值 RSS（MiB） | 退出码 |
|---|---:|---:|---:|---|---:|---:|---:|
| 1000 对包 × 10 导出 | 11101 | 1000 | 1000 | 0.351 / 1.028 / 0.925 | 2.303 | 195.5 | 0 |
| 2000 对包 × 10 导出 | 22201 | 2000 | 2000 | 0.718 / 1.759 / 1.374 | 3.851 | 366.8 | 0 |
| 4 对包 × 2 导出，故意设置极低时间预算 | 14 | 4 | 4 | 0.002 / 0.005 / 0.009 | 0.015 | 20.2 | **1（预期）** |

规模翻倍时本机聚合时间约 2.05 倍、完整 wall 约 1.67 倍；只是这两个负载的测量，不是任意输入复杂度证明。2000 包输出 `results.json` 为 105,611,131 字节，HTML 5,835,096 字节。所有 22201 个 finding 保留：20000 导出失败、2000 依赖失败、200 个 API 未验证、1 个未归属 finding；所有包保持 INCOMPATIBLE + PARTIAL，ABI 完整覆盖 50%。30 秒 / 768 MiB 预算及同规模参考的 2 倍回归阈值均通过。负面预算命令先完成正确性核对，随后因为超时预算返回 1，证明工具并非运行完即宣告通过。

```bash
python3 .agents/skills/tizen-image-compatibility/tests/review/benchmark_v12.py \
  --packages 1000 --symbols 10 --output /tmp/tizen-acceptance-final-1000

python3 .agents/skills/tizen-image-compatibility/tests/review/benchmark_v12.py \
  --packages 2000 --symbols 10 --max-seconds 30 --max-rss-mib 768 \
  --reference .agents/skills/tizen-image-compatibility/tests/review/v12-acceptance-reference.json \
  --max-regression-factor 2 --output /tmp/tizen-acceptance-final-2000

python3 .agents/skills/tizen-image-compatibility/tests/review/benchmark_v12.py \
  --packages 4 --symbols 2 --max-seconds 0.000001 \
  --output /tmp/tizen-acceptance-budget-negative
```

实际测量日志：[1000 包](.agents/skills/tizen-image-compatibility/tests/review/v12-acceptance-scale-1000.json)、[2000 包](.agents/skills/tizen-image-compatibility/tests/review/v12-acceptance-scale-2000.json)、[参考测量](.agents/skills/tizen-image-compatibility/tests/review/v12-acceptance-reference.json)、[预期预算失败](.agents/skills/tizen-image-compatibility/tests/review/v12-acceptance-budget-negative.json)。首次参考测量同为版本 2/2000 包；声明了源码夹具而非真实 RPM/ELF 扫描。完整大报告保留在上述本机 `/tmp` 目录，不加入仓库。可供代码审查的小型示例已加入 [examples/package-report](.agents/skills/tizen-image-compatibility/examples/package-report/README.md)，生成器退出码 0，且运行同一个独立序列化核对器；报告内的失败门禁是夹具的预期结果。

### 验收结论与边界

收到的 6.7–11 节已逐项检查并补齐可执行验收与交付物；代码可进入独立审查。未进行真实 Tizen TV/SDK/设备的生产兼容性验收。真实 glibc scope、API 语义、包 lineage/solver、SDK ELF 独立 ABI 分析、目标适配器及系统/硬件维度的限制见 [能力分类与生产前提](V1_2_CORRECTNESS_REMEDIATION.md)。其中 renamed/split 仅有候选线索；“缺少库路径”不等于“已确认接口破坏”；candidate assessment 不代表逆向兼容通过。

所有兼容/完整度结论以证据为准。未使用 sudo；未修改 main、切换分支、提交、推送、合并或重置。本轮精确文件清单见 [V1_2_ACCEPTANCE_FILES.md](V1_2_ACCEPTANCE_FILES.md)。

补充静态检查均退出 0：`python3 -m compileall -q .agents/skills/tizen-image-compatibility/scripts .agents/skills/tizen-image-compatibility/tests`、skill-creator `quick_validate.py`、`git diff --check`。示例配置、两侧生成 manifest 可读取，18 个 Markdown 文件的本地链接核对通过。精确 argv/退出码/输出见 [v12-acceptance-checks.json](.agents/skills/tizen-image-compatibility/tests/review/v12-acceptance-checks.json)。最终分支仍为 `review/tizen-compatibility-correctness-1.1`，HEAD 仍为 `b5fe963efe4243e969638846fd5523e685dc3928`；原有 `design.md`、`require.md` 哈希与本轮开始时一致。
