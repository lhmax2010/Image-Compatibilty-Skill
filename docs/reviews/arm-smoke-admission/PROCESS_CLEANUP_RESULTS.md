# 实际进程回收验证

**NOT_VERIFIED。** 本轮没有运行专用 Service，缺少本轮活任务进入、同一 cgroup 清零或独立 UID 无遗留的成对实测。

准备的组合包括正常退出、退出 17、墙钟超时、SIGINT、SIGTERM、子进程关闭输出管道、子进程创建独立会话、输出超限、以及控制流程提前退出。每项必须先在已核验的 Slice 看到 `populated 0`，再从服务子组记录任务、内核 cgroup 归属和 `populated 1`，最终在原 Slice inode 复核 `populated 0`、空任务表和专用 UID 无外部进程。stdout/stderr 达到总上限或客户端提前退出时，观察员只对本次登记的 unit invocation 请求停止。任一情况证据缺失都会中断下一项。 [独立观察代码](../../../.agents/skills/tizen-image-compatibility/scripts/arm_smoke_admission/preflight.py)

Controller 自报的清理信息不用于证明本轮退出。宿主测试通过后也仍仅属于宿主环境准入。 [Phase 8H 目标退出边界](../phase8h/RUNTIME_CLEANUP_GATE.md)
