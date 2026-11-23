# Phase 8E 验收

基线 `3f7f32364fef47223cbae07e28cfbac8c4ff7e70`。SDK、静态检测和 Runtime 判定逻辑沿用该基线。**准备工作完成，整体为 CONDITIONAL PASS，SQLite P0 仍未关闭。**

| 验收项 | 结果 |
| --- | --- |
| 真实 SQLite | NOT VERIFIED。已真实启动，动态磁盘门槛中断建索引。 [构建与资源记录](SQLITE_FULL_ACCEPTANCE.md) |
| 产物身份 | 10 个唯一旧产物 SHA256 校验并冻结，4 个主程序可在取得实机准入后用于八项矩阵。Phase 8D Skill 四个对应产物与其逐字节一致。 |
| 环境调查 | 本机可见 QEMU User，未发现核实可运行这两个 SR 快照并获准的设备或 Guest。缺少匹配 Kernel/DTB/启动配置及操作授权。 |
| Adapter | 针对既有合成 v1 回执与错误路径复核 12 项，全通过。目标部署、真实回执、清理和工作区约束待授权环境实测。 |
| 四象限 Runtime | 0/8 实际执行，八项均为 NOT_EXECUTED。 |
| 独立 libc++ 轨道 | 一项真实 Clang+libc++ 离线编译链接通过，0 项执行。原来的 Clang+libstdc++ 产物保留同一 SHA256。 |

[冻结清单](FROZEN_ARTIFACT_MANIFEST.md) · [候选环境](RUNTIME_ENVIRONMENT_OPTIONS.md) · [Adapter 证据](RUNTIME_ADAPTER_READINESS.md) · [八项计划](FOUR_QUADRANT_EXECUTION_PLAN.md) · [libc++](LIBCXX_FEASIBILITY.md)

## 回归与证据

```bash
python3 -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v
git diff --check
```

完整回归共 249 项，244 PASS、5 SKIP、0 FAIL，用时 191.252 秒。跳过项为宿主 Clang 的 AST、显式探针和两类 ARM 测试，以及 libabigail 集成。额外的 12 项协议测试从同一套既有用例选出，覆盖授权门禁、回执身份、超时、重复性、清理控制流程与行为差异，4.501 秒全部通过。测试中使用的合成凭据不构成任何真实运行回执。 [适配器测试说明](RUNTIME_ADAPTER_READINESS.md)

实际 ARM ELF、SDK、原始报告和完整执行日志保留在获准工作区。Git 交付为审查文档及可机器读取的冻结身份。 [剩余条件](REMAINING_GAPS.md)
