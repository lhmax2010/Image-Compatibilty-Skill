# 真实 SR SQLite 全量验收

输入使用 Phase 8C 留存的未压缩 SR 原始报告。该报告已与最终 gzip 版做 Finding、CSV/HTML、Evidence 和包结果对账，结构化 JSON 的差异仅为 RPM 临时副本及解包路径记录。选用这个版本可以避免额外物化约 5.52 GB。原始 results.json SHA256 为 `4dd103092152456bd6cd5e5e834d7255e5a43cf1968776c2c0486356b06506c7`。本轮只读预检重新校验了 11 份源文件，全部与 Phase 8C 的摘要一致。 [Phase 8C 对账](../phase8c/COVERAGE_BEFORE_AFTER.md)

| 资源检查项 | 字节 |
| --- | ---: |
| 任务开始时获准工作卷可用 | 13,097,545,728 |
| 找到的已授权工作卷 | 仅当前工作区所在 ext4 卷 |
| 优先容量 25 GiB | 26,843,545,600 |
| 五个索引输入文件 | 5,521,133,297 |
| 构建器的既有启动门槛 | 13,189,750,242 |
| 正式启动时可用 | 13,527,703,552 |
| 启动时超过既有门槛 | 337,953,310 |

初始探测时缺 92,204,514 B，等其他磁盘占用自然释放后启动。源报告通过只读绑定，新索引和 SQLite 临时目录均在独立的工作区 Phase 8E 输出目录。沿用构建器的 `2 × 输入 + 2 GiB` 启动预算、动态磁盘余量和既有进程内存门槛。建库输入继续依赖原始 Evidence 所在目录。 [构建器与资源保护](../../../.agents/skills/tizen-image-compatibility/scripts/compat/report_enhance.py) · [资源实现](../../../.agents/skills/tizen-image-compatibility/scripts/compat/report_io.py)

```bash
python3 .agents/skills/tizen-image-compatibility/scripts/enhance_report.py build \
  --input "$READ_ONLY_PHASE8C_RAW" --output "$NEW_INDEX_DIR"
```

源报告既有指标为 903,377 个 Finding、11,490 个 INCOMPATIBLE、860,294 个 Linking UNKNOWN、10,258 个未归属 Finding 和 VD/LLVM 719/736 已安装 RPM。这些基准数值独立于真实 SQLite 验收。

## 实际运行结果 — NOT VERIFIED

两份 Manifest 已导入。原始项和包评估阶段进入 SQLite CREATE INDEX 后，磁盘余量降到动态门槛以下。该阶段的 SQL progress callback 执行资源检查，构建器返回 SQLite OperationalError（interrupted），退出码 1。进程没有进入 CSV、对账或最终只读查询验收阶段。新目录的 run.json 为 FAIL，保留失败日志和部分索引。该目录缺少 validation.json、overview.json 和报告入口。 [建库 SQL 阶段](../../../.agents/skills/tizen-image-compatibility/scripts/compat/report_store.py)

| 停止时观测 | 实际值 |
| --- | ---: |
| 建库墙钟 | 1,148.136 秒 |
| 峰值进程 RSS | 348,504,064 B（340,336 KiB） |
| 采样的进程树峰值 RSS | 274,878,464 B |
| 构建器 CPU 时间 | 142.72 秒 |
| 当前所需剩余可用空间 | 9,335,160,290 B |
| 同一采样中实际可用空间 | 9,313,439,744 B |
| 缺口 | 21,720,546 B（约 20.7 MiB） |
| 部分 SQLite 文件 | 3,853,770,752 B |
| 失败现场总分配 | 3,854,589,952 B |

索引扫描期间曾对本轮派生 SQLite 文件进行顺序只读预读，避免重复随机磁盘访问。构建停止后终止了预读操作。资源门槛和输入始终保持原样。准备好的独立审计以成功 run.json 和 validation.json 为前提，本轮未执行完整数据库验收。没有给失败导入、历史数据计数或合成测试授予真实全量完成状态。

已在停止后独立重新计算 11 份源文件 SHA256，与构建前一致，确认源报告没有变化。

再次执行需先获得空间稳定的授权卷，优先至少 25 GiB，新建派生目录。目标审核需逐条核对 ID、状态、完整载荷和 Payload Hash，计算 Linking Group 分组键，核对包与 Provider/Consumer 关联、未归属集合、Evidence 哈希、SQLite integrity_check / foreign_key_check 与逻辑外键。还需从只读 loopback 入口验证去重、搜索、排序、分页和 Evidence，核对成功标记、输入前后 SHA256、实际耗时、峰值内存和磁盘。
