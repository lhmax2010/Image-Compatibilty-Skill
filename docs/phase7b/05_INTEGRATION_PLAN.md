# 集成顺序与最小实施切片

本文件列出 PM 批准后拟实施的改动。当前只新增设计资料。

## 切片一：可独立复核的历史报告关联

- 新建 `compat/impact_source.py` 和 `compat/impact_store.py`、单独 CLI。使用 `report_io.ReportStream` 或已验证的 v1.3 SQLite，分批抽取 `findings`、`raw_elf`、`roles`、`elf_refs`、`aliases`、`packages`、`ownership` 和 `unassigned`。读取 Source Finding payload 以校验镜像角色与参数。摘要列可为旧报告补默认值，不能作为身份来源的唯一证据。
- 对原报告直接读取时使用现有 `Ownership` 对 installed/available、runtime/SDK 和歧义进行归属。已有包评估使用原记录，无需重复运行 `analyze_packages`。没有可靠源记录的归属只作候选。
- `compat/impact_rules.py` 实现有限的声明、端点、原失败及范围关系。所有原 Findings 给出处置，按 `RECORDED` 的保守门槛发布新侧车。复用 v1.3 artifact 验证方式，另写 7B 零悬空和守恒对账。
- 首个可评审切片验收为小型源报告 → 侧车 → CSV/API 原 Finding 回查。需要证明零生产判定改动、历史不可变、旧 schema 降级、确定性及断点恢复。

## 切片二：提取解析对照并启用确认路径

1. 在 `compat/linker.py::dependency_checks` 内增加默认空的可选 observer 或逐 root 迭代出口。保持 `compare_static` 调用参数和默认返回、导出校验、搜索顺序、Finding 载荷、ID 与包评估逐字段一致。新增 observer 只接收已经作出的决策，不参与决策。
2. 为 trace 定义 v1 包头，包含 ordered manifest/有效配置/collector/loader 模型摘要、root selection、side mapping、截断状态及事件计数。观察点包括 root/security/执行上下文、明确/未知前提、DT_NEEDED 搜索和选中路径、首次装载来源、复用原因、version-file 来源、最终 import 选中及候选顺序和完整性。按稳定 root 内序号保存首次加载 edge 引用。一次事件须可唯一对应已有检查，否则只能作辅助证据。流做好大小限制，未完成 root 不发布为完整。
3. 用同一解析器 on baseline 建立对照，adapter 明确将其内部本侧标记映射到 baseline 原生语境。基线 root 与 candidate 派生 transitive component 的物理身份不同，只有确证映射才能对比。不存在证明时只确认原始候选约束事实。保持 baseline 根权限源不变，分别使用对应 lookup manifest。
4. 原始 `emit` 的 Finding 默认映射与 label 只在原 schema 内解释。新 trace 消费显式 side/root/context，避免现有 `seen` 以路径去重造成元数据来源混淆。若同一 root 遇到跨镜像同路径或冲突规范条目且当前模型不能可靠证明身份，将该子范围标为未证，不在本阶段改写 resolver。
5. 启用 `REPLAYED` 与 `TRACE_RECORDED` 模式。校验同源 Phase 7A 置信边界，使用小规模双对照证明确认结果。已有 ABI Finding 的 Provider 移除若仍有匹配替代结果，保留原观察并只记该消费者已满足测试需求。历史 v1.3 数据缺字段时不会反推完整性。
6. 验收 replay 的 root 级停止、cycle、正反方向与 producer/consumer 角色。不得基于 trace 回写旧报告。未来 collector 若单独升级观察字段，按 `collect.elf_job` 既有版本与内容键换代。7B 回放缓存独立键含双 manifest/config/root/namespace/权限/trace 版本，不跨运行借用。

## 切片三：最小浏览及验证动作

在 `compat/report_browser.py` 增加可选且显式配置的只读挂载，使用版本化 `/api/impact/overview`、`/api/impact/groups`、`/api/impact/group`、`/api/impact/consumers`、`/api/impact/members`、`/api/impact/path`、`/api/impact/actions`。每次查询绑定同一 source_run_id/projection，验证源与侧车摘要，沿用只读连接、静态白名单与 loopback。组、成员与路径按需读取。新 endpoints 有独立短超时、响应体上限和游标。不开放任意 SQL、主机路径或 PATH 来源的工具执行。Evidence 由现有安全边界处理，对缺失源显示不可用。新 trace artifact 只开放已经登记且在批准目录下的文件。

在现有增强报告的 assets 中增设可选“影响”入口，按组件/包与 scope、方向、risk 筛选。详情展示 Root Cause Candidate、直接 Consumer、间接根、影响分布、条件、证据与建议验证动作。点击原 ID 跳同一 source 的 `#/finding/<id>`，原路径、旧 groups、原数据表和路由保持兼容。浏览器仅下载小概览和当前页。发布前用同一历史样例验证无侧车、有侧车、未知版本和缺 Evidence 四种体验。

补充 `SKILL.md` 和 `README.md` 的使用约定及 PM 解释边界。沿用 Phase 8 的 `matrix_manifest`、`testing`、`debuginfo` 或 Phase 9 适配器消费建议；本阶段仅生成绑定原 ID 的建议回执槽，运行时能力独立交付。

## 实施顺序与回滚

数据规范和可验证最小样例 → 只读摄取与对账 → root/方向证据 → 同源对照与确认 → 按需路径与组视图 → 性能测试。各切片保持现有报告路径可单独运行。保守历史档位先可用，确认档位等观察器等价与正反例达标再启用。侧车停用后开启旧报告即可回滚，无原库 schema 回退或重建步骤。
