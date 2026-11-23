# Phase 8F 验收

**CONDITIONAL PASS。** SQLite 计量缺口机制已复现，历史差额分摊仍为 UNKNOWN。冻结执行入口完成默认关闭、身份校验和合成运行验证。真实全量 SQLite 为 NOT VERIFIED，正式 ARM Runtime 0/8。基线为 `993c8b514e513f463bf685ac15344668a88cae86`。

| 任务 | 本轮状态 | 可核对依据 |
| --- | --- | --- |
| A · 资源诊断 | 计量机制确认，历史差额归因 UNKNOWN | 小型 SQLite 复现了目录看不到的临时数据库与排序文件。历史差额约 343 MiB。 [资源诊断](SQLITE_RESOURCE_DIAGNOSIS.md) |
| B · 真实 SQLite | NOT VERIFIED | 唯一授权工作卷低于 25 GiB。全量建库启动次数 0。 [全量验收](SQLITE_FULL_ACCEPTANCE.md) |
| C · 冻结执行入口 | 计划核验与合成 PASS | 10 个真实冻结字节通过大小及 SHA256 校验，生成 8 条未执行计划。7 项合成测试覆盖协议、失败和清理。 [入口与回执](FROZEN_RUNTIME_ENTRY.md) |
| D · QEMU User | 宿主隔离探针通过，目标冒烟 NOT_EXECUTED | 只运行 x86-64 宿主预检及 QEMU 自身版本/模型查询。 [隔离与负例](QEMU_USER_SMOKE_READINESS.md) |
| E · 真实设备或 Guest | 未准入 | 缺少已授权的匹配目标和准确启动身份。正式结果为 0/8。 [目标准入](TARGET_ENVIRONMENT_READINESS.md) |
| F · libc++ | 离线指定库依赖核对通过，Runtime NOT_EXECUTED | 两侧各需 2 个同快照库。指定库模型下各核对 32 个版本需求及 361 个版本化导入。 [依赖闭包](LIBCXX_RUNTIME_DEPENDENCIES.md) |

## 自动化回归

```bash
python3 -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v
git diff --check
```

基线实跑 249 项，244 PASS、5 SKIP、0 FAIL。本轮完整运行 256 项，251 PASS、5 SKIP、0 FAIL，退出 0。测试本身耗时 217.620 秒；外层实测墙钟 217.79 秒，最大 RSS 103,332 KiB。此前同机器实跑基线墙钟 104.80 秒。两次系统负载不同，本轮同时独立顺序读取约 5 GB 原始报告用于校验摘要，没有将两次墙钟当成性能对比。测试日志 SHA256 为 `ce19603ad4938e6c7c99e24ffa9a6607449e5d2e97b27ed2fb61b5ea1d7e753a`。非特权 RPM 测试包装和临时目录均在 workspace。

5 个 SKIP 与基线相同。

- `test_real_abidiff_embedded_and_split_layout_break` 未设置 `COMPAT_TEST_ABIDIFF`。
- `test_real_clang_ast_and_arm` 未设置 `COMPAT_TEST_CLANG`。
- `test_explicit_probes_exact_matrix_ids_with_simulated_receipts` 缺该集成测试需要的实际 GCC/Clang 组合。
- `test_real_arm_v6_v7_and_vfp_fixtures` 缺实际 Clang ARM 编译器配置。
- `test_real_hard_softfp_and_soft_pcs` 缺可用的真实 Clang 测试配置。

生产变更集中在冻结 CLI、对 v1 回执可选的身份绑定验证，以及有界进程组停止和证据收集。静态兼容性判定、SQLite 资源门槛和 Finding 字段保持原语义。 [入口](../../../.agents/skills/tizen-image-compatibility/scripts/frozen_runtime.py) · [回执复用](../../../.agents/skills/tizen-image-compatibility/scripts/compat/testing.py) · [超时处理](../../../.agents/skills/tizen-image-compatibility/scripts/compat/core.py)

原始 Phase 8C 报告的 `findings.csv`、`packages.csv`、`index.html`、`results.json` 均重新读取并匹配 Phase 8C 对账中留存原始报告的 expected SHA256。原始 Findings、镜像、SDK 和冻结 ELF 保存在 workspace 的既有位置。 [剩余缺口](REMAINING_GAPS.md)
