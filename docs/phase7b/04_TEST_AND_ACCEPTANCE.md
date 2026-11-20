# 测试与验收计划

以下为实施后的门槛。Phase 7A 的 193 项、188 PASS、5 SKIP、0 FAIL（35 项新增）属于既有结果。本轮仅设计检查，执行记录见 [追溯与检查](07_SOURCE_TRACEABILITY.md)。

## A–E 核心用例

每个 fixture 同时保留原 payload/CSV 和期望的侧车逻辑转储。用独立 oracle 对完整集合按稳定公开 ID 比较。除了计数，还核查结论及来源上下文。

| 组 | 输入与反例 | 自动验收 |
|---|---|---|
| A 基础 1 | 单个选中 Provider，1 个 Consumer 的强 import 命中旧版本，candidate 缺导出；增加第二个相同 Consumer | 两案分别一组 1/2 个确认影响，保留全部 Finding ID。比较索引和手写 gold edges |
| A 基础 2 | 两个同 SONAME Provider，次序不同的两个 root；一案仅查到未选候选 | 选中的 path 与 context 逐个对账，多候选无证时 UNKNOWN，不交叉绑定 |
| A 基础 3 | 无 Provider 的真实失败；无 Consumer 的 ABI 删除；同一包不同角色和双 owner | 缺 Provider 的 edge 目标为 null，完整基线情况下仍有确认影响。无 Consumer 的失败保留，影响不造 0 风险。按 side/scope/role 多值核对，冲突归属标志保留 |
| B 判定 1 | 完整 dynsym 的强符号删除 vs warning/截断/未采完；真实 OBJECT/TLS 尺寸改变 vs FUNC 代码大小变动 | 完整候选失败和相关确认影响保留，缺完整度仅降级影响。已观测 size/type finding 原样保留，代码大小仅观察 |
| B 判定 2 | 完整 Header 真删、失败遍历、迁移到可证明可达的 include、条件宏未知 | 真删 Finding 仍失败，但无调用证明不确认 Consumer。迁移保留原可达性及新建议，未知不得转删除 |
| B 判定 3 | 同 root SONAME 别名复用、另一 root/namespace、RPATH 继承/RUNPATH 直接、加载顺序变化及 baseline 04755 vs candidate 0755 | 复用原有 7A fixture，与启用 observer 前后输出逐字段比较。跨上下文无复用，权限证据归属一致，候选环境 UNKNOWN 不升级 |
| B 判定 4 | 同 symbol 但 verneed 节点或文件不符、默认版去掉仍保留显式版、weak import 与有替代、DT_NEEDED 加 dlsym 字符串 | 精确失败与未证依赖分别保留。版本键互不污染，弱和字符串只产生符合规则的建议 |
| B 判定 5 | candidate 只有 `resolution=missing_provider` 但原 UNKNOWN；baseline 同一约束已失败；candidate trace 与历史 Finding 矛盾 | 无额外确认，原因分别为原失败前提缺失、`PREEXISTING_BASELINE_FAILURE`、`SOURCE_TRACE_CONFLICT`。源不可改写 |
| C 聚合 1 | 一导出变化多 Finding，多根因同 Consumer，同链不同约束，两个不同 Finding 指向同组 | 原数、重复观察数、组数、成员数分别满足 gold。用反向链接查出所有原 ID |
| C 聚合 2 | diamond、循环和高分叉，8 跳边界，未知分叉，同组混合确认/推断 | 有界遍历，最短见证稳定，PARTIAL 带原因，间接确认数为 0。局部确认及未知均保留 |
| C 聚合 3 | 交换镜像，同名 arch 不同 PCS，正向迁移/反向及 candidate 自身失败同路径 | 方向 ID 独立，ABI 不匹配或缺 ARM 证据不跨用，确认只来自同一检查方向 |
| C 范围与 C++ | 精确 public rule、两同级冲突、路径启发式、共享多个 runtime 但没有跨 DSO 边界证明 | 默认 UNDETERMINED，冲突来源可见，INTERNAL 不删记录，输出可行建议而不创造 ABI 失败 |
| D 一致性 | 同输入乱序处理、全量 vs 恢复、同成员重复 vs 同 ID 异载荷、缺 source artifact、未知旧版本 | 公开 ID、逻辑输出摘要和引用集合一致，异载荷拒绝。独立重排源文件时另外验证 group/edge 逻辑键稳定，原字节身份随内容变化。旧源与旧 HTTP routes 逐字节/状态核对 |
| D 报告 | 所有新过滤、50/100 分页、分组成员、从新视图跳旧 Finding、Evidence 断链 | 用 API / CSV / SQLite 交叉比对实际原 ID 与原 status。全页遍历无重复缺漏，正反链接可逆 |
| E 非法输入 | 损坏 SQLite、坏列、重复键、超长 JSON/压缩记录、循环 alias、无效 Evidence/越界 symlink、悬空 FK、未知 schema | 在预算内拒绝或记录明确不可用；源 hash 不变；API 保持有效分页，输出逃逸与 CSV 公式转义正确 |
| E 中断与互斥 | 在导入、trace、关联、索引、导出和发布前注入终止；另开构建进程写同目录 | 事务内数据与 checkpoint 一致，恢复可重放。读者只看完成标记，第二写者退出。不同输入摘要拒绝续建 |

源防回归要求保留 7A 全套自动化门禁，重点对照公共头、dynsym、loader reuse、安全上下文五个修复以及真实不兼容正控制。增加同一入口启用/关闭观察器的结果等价测试，排除观察改变 resolver 顺序。目标工具或设备没有就记录 SKIP 原因，报告实际执行项。

## 复用历史数据的初步验证

1. 选用历史报告的双 manifest、results/CSV、Evidence 或已校验 v1.3 索引。用只读连接或流式读取，记录 SHA 与行数。若要对 workspace 外报告构建侧车，输入按授权范围只读，侧车和所有临时文件写入 workspace。
2. 从规模数据选 200 个固定种子分层样本。优先覆盖 Provider/版本/导入检查、unknown_search_environment、跨方向重复、多个 owner、unassigned、证据缺失与小/超大导航组。不存在的失败类别记录样本层为空，并用合成数据补覆盖。样本查询保留各层总数与抽样分布，选根时包含所需邻接上下文。分区截断和未知仍可见，抽样不用于估计整体影响人数。
3. 用历史数据验收关联引用、回跳、覆盖下降及计数，不要求历史数据出现确认影响。用合成的新 Phase 7A manifest/control 独立验证确认分支。可选用匹配 manifest 重放现有模型，使用新目录且避免采集镜像。
4. 独立对账先验源码原 ID 集，再用原报告验收已存的 898342 Finding、855522 Linking、11111 Unassigned、722/736 Package、134402 Linking 导航组、322036 符号差异行。上述规模以旧输入为准。Phase 7A 后新跑另建计数，不设置与历史相等的门槛。

## 性能预算

历史参考是既有 v1.3 约 30 分钟、350.9 MiB 峰值 RSS、SQLite 约 6.09 GB、CSV 约 1.08 GB、报告约 6.68 GiB（单位沿用历史记法，性能跑用 bytes 与 MiB/GiB 统一记录）。Phase 7B 计时单独开始，历史构建时间不视为可用预算。以下为设计目标，尚未实测。PM 需为发布验收锁定标准参考机规格。建议 Linux、4 vCPU/8 GiB 可用测试内存及本地 SSD，记录型号、SQLite 版本、冷/热缓存及文件系统。

| 项 | 参考负载目标 | 约束与测量 |
|---|---|---|
| `RECORDED` 处理 | 已验真原索引端到端 ≤ 12 分钟，含建索引/导出/对账。单次大输入的摘要核验另记阶段耗时，仍计入端到端 | 跑原报告量级一次预热加三次测量，取最慢值作门槛。分记输入读、关联、索引、校验和导出 |
| `REPLAYED` 选定根 | manifest 中最多固定 200 个选定 root，额外 ≤ 10 分钟；全量重放暂不设产品承诺 | 单 root ≤ 5 秒或 100000 决策事件，超限丢弃该根未完成 trace，仅保留缺口和已有源证据 |
| RSS | 构建进程树 ≤ 768 MiB，单任务硬上限 1 GiB | `/proc` 间隔测量与 VM progress 检查，SQLite 主缓存目标 64 MiB，避免常驻邻接图或全量解压 |
| SQLite 新增空间 | 发布库 ≤ 1.5 GiB，CSV 目标 ≤ 512 MiB，峰值新增写入 ≤ 3 GiB 含 WAL、临时索引和导出 | 约 0.9M 窄源行、最多 3M 个边记录和最多 6M 个紧凑关系行作为测试上界，加索引后测算。先预留空间再写，超预算保留失败状态或显式的部分评估，禁止静默少记源行 |
| 索引 | 构建索引 ≤ 180 秒，纳入总预算 | 对代表性 filter 用 `EXPLAIN QUERY PLAN`，复合索引优先命中稳定排序谓词 |
| 单包或单组查询 | 首屏 50 条热 p95 ≤ 250 ms，冷 p95 ≤ 1 s | 20 个高/低度样本各重复 5 次，按端口实际响应计时，包含 summary + page |
| 多条件筛选和路径见证 | 方向 + risk + scope 热 p95 ≤ 500 ms，冷 ≤ 2 s。路径见证 ≤ 2 s 或返回边界原因 | keyset cursor，避免全量 COUNT 和 OFFSET 深翻页。默认限制同时两请求进行较重查询，单查询超时留可重试说明 |
| 恢复 | 已完成阶段不重放。每个流水批次中断重做 ≤ 60 秒。索引 DDL 故障重建只重做索引阶段 ≤ 180 秒 | 对每一事务前/后做进程终止故障注入。完整逻辑摘要和原 source hash 相等 |

预算依据是将高成本操作限制为磁盘有序扫描、索引连接和窄表写入。无需对所有符号乘以所有消费者。设 F 为 Finding 数、E 为观察边、J 为实际命中关系数，主体量级约为 `O((F+E+J) log N)` 的 SQLite B-tree 操作，受明确切片及 fanout 控制。命中上界未知或关系爆发时记录分区覆盖缺口。源 Finding ledger 必须完整，部分构建不能丢原 ID。任意可用输出均明确 COMPLETE/PARTIAL，发布预算门禁需要参考负载完整对账。以上目标不从 7A 小型回归外推。

## 验收门槛

- 合成 A–E gold 与同向/反向覆盖通过。每个确认影响的源失败、基线正证和 candidate 有效对照可以回查。无证据升级计数为 0。
- 快照校验、独立对账、旧 API/CSV/SQLite 和 Evidence 回归通过。稳定 ID、冲突失败、逻辑快照一致与中断恢复验证完成。
- 记录真实历史抽样的未确认原因分布。固定参考机上实测近百万负载的处理、RSS、空间、索引和查询。任一目标未达需 PM 审议，不能算已达。
- ARMv7 静态规则使用已验证的结构化输入做差异控制。aarch64/x86_64 合成控制与真实 ARM 产品验收分别记录。Phase 8/9 的真实 SDK 或运行时动作不阻断 7B 静态功能的验收。
