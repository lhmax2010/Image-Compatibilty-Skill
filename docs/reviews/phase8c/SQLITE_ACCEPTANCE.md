# 真实 SQLite 全量验收 — NOT VERIFIED

本轮用 Phase 8C 全部原始 JSON、CSV、Manifest 和 Evidence 启动全量增强。源文件在执行环境内只读，输出目录独立。只有工作区所在卷获得本轮写入授权。启动时查询了磁盘、inode、内存和 Swap。

| 指标 | 实测 |
| --- | ---: |
| 索引所需输入文件 | 5,521,133,297 B |
| 启动时资源门槛，含 1 GiB 空闲余量 | 13,189,750,242 B（12.28 GiB） |
| 实际通过启动门槛时可用空间 | 15,008,030,720 B |
| 终止时继续建库所需空间 | 11,784,228,322 B |
| 终止时可用空间 | 11,737,546,752 B |
| 终止时缺口 | 46,681,570 B（44.52 MiB） |
| 终止时已分配 | 1,405,521,920 B |
| Wall time / 峰值 RSS | 229.52 秒 / 253,352 KiB |

基线与候选 Manifest 两阶段完成。原始 Finding 和包评估导入过程中，共享卷可用空间跌破正在运行的资源门槛，抛出 ResourceLimit，退出码 1。run.json 标记 FAIL。输出没有 validation.json、overview.json 或面向用户的 index.html。部分 SQLite 文件随现场证据保留，其关联、分页、搜索、外键与完整性均无真实全量验收结论。合成回归覆盖索引、CSV 对账、Evidence 路径和只读 API。 [全量构建与状态写入](../../../.agents/skills/tizen-image-compatibility/scripts/compat/report_enhance.py) · [资源保护](../../../.agents/skills/tizen-image-compatibility/scripts/compat/report_io.py) · [合成测试](../../../.agents/skills/tizen-image-compatibility/tests/test_report_enhancement.py)

获准使用空间稳定的卷时，选择新派生目录。维持相同门槛和 1 GiB 余量，结束后核对 run.json、validation.json 以及 source-before/after 哈希。独立用只读 SQLite 验证 integrity_check、foreign_key_check 和关联反连接，再逐行核对源 JSON 的 ID、状态和完整 payload。用 loopback 浏览器接口核实 719/736 包、分组成员、搜索、分页、Evidence 摘要和只读访问。

```bash
python3 .agents/skills/tizen-image-compatibility/scripts/enhance_report.py build \
  --input "$PHASE8C_RAW_REPORT" --output "$NEW_DERIVED_DIR"
```

对该次建库输入执行独立复核，11 份源报告文件 SHA256 与启动前一致。目录内持久化的部分索引不构成验收。该次构建读入的原始 results.json SHA256 为 `4dd103092152456bd6cd5e5e834d7255e5a43cf1968776c2c0486356b06506c7`。
