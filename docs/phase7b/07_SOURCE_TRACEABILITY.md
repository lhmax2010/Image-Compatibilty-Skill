# 基线、资料追溯与设计检查

2026-11-19 核对了私有仓库 `git@github.com:lhmax2010/Image-Compatibilty-Skill.git` 的 `HEAD`、`refs/heads/main` 及本地 HEAD，均为 `f72a246fbce64b6e9ee2341464cbc067b5981c37`。该提交继承 `924ef9f5123cf3cbce9df181420f9f716c7ea476` 并包含 Phase 7A 修复。任务附件里“主分支旧、13 项未提交”的状态来自迁移前，本设计以实际提交为准。历史源码路径定位以此版本为准，未改动旧证据。

## 调用链与数据

下表的 `scripts/` 相对路径均位于 `.agents/skills/tizen-image-compatibility/`，名称和行号对应核对后的基线。

| 主题 | 已核对的源码和现有事实 | Phase 7B 决策追溯 |
|---|---|---|
| Static 与告警 | `scripts/tizen_compat.py:45::main` 处理镜像/manifest，采集后调用 `compare_static`、可选 `advanced_abi`、`finalize` 和 `build_results/generate`。`scripts/compat/compare.py:197` 两次链接检查为 candidate 原生、baseline→candidate，均查 candidate providers | baseline 自身对照为新增观察，现有 manifest-only 比较是一次重新判定，历史归组直接读原结果 |
| Finding ID/状态 | `scripts/compat/core.py:264::finding` 对规范 payload 取摘要短前缀。`linker.py:45::emit` 加入 root/consumer 等后重新计算。`compare.py:258::finalize` 识别同 ID 异载荷并记录 occurrences。`report.py:16::build_results` 加入 package ownership 并维护原观测/决策。`coverage.py:75::coverage_report` 与包结果参与原 gate | 原 ID 以源运行限定，从最终 payload 取 hash，不能根据已追加的 `package_ownership` 等字段逆推旧 ID。另建 group ID/影响证据 |
| ELF、ABI、版本 | `scripts/compat/elf.py:13::parse_readelf` 收集 imports/exports、version_file、.dynamic 需求、RTTI/节和 TLS。`elf.py:103::collect_elf` 分清 ELF、导出和解析完整度。`elf.py:170::symbol_identity` 保留 `@/@@`。`elf.py:175/192` 处理 ARM ABI 及匹配。`compare.py:40::compare_elf` 缺导出门控与数据 size/type。`debuginfo.py:33::advanced_abi` 需要可用 root/debug 与工具 | 沿同一对象、来源和精确版本构建关联。ABI 修改与 Consumer 影响独立。无实际工具结论的布局问题生成建议 |
| Header | `scripts/compat/source.py:99::header_inventory_complete`、`source.py:115::declaration_reachability` 负责采集/受限包含图。`compare.py:128::compare_api` 输出差异和证明边界。`semantic.py:8/26` 接现有辅助语义探针 | 不重新解释缺失，保留可达性与 UNKNOWN。无既有编译记录的消费者需要 SDK 验证 |
| Dependency/Linker | `scripts/compat/linker.py:34::dependency_checks` 管理 per-root queue、seen、closure、edges、loaded、loaded_proven。`linker.py:68–83` 识别原消费者上下文，`linker.py:116–168` 管理路径、顺序、命中和 reuse。`linker.py:192–228` 解析版本、imports 和特殊符号 | 已有检查可直接读，首次载入事件和基线绑定需 observer 或可信新 trace。对路径去重及不明作用域保守处理，7B 不实现并行 resolver |
| 包及角色 | `scripts/compat/packages.py:56::collect_package_inventory` 区分已安装与可用 RPM。`package_analysis.py:10/15/43/60` 负责 NEVRA identity、installed ownership、单/多 owner、SDK scope、命中与 peer。`report_store.py:227::_finding` 生成 consumer、root、provider 角色 | 复用侧/范围/包身份与原状态。legacy `affected_package_count` 是已关联包的并集，不能当真正受影响包 |
| SQLite 与归组 | `scripts/compat/report_store.py:47::Store` 建表，`:136::read_manifest` 分批索引，`:227::_finding` 保存压缩 payload、hash 和引用，`:283::read_results` 读取原 schema 1.2。`report_groups.py:16::build_groups` 统计导航成员和角色。`report_symbols.py:31/81` 配对、导出差异、各类 size 观察 | 使用原表只读适配，侧车独立。canonical ELF/旧 pair 是观察索引，不能隐含导入绑定或稳定产品 lineage |
| 原报告与校验 | `scripts/compat/report.py:56::generate` 保存原结果、manifest、CSV、HTML。`report_enhance.py:212::build` 先后写增强索引和输出，`:68::validate` 核对逐条原 CSV hash、payload 和统计。`report_io.py:53/66/145` 负责 CSV 安全、资源 guard、流式读取 | 延用原校验和语义，侧车引入新事务、断点与资源目标。整体吞吐和恢复尚待测 |
| Evidence / HTML / API | `scripts/compat/core.py:205::Tools.run` 保存工具证据。`report_io.py:14::evidence_path` 检查相对 Evidence 子树。`report_browser.py:14/30/130` 以 SQLite ro 模式处理白名单查询和文件，`assets/enhanced-report.js:139` 查询既有 Finding | 复用旧 Evidence 与 Finding 深链接。新视图单页加载，拒绝任意文件和任意 SQL |
| Manifest 与缓存 | `scripts/compat/core.py:16/17/280` 版本与迁移、校验旧字段。`collect.py:188::elf_job` 以版本、mode、virtual path、内容哈希、readelf/nm 键复用。`collect.py` 在缓存外关联消费者权限 | 旧标记缺失保持 UNKNOWN。新 trace 缓存以双方身份和上下文约束，侧车失败不改变原缓存 |

## 已读取的历史材料

下列 Phase 6 和 Phase 7A 文件从用户指定目录只读查看，当前七份设计不复制原产物。共有五份指定 Phase 6 材料和七份指定 Phase 7A 材料可读。

| 阶段 | 文件 | 用于哪项设计 |
|---|---|---|
| 6 | `02_CAPABILITY_AUDIT.md` C03–C14、C22–C27 | 识别 ABI、包关系、浏览器的可复用能力及局限 |
| 6 | `03_CORRECTNESS_FINDINGS.md` F01–F05 | 关联、评估的五个正反回归门控 |
| 6 | `04_COVERAGE_GAPS.md` | ARM PCS 与 ISA/C++ Runtime 的边界，原计数口径 |
| 6 | `05_DEVELOPMENT_ROADMAP.md` | 影响关联优先，后续 SDK、目标运行及发布和产品门禁单独处理 |
| 6 | `06_PHASE7_DESIGN_PROPOSAL.md` | 语义 ID、只读 sidecar、角色、不越级及风险关联方向 |
| 7A | `01_FIX_SUMMARY.md` | 将采集/导出、包含图、SONAME 和安全来源门控接入关联 |
| 7A | `02_CODE_CHANGE_REVIEW.md` | 核对被修函数、报告层完整度门控及缓存版本 |
| 7A | `03_REGRESSION_RESULTS.md` | 历史回归数、前后结果、小报告和资源测试，不算此轮实测 |
| 7A | `04_BEHAVIOR_CHANGE.md` | 原状态可因不同版本重跑变化。历史库重投影保持各自源 ID |
| 7A | `05_V1_3_COMPATIBILITY.md` | 旧 API、SQLite 和字段保持契约。新完整度 gates 不追改旧报告 |
| 7A | `06_REMAINING_RISKS.md` | 条件 Header、loader/namespace、部署权限和 target 不确定性 |
| 7A | `07_PHASE7A_ACCEPTANCE.md` | 五项修复历史验收通过的范围、证据路径及未验证项 |

Phase 6 源目录为 `/home/linhao/lss/tizen-static-acceptance/20261118/phase6-audit-924ef9f/`。Phase 7A 为 `/home/linhao/lss/tizen-static-acceptance/20261118/phase7a-static-fixes-924ef9f/`。跨工作机可先从仓库 [Phase 7A 交接](../PHASE7A_HANDOFF.md) 取得源位置和语境。外部目录仍为只读引用。

历史实际量级来自仓库 [v1.3 验证](../../V1_3_REPORT_VALIDATION.md) 及 [交接证据](../../V1_3_REVIEW_HANDOFF.md)。`134402` 具体是 Linking 导航组，角色是组内投影。`322036` 是符号差异记录数，非镜像唯一符号。历史 Linking 的 `855522` 条全部 UNKNOWN，无法用作确认路径的正例。任务所述 30 分钟指 `V1_3_FINAL_PERFORMANCE.md` 的 1811.156s 重建记录，RSS 350.90 MiB，SQLite 6086623232 B、CSV 1082027727 B、报告分配约 6.677 GiB。仓库 [性能报告](../../V1_3_PERFORMANCE.md) 的 2323.513s 来自另一历史构建。选用前者作量级参考，两个版本均非本轮结果。

## 新增设计假设

- 新的 root trace 可在保持现有 resolver 输出一致的前提下观察到足够的来源和上下文。历史压缩对象对部分查询可复用，但不能保证闭合身份、可信适用条件或首次加载路径。
- 一个源报告独立侧车可用窄表覆盖所有源 ID，典型 fanout 下可满足目标资源约束。产品尚未锁定参考机和确认覆盖范围。
- 受信接口范围表及可比 baseline 对照是可选输入。缺失时仍可完成受限分析，保留未知的角色、范围和影响。真实 ARM 运行行为由后续阶段验证。

## 本轮实际检查

- 只读核对远端和本地基线、12 份指定历史文档、原调用链和数据模型。对照原 `Store` DDL 在内存创建 SQLite，检查实际 Findings、raw ELF、角色列；另在内存执行本文提出的侧车 DDL。
- 在侧车内存库插入一个缺少候选 Provider 的小样例，核对组到原 ID 回查、`foreign_key_check` 及 `quick_check`。重复成员、悬空成员和多跳确认影响插入均被拒绝。最小包→组查询命中 `group_by_package` 覆盖索引。此项只验证结构约束与微型 SQL 查询。
- 使用本机 `jsonschema` 校验概览 Draft 2020-12 结构，测试模拟 1.0 实例和拒绝未知版本。七份文档的相对链接、代码块、空白与 Git 变更范围已核对。
- 未新跑 193 项回归、实际镜像采集、历史真实侧车或浏览器。新增 resolver observer、全量恢复及资源预算留待实施验证。工作树只增加 `docs/phase7b/` 下七份 Markdown，未 Commit、Push、Merge，也未进入生产实现。
