# v1.3 独立代码审查交接

本交付供 ChatGPT 在 GitHub 审查源码、测试与小型验证证据。它是报告功能验证交付，不是 GCC/LLVM 镜像兼容性证明或产品发布认证。分支保持 Draft，不合并。

## 1. 确切版本与提交边界

| 用途 | 完整 Commit SHA |
|---|---|
| PR base：`review/tizen-compatibility-correctness-1.2` | `2d5bacaef2af1a9bd4b793123de02684e5f38128` |
| Commit 1：`fix: finalize v1.2 compatibility correctness` | `67d039c4ecc9a169fe9da0530d3bda6b5df01b62` |
| Commit 2：`feat: add v1.3 scalable compatibility report explorer` | `15c9b6340268983dc51ad308319dafe68f39a6a0` |
| 保持不变的 main | `386a284c37b0fdf105948bef35d1bacdc7a9c389` |

交付分支：`review/tizen-compatibility-report-v1.3`。两个代码提交后另加一个仅文档/证据的交接提交，以便在本文记录确切代码 SHA；该交接提交自身 SHA 由 GitHub PR head 和 `git log -1 --format=%H -- V1_3_REVIEW_HANDOFF.md` 给出，避免文档自引用哈希。没有 amend、force-push、reset、stash 或覆盖已有分支。

执行前暂存区为空。全部 46 个修改/未跟踪文件与此前冻结快照吻合，无未知改动；其中 44 个属于代码/测试/文档，`design.md` 与 `require.md` 是已有本地需求输入，保持原样、不提交。完整初始分类和字节数见 [PREPUBLICATION_CLASSIFICATION.json](reports/review/v1.3/PREPUBLICATION_CLASSIFICATION.json)。

RC 的 27 个文件从 v1.3 开发前 `code-before` 快照精确暂存；共享的 README、SKILL、report_schema 仅将 RC 内容放入第一个提交。未替换工作文件。第二个提交恰为原 v1.3 的 20 个文件，其中 3 个文档与 RC 重叠；合计 44 个不同文件。

## 2. 修改范围与语义边界

**v1.2 RC**：ARM CPU tag 差异与调用约定、ISA、硬件证据分离；显式 C/C++ Probe 不再依赖内置测试开关；符号解析完整度必须有实际采集证据和显式 true；candidate-only 包为 ADDED/UNKNOWN；Missing Interfaces 先过滤再限量，显示完整总数。正反例和原始复现结果见 [V1_2_FINAL_REVIEW.md](V1_2_FINAL_REVIEW.md) 与 `tests/review/rc-before.json`、`rc-after.json`。五项均有通过的回归证据；这些是明确的正确性修复，不能描述成对旧错误行为完全无语义变化。

**v1.3**：独立读取既有报告，生成 Package/ELF/Symbol 统计、Symbol Differences、Linking 导航分组和 SQLite 分页浏览。没有修改既有检测器、采集器、Package Ownership、Coverage Gates 或 Expected Test Manifest。原始 ABI/API/Linking 状态、ID、验证程度与包评估保留；MATCHED、SIZE_CHANGED 等只是显示分类，不增加兼容性信用。

**本次发布整理**：没有修改任何生产代码或测试。新增 28 个小型证据文件及本文，给 `V1_3_CHANGED_FILES.md` 追加发布说明。所有 41 个相关源码/测试/资产的 SHA256 与最终真实报告验证工作区一致，见 [CODE_PROVENANCE.json](reports/review/v1.3/CODE_PROVENANCE.json)。历史文档中“未提交/未授权发布”的表述是此前任务结束时的状态；本次明确授权的 Draft 交付以本文为准。

## 3. 本次重新执行的测试

从仓库根目录执行：

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR="$ACCEPTANCE_ROOT/work/phase5/tmp" \
  /usr/bin/time -v -o "$ACCEPTANCE_ROOT/work/phase5/publication/full-tests.time" \
  python3 -m unittest discover \
  -s .agents/skills/tizen-image-compatibility/tests -v \
  > "$ACCEPTANCE_ROOT/work/phase5/publication/full-tests.log" 2>&1
node --check .agents/skills/tizen-image-compatibility/assets/enhanced-report.js
git diff --cached --check
```

`ACCEPTANCE_ROOT` 是本次独立工作目录；发布的日志仅将本地路径前缀规范化。结果：**152 项，147 PASS，5 SKIP，0 FAIL/ERROR**，unittest 15.711 秒，完整命令 16.08 秒，峰值 RSS 81588 KiB，退出码 0。逐项日志：[full-tests.log](reports/review/v1.3/full-tests.log)，计时：[full-tests.time](reports/review/v1.3/full-tests.time)。JS 语法检查和 Git whitespace 检查通过。

为验证拆分安全性，使用 `git checkout-index --all --prefix=<new-isolated-dir>/` 导出 RC 暂存树，在隔离目录运行相同 unittest discover：**131 项，126 PASS，5 SKIP，0 FAIL/ERROR**，4.392 秒。见 [rc-tree-tests.log](reports/review/v1.3/rc-tree-tests.log) 与 [计时](reports/review/v1.3/rc-tree-tests.time)。这不切换/覆盖工作树；v1.3 新增的 21 项测试全部通过。

| 跳过的确切测试 | 原因 |
|---|---|
| `test_real_abidiff_embedded_and_split_layout_break` | 未设置 `COMPAT_TEST_ABIDIFF`，可选实际 libabigail 集成未启用 |
| `test_real_clang_ast_and_arm` | 未设置 `COMPAT_TEST_CLANG`，可选实际 Clang semantic/ARM 集成未启用 |
| `test_explicit_probes_exact_matrix_ids_with_simulated_receipts` | 所需实际 GCC/Clang 编译工具组合不可用 |
| `test_real_arm_v6_v7_and_vfp_fixtures` | 实际 Clang ARM 编译器不可用 |
| `test_real_hard_softfp_and_soft_pcs` | 实际 Clang 不可用 |

没有安装工具或把 SKIP 记为 PASS。旧 RC 文档中 131/131 的历史结果来自当时显式配置的 Clang/libabigail 包装工具，与本次环境不同。两份日志分别保留，不覆盖历史证据。

统计、链接分组、JSON/CSV/HTML、输入不变性、所有权和 Expected Test Manifest 的具体测试可在上述完整日志按名称定位；新测试到要求的映射见 [V1_3_REPORT_VALIDATION.md](V1_3_REPORT_VALIDATION.md)。未重跑真实 Static、未执行目标镜像程序。

## 4. 真实 Tizen 输入与证据对应

Profile `tizen-headless-armv7l`，架构 `armv7l`，方向 baseline → candidate。GCC/LLVM 是用户声明标签，未做实际编译器来源归因。

| 镜像 | 归档字节数 | 下载时核实的 SHA256 |
|---|---:|---|
| [GCC baseline 20261115.233954](https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Unified/tizen-unified_20261115.233954/images/standard/tizen-headless-armv7l/tizen-unified_20261115.233954_tizen-headless-armv7l.tar.gz) | 300322412 | `c4cb24c311c2d4907a180be23017a22a7115157aefe7e3574b0c2a9ec0c8c70b` |
| [LLVM candidate 20261113.065522](https://download.tizen.org/RBS/TIZEN/Tizen/Tizen-Unified-Toolchain/tizen-unified-toolchain_20261113.065522/images/standard/tizen-headless-armv7l/tizen-unified-toolchain_20261113.065522_tizen-headless-armv7l.tar.gz) | 294165770 | `4c3cc88a0854851dde6bbcfae71ae2a534d25e83b1778d2f9efeda7b4845d63e` |

准确下载记录摘录见 [INPUT_PROVENANCE.json](reports/review/v1.3/INPUT_PROVENANCE.json)；以该记录中的实际字节数为依据。增强输入为 `<ACCEPTANCE_ROOT>/reports/phase4-static/skill-report`，输出为 `reports/phase5-report-enhancement`。源 `results.json` SHA256 为 `6acdc3f24bcd874318159c56b521a55b98037df91a8073c351fce6ed233d068d`。

证据与代码对应不是“同一个 Git SHA 从头到尾重新生成全部报告”：原完整生成后，曾做已记录的概览状态显示修正、列表载荷优化和导航索引修复。最终浏览器、独立对账、全量测试和冻结源码哈希对应本次代码；[overview-refresh-evidence.json](reports/review/v1.3/overview-refresh-evidence.json) 与 [navigation-index-evidence.json](reports/review/v1.3/navigation-index-evidence.json) 记录派生数据修复边界。没有因本次 Git 交付而重复执行巨型分析。

## 5. 数量守恒与兼容性状态复核方法

1. **898342 条 Finding**：逐条保留原始 ID、完整 JSON 无损压缩载荷与 canonical payload SHA256；内置验证逐字段比对原 `findings.csv` 的 13 个字段与载荷，并核对状态直方图。独立读取生成的 `finding-index.csv`，依序与 SQLite 的 `id,status,dimension,n,payload_hash,group_id` 比较，不只比较行数。11111 条 unassigned ID 另作逐行核对。原状态不变：12195 INCOMPATIBLE、860110 UNKNOWN、25726 COMPATIBLE、311 IDENTICAL。
2. **855522 条 Linking Finding**：全部仍为 UNKNOWN。134402 个导航组的 `sum(raw_count)` 必须等于原 Linking 总量及完整成员 CSV 行数；逐条对账 `group_id,id,consumer_image,consumer_path,root_image,root_path,provider_path`，检查成员引用存在且不存在非 Linking 成员。62187 个多观察组包含 783307 条记录，加 72215 个单条组，恰为 855522。9 个原因类别的原始数和组数详见验证文档及 overview；原因缺失保留 NOT_RECORDED。
3. **722/736 Package**：从两侧原 installed RPM inventory、原 packages.csv、SQLite packages 表与生成的 package CSV 对账，合计 1458 行；715 matched、7 baseline-only、21 candidate-only。逐项保留原包状态/verification/coverage/confidence/limitations；另从独立 canonical ELF 行重新累计每包符号统计，防止共享归属/别名重复计数。2007/2116 原 ELF 行归一为 1968/2077，各去除 39 个别名。共享所有权导致包归属总和可超过镜像去重总量。
4. **UNKNOWN 保留**：真实 manifests 的 `collection_complete=false`；全部完整包计数保持 UNKNOWN，另给 observed 数字。183/178 个未观察到 ELF 的包不能得到完整零；缺 SDK、debuginfo、loader 环境的状态不提升。
5. **JSON/CSV/HTML**：内置 23 项对账与独立 12 项对账全部通过。CSV 不限量，HTML 只显示分页；UI 显示总数，原始 Finding 详情可追溯完整载荷。实际 Chromium 验证 Overview → Package 搜索 → glibc → ELF 50 行符号 → Linking → Group → 原 Finding，无 JS 异常。

机器记录：[validation.json](reports/review/v1.3/validation.json)、[independent-validation.json](reports/review/v1.3/independent-validation.json)、[overview.json](reports/review/v1.3/overview.json)。独立对账脚本原文（仅路径前缀脱敏，作为文本证据）：[independent_reconcile.py.txt](reports/review/v1.3/independent_reconcile.py.txt)。它读取实际 SQLite/CSV，不能仅凭 GitHub 小型证据重新计算所有原始 Finding。

## 6. 输入不变性与资源测量

[source-before.json](reports/review/v1.3/source-before.json) 与 [source-after.json](reports/review/v1.3/source-after.json) 逐项 size/SHA256 相等。原独立审计覆盖全部 9724 个 Phase3/4 报告文件；rootfs 两侧 8392/8595 个路径的内容、mode、UID/GID、符号链接均一致；2 个归档与 8 个分区哈希一致，errors 为空。见 [INPUT_IMMUTABILITY_AFTER.json](reports/review/v1.3/INPUT_IMMUTABILITY_AFTER.json) 与 [审计脚本文本](reports/review/v1.3/audit_immutable.py.txt)。本次提交仅复用该只读核验记录，不再重读整套镜像；当前测试只使用独立临时目录中的合成输入。

完整生成 wall **2323.513 秒**、峰值 RSS **367009792 B（350.01 MiB）**，最终输出约 **6.578 GiB**。测量用 monotonic wall、`resource.getrusage` 的进程峰值和进程树 RSS 采样；磁盘为文件逻辑长度及 `st_blocks*512` 分配量。测试用 `/usr/bin/time -v`。详细阶段和资源样本已提交，见 [run.json](reports/review/v1.3/run.json)、[stages.json](reports/review/v1.3/stages.json)、[resource-samples.jsonl](reports/review/v1.3/resource-samples.jsonl)、[FINAL_ARTIFACTS.json](reports/review/v1.3/FINAL_ARTIFACTS.json)。

披露边界：一次只读顺序预读花费 624.213 秒，已包含在生成 wall 内；导航索引修复另用 27.758 秒；输入审计耗时含受控暂停。均非冷缓存基准。真实浏览器 glibc 详情约 4.98 秒，Linking 列表约 2.41 秒。保留先前测试选择错误、索引修复前超时及中断说明，不把失败尝试抹去。详见 [V1_3_PERFORMANCE.md](V1_3_PERFORMANCE.md)。

## 7. 浏览器实现、安全边界和审查重点

- `report_browser.py`：标准库服务只绑定 127.0.0.1；SQLite `mode=ro`；参数化查询、列/排序白名单；UI 50/API 最多 100 行，SQLite 20 秒进度期限；窄导航索引先选 ID 再取详情，较重 coverage/evidence 仅详情返回。重点审查筛选、分页总数和超时边界。
- `enhanced-report.js/html`：用文本节点呈现不可信字段，静态 HTML 转义，无外部 CDN；Host 限制、CSP、nosniff；不支持写操作。证据路径必须位于原报告 evidence 子树；固定资产/CSV 白名单，拒绝穿越。该服务不是经过认证的公网、多用户或任意恶意报告隔离服务，不应对外暴露。
- `report_io.py`：有界 JSON 解码、资源停止条件、CSV 公式前缀处理；重点审查异常大单条记录和流式边界。
- `report_store.py` / `report_symbols.py`：原载荷/ID/状态保留、canonical ELF、共享所有权、完整与 observed 计数、歧义配对、符号多属性变化。动态导出不等于 Public API；等量不证明兼容。
- `report_groups.py` / `report_enhance.py`：导航组保留需求、方向、状态、provider、全部成员；对账和源文件不变性；不可把组数降低理解为风险降低。

仍有限制：缺失 SDK/debug/loader/runtime 证据、未记录 hardlink、原 evidence 绝对路径可移植性、单机浏览器测量、重详情延迟、I/O 生成成本，以及 5 项可选集成未执行。`file://` 只支持静态概览，完整交互需本机只读服务。详见 [V1_3_KNOWN_LIMITATIONS.md](V1_3_KNOWN_LIMITATIONS.md)。

## 8. 交付文件与排除项

下表列出相对 PR base 的所有提交文件及用途（源码前缀以完整相对路径表示）。`EVIDENCE_MANIFEST.json` 记录复制来源、原 SHA256、发布后 SHA256 和仅路径前缀替换；原文件未修改。新证据全部为小型 UTF-8 文本。

| 完整相对路径 | 分类 | 用途 |
|---|---|---|
| `.agents/skills/tizen-image-compatibility/SKILL.md` | v1.2 RC + v1.3 docs / documentation | RC 证据入口；v1.3 离线报告操作说明 |
| `.agents/skills/tizen-image-compatibility/assets/enhanced-report.css` | v1.3 / source | v1.3 浏览器样式 |
| `.agents/skills/tizen-image-compatibility/assets/enhanced-report.html` | v1.3 / source | v1.3 静态概览与交互页面骨架 |
| `.agents/skills/tizen-image-compatibility/assets/enhanced-report.js` | v1.3 / source | v1.3 搜索/筛选/排序/分页和详情渲染 |
| `.agents/skills/tizen-image-compatibility/references/correctness.md` | v1.2 RC / documentation | RC ARM 与符号解析完整性边界 |
| `.agents/skills/tizen-image-compatibility/references/execution.md` | v1.2 RC / documentation | RC 自定义 Probe 调度与 ARM 目标核验规则 |
| `.agents/skills/tizen-image-compatibility/references/packages.md` | v1.3 / documentation | v1.3 包统计、canonical ELF 与 UNKNOWN 计数规则 |
| `.agents/skills/tizen-image-compatibility/references/report_schema.md` | v1.2 RC + v1.3 docs / documentation | RC 完整度/预览契约；v1.3 索引与导出字段 |
| `.agents/skills/tizen-image-compatibility/scripts/compat/core.py` | v1.2 RC / source | RC collector 版本与 manifest 完整度类型校验 |
| `.agents/skills/tizen-image-compatibility/scripts/compat/elf.py` | v1.2 RC / source | RC ARM ABI/ISA 分离、readelf 完整证据采集 |
| `.agents/skills/tizen-image-compatibility/scripts/compat/linker.py` | v1.2 RC / source | RC 缺失解析完整度不授予验证信用 |
| `.agents/skills/tizen-image-compatibility/scripts/compat/package_analysis.py` | v1.2 RC / source | RC 新增包 ADDED/UNKNOWN 分类 |
| `.agents/skills/tizen-image-compatibility/scripts/compat/report.py` | v1.2 RC / source | RC Missing Interfaces 过滤后限量及总数 |
| `.agents/skills/tizen-image-compatibility/scripts/compat/report_browser.py` | v1.3 / source | v1.3 本机只读 API、索引搜索/筛选/分页、安全边界 |
| `.agents/skills/tizen-image-compatibility/scripts/compat/report_enhance.py` | v1.3 / source | v1.3 构建编排、CSV/概览、对账与输入哈希 |
| `.agents/skills/tizen-image-compatibility/scripts/compat/report_groups.py` | v1.3 / source | v1.3 Linking 导航分组与全量成员关联 |
| `.agents/skills/tizen-image-compatibility/scripts/compat/report_io.py` | v1.3 / source | v1.3 有界流式 JSON、资源守卫、CSV 安全转义 |
| `.agents/skills/tizen-image-compatibility/scripts/compat/report_store.py` | v1.3 / source | v1.3 SQLite 载荷保留、canonical ELF/所有权索引 |
| `.agents/skills/tizen-image-compatibility/scripts/compat/report_symbols.py` | v1.3 / source | v1.3 符号统计、配对与显示差异 |
| `.agents/skills/tizen-image-compatibility/scripts/compat/testing.py` | v1.2 RC / source | RC 显式 Probe 独立调度 |
| `.agents/skills/tizen-image-compatibility/scripts/enhance_report.py` | v1.3 / source | v1.3 build/serve 命令入口 |
| `.agents/skills/tizen-image-compatibility/tests/review/rc-after.json` | v1.2 RC / test/evidence | RC 五项问题修复后实际复现值 |
| `.agents/skills/tizen-image-compatibility/tests/review/rc-baseline-tests.txt` | v1.2 RC / test/evidence | RC 开发前 120 项历史测试日志 |
| `.agents/skills/tizen-image-compatibility/tests/review/rc-before.json` | v1.2 RC / test/evidence | RC 五项问题修复前实际复现值 |
| `.agents/skills/tizen-image-compatibility/tests/review/rc-changed-files.txt` | v1.2 RC / test/evidence | RC 历史精确文件清单 |
| `.agents/skills/tizen-image-compatibility/tests/review/rc-checks.json` | v1.2 RC / test/evidence | RC 静态/配置/链接/冻结检查记录 |
| `.agents/skills/tizen-image-compatibility/tests/review/rc-scale.json` | v1.2 RC / test/evidence | RC 2000 包压力验证结果 |
| `.agents/skills/tizen-image-compatibility/tests/review/rc-source-sha256.json` | v1.2 RC / test/evidence | RC 原始冻结源码指纹 |
| `.agents/skills/tizen-image-compatibility/tests/review/rc-test-metrics.txt` | v1.2 RC / test/evidence | RC 历史测试资源测量 |
| `.agents/skills/tizen-image-compatibility/tests/review/rc-tests.txt` | v1.2 RC / test/evidence | RC 历史工具启用时 131 项测试日志 |
| `.agents/skills/tizen-image-compatibility/tests/review/reproduce_final_review.py` | v1.2 RC / test/evidence | RC 五项问题独立复现脚本 |
| `.agents/skills/tizen-image-compatibility/tests/test_correctness.py` | v1.2 RC / test/evidence | RC 合成 fixture 显式标记完整解析证据 |
| `.agents/skills/tizen-image-compatibility/tests/test_framework.py` | v1.2 RC / test/evidence | RC 合成依赖 fixture 显式完整度 |
| `.agents/skills/tizen-image-compatibility/tests/test_release_review.py` | v1.2 RC / test/evidence | RC 五项正确性正反例回归 |
| `.agents/skills/tizen-image-compatibility/tests/test_report_enhancement.py` | v1.3 / test/evidence | v1.3 新增 21 项报告回归 |
| `README.md` | v1.2 RC + v1.3 docs / documentation | RC 说明与 Cline v1.3 报告 build/serve 用法 |
| `V1_2_FINAL_REVIEW.md` | v1.2 RC / documentation | RC 五项问题处置、方法和历史证据 |
| `V1_2_RELEASE_READINESS.md` | v1.2 RC / documentation | RC 静态产品测试准备度及限制 |
| `V1_2_STATIC_ACCEPTANCE_INPUT.json` | v1.2 RC / input template | RC 拟用静态输入清单模板 |
| `V1_3_CHANGED_FILES.md` | v1.3 / documentation | v1.3 原开发精确清单及本次交付范围 |
| `V1_3_KNOWN_LIMITATIONS.md` | v1.3 / documentation | v1.3 证据、浏览器、资源与移植限制 |
| `V1_3_PERFORMANCE.md` | v1.3 / documentation | v1.3 实际生成/浏览耗时和资源方法 |
| `V1_3_REPORT_DESIGN.md` | v1.3 / documentation | v1.3 数据/存储/浏览/计数设计 |
| `V1_3_REPORT_VALIDATION.md` | v1.3 / documentation | v1.3 测试映射、实际数量与修正证据 |
| `reports/review/v1.3/CODE_PROVENANCE.json` | 发布验证证据 | 代码提交与原验证工作区 41 个文件 SHA256 对应 |
| `reports/review/v1.3/EVIDENCE_MANIFEST.json` | 发布验证证据 | 证据复制来源、双侧哈希、路径规范化说明 |
| `reports/review/v1.3/FINAL_ARTIFACTS.json` | 发布验证证据 | Final logical/allocated report sizes |
| `reports/review/v1.3/INDEX_PREREAD.json` | 发布验证证据 | Disclosed sequential read within build wall interval |
| `reports/review/v1.3/INPUT_IMMUTABILITY_AFTER.json` | 发布验证证据 | Full input hash and rootfs metadata audit result |
| `reports/review/v1.3/INPUT_PROVENANCE.json` | 发布验证证据 | 下载来源、实际大小、发布/实测 SHA256 摘录 |
| `reports/review/v1.3/PREPUBLICATION_CLASSIFICATION.json` | 发布验证证据 | 执行前 46 个变更/未跟踪文件完整分类 |
| `reports/review/v1.3/audit_immutable.py.txt` | 发布验证证据 | Actual input immutability audit script (path-normalized text evidence) |
| `reports/review/v1.3/browser-real-before-group-index.json` | 发布验证证据 | Actual browser timeout before navigation index repair |
| `reports/review/v1.3/browser-real-first-selection.json` | 发布验证证据 | Retained earlier browser harness selection error |
| `reports/review/v1.3/browser-real.json` | 发布验证证据 | Final actual Chromium routes, timings and JS errors |
| `reports/review/v1.3/full-tests.log` | 发布验证证据 | Current full suite: exact test names and skip reasons |
| `reports/review/v1.3/full-tests.time` | 发布验证证据 | Current full-suite command exit code, wall time and RSS |
| `reports/review/v1.3/independent-validation.json` | 发布验证证据 | Independent readback: 12 checks, exact IDs/member fields and fixed real counts |
| `reports/review/v1.3/independent_reconcile.py.txt` | 发布验证证据 | Actual independent reconciliation script (path-normalized text evidence, not an executable tool) |
| `reports/review/v1.3/input-audit-pause.json` | 发布验证证据 | Controlled pause included in immutability audit elapsed time |
| `reports/review/v1.3/navigation-index-count-interruption.json` | 发布验证证据 | Retained failed pre-count during navigation index repair |
| `reports/review/v1.3/navigation-index-evidence.json` | 发布验证证据 | Index-only repair and query plan, group count unchanged |
| `reports/review/v1.3/overview-refresh-evidence.json` | 发布验证证据 | Display-only original-status repair, DB/CSV unchanged |
| `reports/review/v1.3/overview.json` | 发布验证证据 | Image/package/ELF/symbol/linking summary and preserved outcome |
| `reports/review/v1.3/rc-tree-tests.log` | 发布验证证据 | Isolated staged RC tree complete suite |
| `reports/review/v1.3/rc-tree-tests.time` | 发布验证证据 | Isolated RC tree command exit code and resource metrics |
| `reports/review/v1.3/resource-samples.jsonl` | 发布验证证据 | Recorded build resource samples and peak/limit measurements |
| `reports/review/v1.3/run.json` | 发布验证证据 | Completed build wall time, RSS and output sizes before navigation repair |
| `reports/review/v1.3/source-after.json` | 发布验证证据 | Original report top-level file size/SHA256 after enhancement |
| `reports/review/v1.3/source-before.json` | 发布验证证据 | Original report top-level file size/SHA256 before enhancement |
| `reports/review/v1.3/stages.json` | 发布验证证据 | Measured build stage durations |
| `reports/review/v1.3/validation.json` | 发布验证证据 | Build reconciliation: 23 checks, status histogram and full CSV counts |
| `V1_3_REVIEW_HANDOFF.md` | 发布文档 | 确切代码提交、全文件用途、测试/真实报告证据与审查重点 |

未提交的仓库文件只有 `design.md`、`require.md`，内容与发布前 SHA256 相同。独立工作目录中的镜像、rootfs、分区、RPM 数据、巨型报告/CSV/SQLite、临时缓存、测试临时目录及浏览器配置均不加入 Git；未使用 Git LFS。GitHub 上的小型记录支持审查方法、逻辑和结果摘要；完整数据级复算仍需原始本地输入。

评估：**可进入独立代码审查，保持 Draft**。只发布新 review 分支，不修改 main 或旧 1.2 review 分支，不合并任何 PR。所有具体兼容性结论继续以原始报告及其 UNKNOWN/覆盖范围为准。
