# 数据模型、持久化与兼容

## 标识和语义

一次侧车只服务一个源报告。`source_run_id` 是规范化有序清单的 SHA-256，清单分别绑定 results、双 manifest、已纳入的 CSV 原始字节摘要。`projection_id` 再绑定源索引指纹、输入档位、已使用的 trace 摘要、规则版本、scope 配置及预算策略。方向作为结构字段绑定有序的消费者来源和查找环境，允许 `BASELINE_ON_CANDIDATE`、`CANDIDATE_NATIVE`，基线自解析只作为 `BASELINE_CONTROL` 证据。反向迁移通过交换输入另建运行；同 basename、SONAME 或同内容哈希不跨镜像自动合并。

| 对象 | 逻辑键 |
|---|---|
| Finding | `(source_run_id, 原 finding.id)`。保留原 status、payload hash 和 occurrences。源序号是本库内部外键，不覆盖原 ID |
| ELF 或 Header | `(side, scope, kind, 规范虚拟绝对路径)`，附源 index ID/raw path 与别名依据。记录可信 symlink 链、原路径和路径冲突，拒绝跨镜像或有歧义的别名折叠。迁移路径用独立匹配证据 |
| Package | `(side, scope, 现有 package_id)`，保留 NEVRA、instance 和 installed ownership 状态。旧 peer 与共享文件提示保留独立语义 |
| Context | `(direction, root对象, consumer_origin, lookup_side, namespace, resolver策略, loader和有效配置摘要, root执行元数据来源及摘要, 图作用域)`。阶段性搜索或已装载状态由 edge decision 承载 |
| Requirement | 按 kind 标记的规范结构。NEEDED 保留原请求串。IMPORT 保留 raw name、base、版本或显式 null、默认版本选择、binding/type、version_file、lookup kind。版本约束包括所需文件、节点、weak flag。Header 包含公共入口、声明与适用条件 |
| Edge | `context + from + to或明确缺失标记 + kind + requirement + 决策来源和等价的决策键`。记录 strength、解析结果和证据。推断边不能替换源解析边 |
| Impact Group | `(rules_major, direction, cause_kind, stable_anchor, exact_contract, applicability_key)`。锚点按侧与作用域注明，解析失败键包含所需的搜索/安全等价条件，无充分条件就包含精确 context。接口移除按已证同一 Provider 契约迁移归组，保留不同消费者上下文 |

规范化采用 UTF-8、稳定按键排序、无浮点/非有限值、原字段大小写与装饰名保留、null 明确区别缺字段。引用键的复合组件使用 JSON 数组，防止分隔符碰撞。`EG-/IG-/CX-` 等类型前缀加完整 SHA-256。插入已存在 hash 时比较完整规范键，不同则停止构建。ID 不引用 SQLite 序号、时间戳、遍历顺序、计数或验证结果。`IG-` 在相同方向、规范锚点、约束、策略大版本和条件下稳定，换路径、方向或策略大版本可以产生不同 ID。外部唯一使用 `(projection_id, group_id)`。跨产品运行的根因承接待 Phase 10 定义。

## SQLite 侧车 v1

下面是 v1 逻辑 DDL。所有 FK 在构建连接开启。单次构建只写本文件。参照原数据库的字段通过导入字典与对账实现，SQLite 外键不跨库。`key_json` 存规范键，`pub_id` 存公开 hash，内部整数用来压缩高频关联。

```sql
PRAGMA user_version = 1;
PRAGMA foreign_keys = ON;

CREATE TABLE meta (
  key TEXT PRIMARY KEY NOT NULL,
  value_json TEXT NOT NULL
);
CREATE TABLE checkpoint (
  phase TEXT PRIMARY KEY NOT NULL,
  last_key TEXT NOT NULL,
  input_digest TEXT NOT NULL,
  finished INTEGER NOT NULL CHECK(finished IN (0,1))
);
CREATE TABLE source_finding (
  fno INTEGER PRIMARY KEY,
  finding_id TEXT UNIQUE NOT NULL,
  status TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  occurrences INTEGER NOT NULL CHECK(occurrences > 0),
  disposition TEXT NOT NULL CHECK(disposition IN
    ('PENDING','GROUPED','UNASSESSED','OUT_OF_SCOPE')),
  reasons_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE object_ref (
  obj INTEGER PRIMARY KEY,
  kind TEXT NOT NULL CHECK(kind IN ('ELF','HEADER','PACKAGE')),
  side TEXT NOT NULL CHECK(side IN ('baseline','candidate')),
  scope TEXT NOT NULL CHECK(scope IN ('runtime','sdk')),
  identity TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  UNIQUE(kind,side,scope,identity)
);
CREATE TABLE context (
  ctx INTEGER PRIMARY KEY,
  pub_id TEXT UNIQUE NOT NULL,
  root_obj INTEGER NOT NULL REFERENCES object_ref(obj),
  direction TEXT NOT NULL,
  key_json TEXT NOT NULL,
  conditions_json TEXT NOT NULL
);
CREATE TABLE requirement (
  req INTEGER PRIMARY KEY,
  pub_id TEXT UNIQUE NOT NULL,
  kind TEXT NOT NULL,
  key_json TEXT NOT NULL
);
CREATE TABLE dependency_edge (
  edge INTEGER PRIMARY KEY,
  pub_id TEXT UNIQUE NOT NULL,
  ctx INTEGER NOT NULL REFERENCES context(ctx),
  from_obj INTEGER NOT NULL REFERENCES object_ref(obj),
  to_obj INTEGER REFERENCES object_ref(obj),
  req INTEGER NOT NULL REFERENCES requirement(req),
  kind TEXT NOT NULL,
  strength TEXT NOT NULL CHECK(strength IN ('DIRECT','INFERRED','UNKNOWN')),
  outcome TEXT NOT NULL,
  key_json TEXT NOT NULL,
  detail_json TEXT NOT NULL
);
CREATE TABLE edge_finding (
  edge INTEGER NOT NULL REFERENCES dependency_edge(edge),
  fno INTEGER NOT NULL REFERENCES source_finding(fno),
  PRIMARY KEY(edge,fno)
) WITHOUT ROWID;
CREATE TABLE impact_group (
  grp INTEGER PRIMARY KEY,
  pub_id TEXT UNIQUE NOT NULL,
  anchor INTEGER REFERENCES object_ref(obj),
  req INTEGER REFERENCES requirement(req),
  direction TEXT NOT NULL,
  cause_kind TEXT NOT NULL,
  key_json TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  interface_scope TEXT NOT NULL CHECK(interface_scope IN ('PUBLIC','INTERNAL','UNDETERMINED'))
);
CREATE TABLE group_finding (
  grp INTEGER NOT NULL REFERENCES impact_group(grp),
  fno INTEGER NOT NULL REFERENCES source_finding(fno),
  PRIMARY KEY(grp,fno)
) WITHOUT ROWID;
CREATE TABLE group_edge (
  grp INTEGER NOT NULL REFERENCES impact_group(grp),
  edge INTEGER NOT NULL REFERENCES dependency_edge(edge),
  PRIMARY KEY(grp,edge)
) WITHOUT ROWID;
CREATE TABLE consumer_impact (
  impact INTEGER PRIMARY KEY,
  pub_id TEXT UNIQUE NOT NULL,
  grp INTEGER NOT NULL REFERENCES impact_group(grp),
  ctx INTEGER NOT NULL REFERENCES context(ctx),
  consumer INTEGER NOT NULL REFERENCES object_ref(obj),
  req INTEGER NOT NULL REFERENCES requirement(req),
  relation TEXT NOT NULL CHECK(relation IN ('DIRECT_CONSUMER','INDIRECT_ROOT')),
  assessment TEXT NOT NULL CHECK(assessment IN
    ('CONFIRMED_CONTRACT_IMPACT','POSSIBLE_IMPACT','UNASSESSED','NO_BREAK_OBSERVED')),
  reason TEXT NOT NULL,
  CHECK(relation != 'INDIRECT_ROOT' OR assessment != 'CONFIRMED_CONTRACT_IMPACT'),
  UNIQUE(grp,ctx,consumer,req,relation)
);
CREATE TABLE impact_basis (
  impact INTEGER NOT NULL REFERENCES consumer_impact(impact),
  edge INTEGER NOT NULL REFERENCES dependency_edge(edge),
  purpose TEXT NOT NULL,
  PRIMARY KEY(impact,edge,purpose)
) WITHOUT ROWID;
CREATE TABLE object_package (
  obj INTEGER NOT NULL REFERENCES object_ref(obj),
  pkg INTEGER NOT NULL REFERENCES object_ref(obj),
  ownership TEXT NOT NULL,
  PRIMARY KEY(obj,pkg)
) WITHOUT ROWID;
CREATE TABLE group_package (
  grp INTEGER NOT NULL REFERENCES impact_group(grp),
  pkg INTEGER NOT NULL REFERENCES object_ref(obj),
  role TEXT NOT NULL CHECK(role IN ('DIRECT_CONSUMER','INDIRECT_ROOT','PROVIDER')),
  PRIMARY KEY(grp,pkg,role)
) WITHOUT ROWID;
CREATE TABLE artifact_ref (
  artifact INTEGER PRIMARY KEY,
  source_kind TEXT NOT NULL,
  reference TEXT NOT NULL,
  state TEXT NOT NULL,
  sha256 TEXT,
  UNIQUE(source_kind,reference)
);
CREATE TABLE edge_evidence (
  edge INTEGER NOT NULL REFERENCES dependency_edge(edge),
  artifact INTEGER NOT NULL REFERENCES artifact_ref(artifact),
  locator TEXT NOT NULL,
  PRIMARY KEY(edge,artifact,locator)
) WITHOUT ROWID;
CREATE TABLE scope_decision (
  grp INTEGER NOT NULL REFERENCES impact_group(grp),
  rule_id TEXT NOT NULL,
  origin TEXT NOT NULL,
  match_level TEXT NOT NULL,
  outcome TEXT NOT NULL,
  config_digest TEXT NOT NULL,
  PRIMARY KEY(grp,rule_id,origin)
) WITHOUT ROWID;
CREATE TABLE validation_action (
  action_id TEXT PRIMARY KEY NOT NULL,
  grp INTEGER NOT NULL REFERENCES impact_group(grp),
  impact INTEGER REFERENCES consumer_impact(impact),
  kind TEXT NOT NULL,
  request_json TEXT NOT NULL,
  state TEXT NOT NULL,
  key_json TEXT NOT NULL
);
CREATE INDEX edge_out ON dependency_edge(ctx,from_obj,kind,to_obj);
CREATE INDEX edge_in ON dependency_edge(ctx,to_obj,kind,from_obj);
CREATE INDEX edge_req ON dependency_edge(ctx,req,kind);
CREATE INDEX edge_finding_by_source ON edge_finding(fno,edge);
CREATE INDEX group_finding_by_source ON group_finding(fno,grp);
CREATE INDEX groups_by_anchor ON impact_group(anchor,pub_id);
CREATE INDEX groups_filter ON impact_group(direction,risk_level,interface_scope,pub_id);
CREATE INDEX impact_in_group ON consumer_impact(grp,assessment,relation,pub_id);
CREATE INDEX group_by_package ON group_package(pkg,role,grp);
CREATE INDEX action_in_group ON validation_action(grp,action_id);
```

Finding↔Group、Finding↔Edge、Group↔Edge 均为多对多。Context/Requirement 对 Edge 为一对多。Consumer Impact 是组、上下文、需求、消费者和关系的唯一组合。Package 通过 object ownership 多对多映射，`group_package` 是按角色去重的查询索引。它保留 Provider 和受影响组件角色，消费者影响细节通过 `consumer_impact` 查得。角色多值不相加。潜在线索及无 owner 保持原始来源，包索引可按对应角色标注证据限制。Evidence 原始引用直接通过 Finding 查看。新增决策证据只记录原 trace、manifest 或报告的引用及定位符，不复制正文。`artifact_ref` 允许保存缺失或不安全引用的原字符串，下载端永远不会据此打开文件。

应用校验补充 DDL 无法表达的条件：Context root 必须为 ELF，方向和 source side 一致，`object_package.pkg` 必须为 Package 同侧同 scope，`impact_basis` 中每个 edge 必须属于对应 group，action 指向的 impact 属于同组。确认影响必须同时存在来自可比两端的有效决策和来源合格的失败 Finding。每个分组的 `group_finding` 至少有一行。所有 `PENDING` 都须完成，对账用原 ID、payload hash 和处置集合做反连接，并根据 `GROUPED` 校验归组是否存在。相同原 ID 同载荷的重放允许幂等，冲突记录必须失败。可在独立工作表保留未归属原因及原 unassigned 成员，以原 ID 回读，来源含 `NO_PATH`、`NO_OWNER`、`AMBIGUOUS_OWNER`、`INCOMPLETE_INVENTORY`、`NO_BASELINE_PEER`、`SDK_SCOPE_UNMAPPED`。

## JSON、CSV、HTML 和兼容

`impact-overview.json` 仅发布身份、输入档位和独立计数。完整记录通过分页 API 或流式导出。以下 JSON Schema 描述概览。版本、枚举以及 API 项字段在实现前冻结，与 SQLite `user_version` 分别校验。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Phase 7B impact overview v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["impact_schema", "source_run_id", "projection_id", "mode", "state", "counts"],
  "properties": {
    "impact_schema": {"const": "1.0"},
    "source_run_id": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
    "projection_id": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
    "mode": {"enum": ["RECORDED", "REPLAYED", "TRACE_RECORDED"]},
    "state": {"enum": ["COMPLETE", "PARTIAL"]},
    "counts": {
      "type": "object",
      "additionalProperties": false,
      "required": ["source_findings", "observations", "grouped_findings", "unassessed_findings", "out_of_scope_findings", "groups", "member_links"],
      "properties": {
        "source_findings": {"type": "integer", "minimum": 0},
        "observations": {"type": "integer", "minimum": 0},
        "grouped_findings": {"type": "integer", "minimum": 0},
        "unassessed_findings": {"type": "integer", "minimum": 0},
        "out_of_scope_findings": {"type": "integer", "minimum": 0},
        "groups": {"type": "integer", "minimum": 0},
        "member_links": {"type": "integer", "minimum": 0}
      }
    }
  }
}
```

列表统一返回 `{projection_id,items,next_cursor}`，默认 50、最多 100，游标绑定投影与排序/筛选条件。Group 详情字段包括 group_id、direction、root_cause_candidate、原状态分布、scope 与来源、风险等级、已确认/可能/未评估分布、未完成验证数。成员引用及消费者用独立分页接口。Edge 明细公开 context、端点、需求、strength、决策原因和原引用。验证动作携带 `action_id`、环境要求及原 Finding 入口。以原 ID 链接到旧报告路由，独立保留 source_run_id。旧读者仍读取原 JSON/CSV/SQLite。新读者遇到缺侧车隐藏影响面板并显示未构建，未知大版本、摘要不一致或未发布状态拒绝加载新增视图，原报告可读。

`COMPLETE` 表示本档位的输入已完整处理并对账。`PARTIAL` 表示某些分区或验证所需输入缺失或被预算截断。两者都可以含 UNKNOWN 和已记录的未评估项，发布完整性不代表兼容性。`root_cause_candidate` 由组的 `cause_kind`、锚点、约束和适用条件生成，以组键为准。

| API 记录 | 必需内容与类型 |
|---|---|
| `ImpactGroup` | `group_id:string`、`direction:enum`、`root_cause_candidate:{kind:string,anchor:object|null,requirement:object|null,applicability:object}`、`original_status_counts:map<string,uint>`、`assessment_counts:map<string,uint>`、`risk_level:enum`、`interface_scope:enum`、`action_count:uint` |
| `DependencyEdge` | `edge_id:string`、`context_id:string`、`from:object`、`to:object|null`、`kind:enum`、`requirement:object`、`strength:enum`、`outcome:string`、`reasons:array<string>`。Evidence 和 Finding 引用各自有查询页，索引不把正文打包进该对象 |
| `ConsumerImpact` | `impact_id:string`、`group_id:string`、`context_id:string`、`consumer:object`、`requirement_id:string`、`relation:enum`、`assessment:enum`、`reason:string`。路径按需查询，返回已知的 context、edge IDs 与截断原因 |
| `FindingLink` | `source_run_id:string`、`finding_id:string`、`group_id:string`、`original_status:enum`，由 `group_finding` 联接源 ledger 输出 |
| `ValidationAction` | `action_id:string`、`group_id:string`、`impact_id:string|null`、`kind:enum`、`state:enum`、`request:{requirement:object,environment:object,expected_artifacts:array<string>}` |

`object` 中的端点结构为 `{side,scope,kind,identity}`，均为字符串。输出枚举复用同名数据库列及 [关联规则](03_ASSOCIATION_RULES.md) 定义。`uint` 为非负整数。返回列表包裹当前 `projection_id`，跨投影游标拒绝使用；记录中缺失证据用 null 和原因表达。

拟导出 `impact-groups.csv`、`impact-finding-links.csv` 和 `impact-consumers.csv`，每表粒度固定。沿用 CSV 公式转义；引用 SHA 与实际数据重新对账。原 CSV 保持不变。新增视图用现有安全 DOM 构建与回跳路由，增量改动见 [集成计划](05_INTEGRATION_PLAN.md)。

## 增量、事务和回滚

- 新目录用独占构建锁，SQLite 只写临时侧车。源采用 `mode=ro`，优先使用已完成且无未清理 WAL 的版本。预检记录原文件大小、摘要、报告版本、必要列、原验证结果和解析器身份。SQLite-only 模式需要索引来源证明，不能信任未校验数据库自称的摘要。
- 以原 `n` 键集批读源 Finding，记录键和摘要。首次导入默认 5000 条/事务。解析 trace 按方向和 root 提交，关联按稳定 group key 切片。数据写入与 checkpoint 同事务，崩溃后重放最后未提交切片。重放以规范键辨识同载荷重复，哈希或值不同则终止。
- 构建任务版本、输入指纹、规则、配置、资源策略任一变化便新建输出；v1 不对已发布侧车做就地增量更新。不变阶段可恢复，性能验收比较恢复与全量产物的逻辑内容。未来跨版本复用若不能精准识别受影响 root，按全量重建处理。
- 同一不可变输入在不同 worker 顺序下须有相同公开记录与逻辑摘要。仅重新序列化或换序源文件会改变原字节摘要，也会产生新 run/projection ID；等价的组和边键仍稳定，比较这类输入时明确排除外部 run 标识和物理序号。
- 发布前独立核对 FK、唯一性、原 ID 和状态、包与 Evidence 引用、输入再验证、JSON/CSV/SQLite 逻辑摘要。写完 CSV、概览和新库后再发布完成标记，目录重命名在同一文件系统内执行。读者只打开带正确清单且完成的目录。资源超限或损坏留进度和失败原因，不替换已发布视图。回滚停用当前侧车，原报告入口继续使用。
