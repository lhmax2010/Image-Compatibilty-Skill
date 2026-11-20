# 数据完整性与证据边界

发布前校验 source 1.3 / 1.2 声明、原验证状态和所需索引表。构建保留原文件的设备、inode、大小、mtime/ctime 快照，计算 SQLite、索引 CSV、概览及验证记录的 SHA256。完成前复核源文件版本，服务挂载时重新计算内容身份。重放额外校验两份 manifest 内容与原增强报告对账记录。

新库逐条导入原 Finding id/status/dim/n/hash 和旧组，以原 SQLite 覆盖索引交叉检查以下契约：

- 每个原 ID 与原位置、旧 Linking 组逐行相符，每个位置的状态、维度逐行相符。
- Linking 导出与 Finding 导出的成员集合一致。每条原 Linking Finding 在原观察组保留一个成员引用。新增关联允许跨组重复引用，成员计数与原总量分别报告。
- 软件包关联只引用存在的原 installed package identity 与 side。原角色、已观察但不完整的归属以及 unassigned 数保留在来源。投影按 side、角色、包与组去重，不能把组的角色汇总当作原角色条数。
- 真正确认的候选原 Finding 还须重解压有限的原 payload，逐条验证其 hash、原字段和重放匹配。所有原完整 payload 经现有 API 可读。以原有 v1.3 逐项对账结果和 SHA256 绑定来追踪原证据。
- 原文件只读打开。新 Evidence 查询保留原引用，缺失或不安全的路径保持不可用。原状态不取自组风险。文件级 SHA/source snapshot 变化让新侧车过期。
- 发布以 `run.json` 为提交标记，只有与该标记一致的 SQLite 能挂载。构建目录创建原子排他，任何异常与部分 DB 均不可误读为完成。

合成回归逐字段比对原 SQLite 与新 ledger，检查全源摘要、FK、双向组关联与原 Evidence。单独的演示从新库顺序比对原 CSV 的全部 37 行，通过 HTTP 查询核对原 Finding ID 和状态。新入口直接查询原报告，不重新打包或改变原 JSON/CSV/SQLite。

## 历史真实报告

真实来源为此前通过验证的 `phase5-report-enhancement-final-924ef9f`，源 SQLite SHA256 为 `4ac8769a15ae17fd4ed7571412ba90c68ad2a7d20153cee9c3b6da7a134ebd59`。完成清单 `.local-backups/v14-rc/real-reconciled/run.json` 包含全部七个输入哈希和投影身份 `f0345082d9cdfb5b4513c69ea2d61aebb53053d69570c92dc8a92108e86bf735`。侧车 SQLite SHA256 为 `50d437f34d2aaf3d2d318e0ed8e0a565cc7afb40af8dfd3c0c3be5adede67098`。

| 对账项 | 实测 |
|---|---:|
| 原 Finding | 898342 |
| 原 Linking Finding 与旧组 | 855522 / 134402 |
| 原 Unassigned | 11111 |
| 原 Package Role 行 | 2106110 |
| 原 GCC/LLVM Package | 722 / 736 |
| 与至少一个影响组关联的 GCC/LLVM Package | 539 / 556 |
| 新影响组 / 成员引用 / 包角色深链 | 183290 / 984285 / 824606 |
| 有至少一个组的原 Finding | 897435 |
| 原状态 | 25726 COMPATIBLE / 311 IDENTICAL / 12195 INCOMPATIBLE / 860110 UNKNOWN |
| 确认影响 / 潜在 / 未评估 | 0 / 853881 / 44461 |

原因分布为 431466 条 `CANDIDATE_NATIVE_ONLY`、422415 条 `LOADER_OR_SCOPE_UNPROVEN` 和 44461 条 `NO_EXACT_LINKER_CHECK`。本轮真实导入未重放。确认证据缺口来自历史输入的方向、装载上下文及基线绑定记录。源 Finding 即使无组仍保留在完整 ledger，原 Findings API 可查询。构建期间原文件用内容摘要和文件版本绑定，发布前再次校验版本。

独立验证脚本按原序逐字段比较了 898342 条 CSV 记录和发布 ledger，包括原 Finding ID、状态、维度、顺序、payload 摘要与旧组 ID。原包、原角色、Linking 和 Unassigned 计数一致，侧车 FK 对账通过。`EXPLAIN QUERY PLAN` 确认包反查和组内翻页命中主键，Finding 反查命中 `findings_to_groups` 覆盖索引。

真实服务重新核对全部七个源哈希及侧车哈希，完成两页互斥检查、按范围和影响级别筛选、组成员与包查询、旧和新 Finding 下钻及 Finding 反查组。原 Finding `TC-10567671e8b552d1` 的证据经 HTTP 下载后 SHA256 仍为 `b78f906d48e3ad70afea6749c05dad8d9291987cb0598215fde4dd858d7b5928`。路径穿越返回 403，侧车文件下载请求返回 404。验收脚本关闭了 loopback 服务，最终校验回执为 `COMPLETE`。
