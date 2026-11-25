# 真实 SR SQLite 验收

使用 Phase 8C 的同一未压缩只读源报告。启动时工作区所在 ext4 卷可用 291,220,434,944 B，超过 25 GiB 准入要求。五个索引输入合计 5,521,133,297 B，生产 ResourceGuard 的实际启动门槛为 13,189,750,242 B。源摘要记录覆盖 11 个文件，共 5,543,410,883 B。SQLite 临时文件与输出均位于工作区内的全新目录。历史报告与失败证据继续保留。

```bash
python3 .agents/skills/tizen-image-compatibility/scripts/enhance_report.py build \
  --input "$PHASE8C_RAW_REPORT" --output "$NEW_SQLITE_DIR"
```

源报告独立基准为 903,377 Finding、11,490 INCOMPATIBLE、860,294 Linking UNKNOWN、10,258 未归属 Finding 及 VD 719 / LLVM 736 已安装 RPM。完整验收依赖当前建库的 PASS `run.json`、`validation.json`，以及逐条原始载荷与 SHA256、关联、Evidence、数据库完整性、逻辑外键及只读浏览对账。

## 交付时状态：NOT VERIFIED

真实建库经准入后启动。交付检查时 SQLite 仍处于 `original findings and assessments`，进程多次在共享卷等待内核磁盘 I/O。尚无成功 run.json、validation.json 或独立对账结果。该时点没有触发容量或内存保护，也没有从部分索引推导数据完整性。

- 构建已运行约 1698 秒，CPU 104.02 秒。
- 最后采样可用磁盘 279,137,341,440 B，派生输出已分配 2,028,314,624 B。
- 实测采样进程 RSS 峰值 259,149,824 B，进程树采样 RSS 高水位 231,317,504 B。

本地保留 `sqlite.log`、`sqlite/resource-samples.jsonl`、阶段和输入摘要。独立审计已安排在构建成功后检查全量载荷、关系、Evidence 与只读查询。完整 SQLite 是独立子任务，工作流功能验收使用原始静态报告及实机回执。

独立重读的 11 个源文件 SHA256 与历史 Phase 8E 审计及本轮启动快照全部相符。该检查只授予源文件不可变性证据，完整建库仍需成功回执和独立索引对账。
