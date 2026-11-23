# 真实 SR 重跑与对账

使用已验收的 SR VD → LLVM、`tizen-headless-armv7l` 同一对标准化 Rootfs TAR 和配置，执行 `static --exclude performance`。两边发布归档和标准化输入 SHA256 均与 Phase 8A 一致。 [发布构建、输入与基线身份](../phase8a/SR_EVIDENCE_EXCERPTS.json)

| 指标 | Phase 8A 基线 | 本轮 |
|---|---:|---:|
| Finding | 903,383 | 903,383 |
| INCOMPATIBLE | 11,490 | 11,490 |
| UNKNOWN | 868,075 | 868,075 |
| COMPATIBLE | 23,486 | 23,486 |
| IDENTICAL | 332 | 332 |
| ABI 完整覆盖率 | 45.42% | 45.42% |
| Linking UNKNOWN | 860,300 | 860,300 |
| Linking 完整覆盖率 | 0% | 0% |
| VD / LLVM 已安装 RPM | 719 / 736 | 719 / 736 |

第一次常规提取触发 workspace 的静态运行磁盘余量保护。第二次以只读权限复用已有提取文件，VD 8,460 个 TAR 成员、LLVM 8,611 个 TAR 成员逐项核对路径、内容、链接和归档元数据。同步压缩五个大型输出流，保存完整序列化载荷。历次原始归档和历史报告只读。成功运行墙钟 231.95 秒，峰值 RSS 3,869,716 KiB。耗时包含输入校验和压缩写入，与基线 191.22 秒的工作路径不同。

正常运行仍为 INCOMPATIBLE、验证 PARTIAL、执行 PARTIAL，退出 1。基线 readelf 2,053 / 2,054，候选 2,119 / 2,120，两个不足均是 `toybox`。真实故障负对照以同一只读环境复现子进程权限故障，执行 FAILED、兼容性 UNKNOWN、退出 3。RPM 数量正确为 null。采用生产 manifest 读取入口验证了历史 schema 1.2 及本轮记录。无旧回执的早期 SR manifest 汇总 UNKNOWN，Phase 8A 原回执仍汇总 PARTIAL。 [采集聚合](COLLECTOR_EXECUTION_REVIEW.md)

## 不变性与对账

- **903,376 条** Finding 的原 ID 与完整 JSON 载荷一致。其余七条是已核对的 DWARF ID 映射，状态全部保持 UNKNOWN。未发现其它变化。 [逐条映射](FINDING_ID_STABILITY.md)
- 逐条核对两代 JSON/CSV 中 Finding ID、维度、状态和严重度，校验 HTML 的前 1,000 条预览。验证 4,086 个不同 Evidence 引用在对应报告证据目录内可定位。
- 在应用七条 ID 映射后，逐项核对 719 条基线包评估、候选包评估、包与消费者/Provider 关系、接口关联和 10,258 条未归属记录，记录及引用均一致。全部覆盖维度的统计与基线一致。

| Phase 8A 数据身份 | 未压缩 JSON SHA256 |
|---|---|
| 已验收基线 | `b14b9814e16c6e49151d22f3be84eac59a00bbb4050b41f9db585495ac6f5f32` |
| 本轮结果 | `6aaf52f97041441bd1090ca40132949c30146d0ab652ee9d516df3e97cee3d99` |

回归 `test_history_pairs_only_same_dwarf_observation_and_keeps_original_ids` 用真实 SQLite 格式的受控小型索引验证旧、新 ID 的匹配和普通记录的稳定性。真实全量索引执行情况见 [剩余缺口](REMAINING_GAPS.md)。 [回归源码](../../../.agents/skills/tizen-image-compatibility/tests/test_phase8a_final.py)
