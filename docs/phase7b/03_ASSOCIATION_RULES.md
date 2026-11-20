# 关联、传播、聚合与验证建议

## 独立判定轴

| 字段 | 定义 |
|---|---|
| 原 Finding status/severity/confidence | 原检测结果，保留原载荷和分类。组展示成员分布，禁止覆盖 |
| Edge strength | `DIRECT` 为已观测的精确关系，例如 DT_NEEDED 声明或模型内已选 Provider。`INFERRED` 有明确推导和前提，例如同 root 的路径拼接。`UNKNOWN` 表示关系证据不足、冲突或不可比 |
| Consumer assessment | `CONFIRMED_CONTRACT_IMPACT` 表示可比静态上下文中已证明的具体基线契约受影响。`POSSIBLE_IMPACT` 表示有正向线索但缺决定性条件。`UNASSESSED` 表示无可定位关系或证据门槛不足。`NO_BREAK_OBSERVED` 表示在两侧同一项完整对照中仍满足要求 |
| Group risk | 按影响分布给验证优先级。`HIGH` 为存在已确认的 HIGH/CRITICAL 契约影响。`MEDIUM` 为有其他已确认影响或高严重度且有具体路径的潜在影响。`LOW` 为其余有实际线索的候选。无可判定证据为 `UNASSESSED`。原 severity 完整保留 |
| Validation | 初始 `PROPOSED` 或 `BLOCKED_INPUT`。后续阶段可附授权 receipt 跟踪 `VERIFIED`、`FAILED` 或 `INCONCLUSIVE`。探针失败属于自己的结果，原 Finding 和旧影响运行保持可复核 |

组的 `evidence profile` 输出 DIRECT/INFERRED/UNKNOWN counts 和缺失前提。组同时有已确认和未评估消费者时显示两个计数，不用一个置信分填平差异。静态确认只针对该运行和约束。

## 必要门控与可接受的源证据

确认直接影响需全部成立：

1. 目标方向为 baseline 消费者在 candidate。已识别编译目标和消费对象，loader 查找环境与基线对照配对，root 身份、namespace/作用域和源权限证据可追溯。双方启用的必要配置分别记录，允许镜像本身的合法差异。容器策略、运行凭据或另一个根的选择未知时不得借用。
2. 可信基线记录证明相同消费者、同一原始义务在原启动环境中满足。符号变化还需证明旧 export 对应的是被选中的定义。若 baseline 已失败，标记 `PREEXISTING_BASELINE_FAILURE`，保留 candidate 的直接失败事实，不归因为迁移变化。
3. 可信的 candidate 原失败 Finding，且与观察的需求、作用域和结果完全一致。需原状态 `INCOMPATIBLE`、解析器实际门控满足、相关完整性证据适用。候选 trace 若给出与原状态冲突的结果，记录 `SOURCE_TRACE_CONFLICT`，当前原运行内保留未确认。补跑产生的新事实要使用新运行和新证据。
4. 对跨版本文件配对，受影响变化归因必须指向明确安装路径或经验证的别名/配对证据。若仅能证明当前需求失败，允许建立以需求为锚点的组，组不能声称某个变动 Provider 是其根因。独立 scope 分类与真实运行动态行为不参与升级。

历史报告中明确的解析失败可按原状态展示。若缺 2 或上下文来源缺失，只在有明确相关事实时列潜在影响。中间依赖候选或无归属包不能令有效 ELF 级直接确认降级，也不能把未知 Package 归属升为确认。程序启动成功或完整 API 可用均超出本模型。

## 规则表

| 场景 | 证据与关系 | 反例或降级 |
|---|---|---|
| DT_NEEDED | 原 `check_id` 和 manifest `needed` 证明直接引用。已选对象取 resolver 结果和其决策依据 | 只在文件表找到同 basename/SONAME 的库，不建立已绑定边。对某库有 DT_NEEDED 不等于消费其全部符号 |
| 缺少 Provider | 在已知作用域、完整搜索与元数据中接受原 `missing_provider/unresolvable_provider + INCOMPATIBLE`。边可无目标，保留需求及解析检查 | `dynamic loader` 可能写 `missing_provider` 但原 status 为 UNKNOWN。缺 cache、孤立 DSO 或未记录策略时不确认 |
| 缺符号与类型错误 | 精确 import、版本约束、binding/type、已选基线定义和同需求的候选失败，支持直接影响。成对数据 size 的 ABI Finding 本身仍保留 | 只有 ABI 删除而没有实际基线绑定、替代 Provider 仍满足要求、非默认版本 fallback、弱引用、IFUNC/UNIQUE/protected 或多匹配未知，不能确认该消费者失败 |
| Symbol Version | 区分 verneed 约束和 import 选择。保留 `version_file` 与定义节点、`@`、`@@` 和未版本化 null，使用 resolver 的实际版本语义 | 独立的版本名相同不意味着来自相同 Provider。旧默认版本失效不能误计为同名显式版本也不可用 |
| SONAME 变化 | 原变更 Finding 可以聚合自身契约。历史匹配、可执行的别名与解析成功对应原证据 | 改名本身不证明失败。同 SONAME 的多个路径在不同 root 中可能选择不同对象 |
| Provider 替换或歧义 | scope 已建立、同精确要求经替代选中且匹配时记录 `NO_BREAK_OBSERVED`。独立记录替换来源。多匹配只保存候选与原因 | 路径相同不能视为相同构建，符号计数相同不能证明合同，原代码的第一匹配在 UNKNOWN 时只是观察 |
| 已装载 SONAME 复用 | 同 root/base namespace 的有效首选决策，引用原已装载对象的决策和请求名或 SONAME 命中 | 历史只记录 Provider 路径，通常缺首次装载原因。无 trace 不标为已证明的复用事件，也不产生不存在的二次查找失败 |
| RPATH / RUNPATH | 只消费原 resolver 的候选顺序、继承与命中。新增 trace 可记录路径类别、继承来源和判定前提 | 禁止对所有 rpath/runpath 合并搜索。无法扩展 token、候选不完整或跨 root 复用，记录 UNKNOWN |
| secure-execution | 上下文引用实际消费者来源的 mode/capability 元数据，并保留 candidate 查找配置。复用 Phase 7A 门控 | baseline setuid、capabilities 或来源未知时，不以 candidate 同名文件补状态。静态 mode 无法证明实际 AT_SECURE |
| Header | 直接沿用原路径、include reachability 及完整度。产品声明目录只是范围线索。SDK 与 runtime 按 scope 隔离 | 未盘全 Header 的缺失、include 条件不明保持未知。`PROVEN_PRESENT` 的迁移不会被据路径重判删除。除已有消费者编译证据外，只关联验证建议 |
| 弱引用、dlopen/dlsym、未知路径 | 保存弱引用是否缺失的观察。动态加载仅记录明确的现有证据或建议探针 | 弱引用缺失不等同于强符号契约失败。字符串命中、SONAME 相同和间接依赖均不能证明 dlopen/dlsym 实际发生 |

版本和 Loader 规则沿用 Phase 7A 判断。`complete`、`export_inventory_complete`、`resolution_metadata_complete` 有不同用途。缺字段、错误 ARM PCS、权限或作用域未知都不能获得新信用。对无需导出观测的路径型关系仍可保留原声明事实。

## 图传播

使用 `DECLARES_NEEDED`、`SELECTED_PROVIDER`、`BASELINE_IMPORT_BINDING`、`CANDIDATE_REQUIREMENT_CHECK`、`VERSION_REQUIREMENT` 和 `ROOT_REACHES`。路径只沿同 context 的已知选择边，从已观察的直接受影响 Consumer 向当前根反向搜索。声明边可用于标注潜在路径，不计入已选链。UNKNOWN 边以缺失前提结束路径，留下缺口原因，禁止穿过继续推测。root 通过其他不相关命名空间到达同 ELF 时不可合并。

按 `(ctx,node,传播模式)` 去重，最多 8 跳、每次查询扫描 10000 条边、保留一条字典序稳定的最短见证及最多两条同长可解释替代。按稳定 ID 扩展相邻节点，节点访问不枚举路径组合。循环边能保留在直接事实里，见证不重复顶点。达到界限返回 `PARTIAL / TRAVERSAL_LIMIT` 和已观察结果。对 `RECORDED` 尚未证实父边来源的路径明确标为推导。所有多跳结果不能超过 `POSSIBLE_IMPACT`。即使底层 Finding 为已确认，根影响仍需自己的直接证据才能单独确认。

## 归组和独立计数

合并需规范键完全一致。允许已证同一旧导出删除对多个直接 Consumer 的重复 Finding 共享一组，版本缺失和 import 缺失只有在 trace 明确指向同一失效约束时才能挂到同一候选。共享某段链、同一 Package、多 Finding 同类文本、多个 UNKNOWN、不同运行方向、不同版本/ABI 或执行条件均不构成等价。SONAME 改名和具体符号消失默认独立。多因关系允许一个源成员关联多个候选，反向追溯从原 ID 展示全部组。无法证明等价时保持独立，以说明群组仍是根因候选。

独立报 `COUNT(DISTINCT finding_id)`、`SUM(occurrences)`、`COUNT(group_id)`、`COUNT(group_id,finding_id)`、按作用域去重的 Consumer/Root/Package。不用按角色的和替代并集。每个组可分别统计同 ELF 在不同 context 下确认、可能及未知的项。Package 的角色来自 installed ownership 和原路径证据，包页只给已确认/可能涉及哪些组件、未映射原因和未验证项。Provider 角色不会被自动计为受影响 Consumer。`UNASSESSED` 与完整输入下合法的“无观测到消费者”分开。

## 接口范围

三态为 `PUBLIC`、`INTERNAL`、`UNDETERMINED`。优先级为具名产品维护者签发的精确规则 → 已匹配版本/架构/SDK 的公开契约清单 → 明确覆盖范围的受信产品元数据。安装路径、包名、符号前缀、导出 visibility 和 RPM tag 单独仅作筛选提示，默认未判定。每条规则带来源、版本或摘要、image/arch/scope、精确接口匹配和 ID。两条同级矛盾，或配置与受信记录冲突且无注明的批准覆盖规则，保留全部来源和 `UNDETERMINED/CONFLICT`。分类不修改影响或兼容性，不隐藏 INTERNAL 问题。

## C++ Runtime 边界标注

| 可观测事实 | 可提取线索 | 待证行为 |
|---|---|---|
| 同可信闭包中的 libstdc++、libc++、libc++abi、libgcc_s、libunwind 选中路径，DT_NEEDED、GLIBCXX/CXXABI 版本、含 unwind 的节 | 多 runtime 或 ABI 家族同时出现在同 root，可标记 `MIXED_RUNTIME_CONTEXT`。仅在同约束边界有类型/符号证据时标记接口暴露候选 | 搜索优先、interposition、跨 DSO 分配/析构与对象生命周期 |
| RTTI/vtable 顶层名、原 mangled 匹配、可见的 stdlib 类型、异常 personality 符号、EHABI/其他 unwind 节 | 符号名空间或版本提示风险，不能证明参数 ABI、函数实现或对象实际跨边界。脱符号仍 UNKNOWN | dynamic_cast、typeinfo 等价、异常跨 DSO、ARMv7 展开行为 |
| 已观察的 pthread_cancel、_Unwind_ForcedUnwind 导入和相关运行库 | cancel/forced unwind 路径候选，符号出现不证明调用链可达 | 线程清理、异常路径、forced unwind 传播与目标行为 |

标注不改变原始状态。不同 runtime 实现、名称不匹配或 RTTI/异常元数据不足，产生对应验证动作。后续可用 DWARF 或产品声明的 C ABI 边界缩窄待验范围。

## 后续验证动作

| 动作 | 触发、环境与目标 | 预期回执 |
|---|---|---|
| `ABI_LAYOUT` | 同接口 type/OBJECT/TLS 或 C++ 布局疑问。两侧同产品 ELF、匹配 Build-ID debug 和 libabigail | 工具版本、输入摘要、ABI 差异、结构和退出码 |
| `HEADER_COMPILE` | 入口迁移、条件或 SDK 归属未证。两 SDK/编译器、ARM float ABI/宏，使用指定公开入口编译调用 | 工具链身份、命令、目标 ELF 信息、编译输出及前置基线结果 |
| `VERSION_LINK` | 缺定义节点、非默认版本或替代 Provider。匹配 sysroot/linker/target，验证指定版本/路径 | 精确符号、版本节点、工具链输出及输入哈希 |
| `DYNAMIC_LOOKUP` | dlopen/dlsym/namespace 或选中顺序未知。授权设备或匹配隔离镜像，记录参数与安全环境 | loader trace、可重现退出状态、Provider 或失败上下文 |
| `CPP_BOUNDARY` | C++ family 混用、RTTI/EH、ownership 或 forced unwind。经产品批准的跨 DSO 场景和目标 runtime | ABI 家族、测试路径、RTTI/EH/析构/取消观测及可信 receipt |
| `TLS_PROBE` | TLS 类型/数据 size 或线程并发疑问。匹配目标环境与复现 DSO | 初始化、生命周期和多线程读取结果 |
| `LOADER_CONTEXT` | cache/RPATH/hwcaps/secure-execution 或首次装载未知。真实设备/明确配置的 loader 模型 | search/namespace/credentials 证据及解析记录 |
| `PACKAGE_SDK_CHECK` | Installed ownership 或 SDK peer 缺失、路径替代待证。对应 RPM DB/SDK 和产品清单 | 归属、范围、版本、映射证据且保留歧义 |

`action_id` 由 group、可选 consumer/context、kind、目标约束与版本产生。动作从组透过 `group_finding`、从影响透过 `impact_basis` 回到精确原 ID。结果作为独立带来源 receipt 引用 action_id、run/环境及 Evidence 摘要，后续评估读取这些结果并保留原观察。Phase 7B 只提出验证任务。
