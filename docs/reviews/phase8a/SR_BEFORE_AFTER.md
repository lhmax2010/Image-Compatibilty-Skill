# SR 真实数据修复前后对账

基线、候选的公开归档字节数与发布 SHA256、标准化 TAR SHA256、两个结果的未压缩 JSON SHA256 均在机器证据中可查询。比较方向相同，均以 VD 消费者迁至 LLVM 为对象。 [输入来源与结果身份](SR_EVIDENCE_EXCERPTS.json)

| 项目 | 修复前 | 修复后 |
|---|---:|---:|
| INCOMPATIBLE | 11,646 | 11,490 |
| UNKNOWN | 868,075 | 868,075 |
| COMPATIBLE | 23,486 | 23,486 |
| IDENTICAL | 332 | 332 |
| 总计 | 903,539 | 903,383 |
| ABI 完整验证覆盖率 | 45.42% | 45.42% |
| ABI 不兼容检查单元 | 456 | 422 |
| ELF 完整验证覆盖率 | 5.99% | 5.99% |
| Linking 完整验证覆盖率 | 0% | 0% |
| VD / LLVM 安装 RPM | 719 / 736 | 719 / 736 |
| 壁钟耗时 | 183.64 秒 | 191.22 秒 |

903,376 条 Finding 保持原 ID 与状态。移除的 156 条均为 GNU 版本节点标记。另有 7 对 DWARF 类型布局记录，既有负载中的临时解包路径改变了 ID，组件、状态和 Evidence 均相同。证据列出全部七对 ID。 [ID 差异与版本样本](SR_EVIDENCE_EXCERPTS.json)

逐条顺序核对新 JSON/CSV 的 Finding ID、状态、严重度与维度。HTML 的前 1,000 条 Finding 和 719 条基线包评估与机器数据一致。消费者、包、Provider 和接口关联未见悬空 ID。4,086 个不同 Evidence 引用指向报告目录中的存在文件。保留 10,258 个未归属 ID。 [序列化入口](../../../.agents/skills/tizen-image-compatibility/scripts/compat/report.py#L73) · [完整性与证据回归](REGRESSION_SUMMARY.md)

复核可以用相同发布归档和归档 SHA256，按发布 Profile 的分区挂载语义离线组装 `/` 与 `/opt`。使用评审代码以 `static --exclude performance` 跑 VD → LLVM，保留新报告和加载上下文。用 `findings.csv` 与 `results.json` 对账并核对两侧 RPM 记录。现场验证将大型 JSON/CSV 的标准序列化字节流直接写入 gzip，避免占满磁盘。191.22 秒包含压缩写入，两次磁盘和缓存条件各自独立。 [源码版本](SOURCE_CHANGES.json) · [资源限制](KNOWN_LIMITATIONS.md)
