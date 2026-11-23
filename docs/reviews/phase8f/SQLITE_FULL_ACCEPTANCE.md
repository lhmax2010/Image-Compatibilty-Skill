# 真实 SQLite 全量验收

**NOT VERIFIED。** 当前 workspace 只有一个获准的 ext4 工作卷。预检可用 3,134,742,528 B，约 2.92 GiB，距本轮 25 GiB 门槛缺 23,708,803,072 B。预检剩余 inode 93,182,636，MemAvailable 为 21,721,702,400 B，SwapFree 为 2,310,144 B。后续观测可用 1,901,527,040 B。全量构建启动次数为 0。 [资源诊断](SQLITE_RESOURCE_DIAGNOSIS.md)

源为 Phase 8C 的已对账未压缩报告。其 `results.json` 对账 SHA256 为 `4dd103092152456bd6cd5e5e834d7255e5a43cf1968776c2c0486356b06506c7`。原 Phase 8E 部分索引和 FAIL 记录原样保留。本轮未创建新的全量输出。四个主要原始报告文件均重新核对为 Phase 8C 对账的 expected SHA256，其中 gzip 复跑版 results.json 的历史 observed SHA256 单列并保持原状。 [Phase 8C 对账](../phase8c/COVERAGE_BEFORE_AFTER.md) · [Phase 8E 失败现场](../phase8e/SQLITE_FULL_ACCEPTANCE.md)

| 来自原始报告的基准 | 值 |
| --- | ---: |
| Findings | 903,377 |
| INCOMPATIBLE | 11,490 |
| Linking UNKNOWN | 860,294 |
| 未归属 Findings | 10,258 |
| VD / LLVM 安装 RPM | 719 / 736 |

取得稳定的 workspace 内授权卷（或用户明确授权的新路径）并实测可用至少 25 GiB 后，固定 Phase 8C 输入目录和独立输出。保持输入只读并记录建库前后输入 SHA256。构建器会将 `SQLITE_TMPDIR` 指向输出下的 `tmp/`，宿主 `TMPDIR` 也应设在获准工作卷。继续使用现有动态磁盘、内存和产物门槛。

```bash
python3 .agents/skills/tizen-image-compatibility/scripts/enhance_report.py build \
  --input "$READ_ONLY_PHASE8C_REPORT" --output "$NEW_REPORT_ON_AUTHORIZED_VOLUME"
```

验收条件包括对全部基准 Findings 的 ID、状态和完整 Payload Hash 逐项对账，检查包、Consumer、Provider、Group、未归属成员和 Evidence 的引用及源文件哈希。通过只读 SQLite 连接运行 `PRAGMA integrity_check`、`PRAGMA foreign_key_check` 及独立逻辑反连接检查，验证查询、分页、排序、去重和只读访问。成功标记需同时核对 `run.json` 及 `validation.json`，并记录实际耗时、RSS 峰值和输出体积。上述索引级检查本轮均未执行。 [构建及校验入口](../../../.agents/skills/tizen-image-compatibility/scripts/enhance_report.py)
