# 独立目标退出与信任边界

Controller 的退出只提供信号或返回码。适配器单独使用多个 SDB shell 读取目标内核和用户 manager，核对本次设备端点、boot ID、Attempt ID、目录身份及冻结 SHA256。

- 运行期读取实际 scope 的控制组路径、inode、任务列表、期限和 `KillMode=control-group`，以及 armed Shell 的 PID、starttime、PGID、Session、UID 和 capabilities。详细 PID 材料使用短独立请求并对比分拆前抓到的 starttime，放行命令再次核对目标 PID 及 cgroup。
- 退出后查询最早观测到的全部活任务。重新使用同一个 PID 只能在 starttime 不同或原进程已终止时排除。核实原 scope inactive 或 failed，内核 cgroup 消失或同 inode 下无任务且无子组。只删除已登记的测试文件并要求空目录可删除，再由独立请求确认目录消失。
- 每个观察响应有独立随机挑战和原始证据 ID。核对观察端 PID、观察顺序、现场绑定和新鲜度。连接中断、自称 `cleanup: ok`、缺失或过期数据均不能自行满足清理证明。原始 JSON 不是供调用方注入 VERIFIED 的输入。

真实设备上的用户 scope `cgroup.procs` 对该 UID 可写。验证器记录这一实测条件和 `Delegate=no` 状态。本轮的目标清理通过仅覆盖白名单中的实际采样进程、cgroup 和对应私有目录。它不能独立保证同 UID 的任意代码无法迁移任务，也无法给同一 SDB 通道提供额外的强认证。

因此新报告可给本次观测 `target_cleanup_status=VERIFIED`，原有严格字段 `target_process_cleanup_status`、`formal_runtime_status` 和正式 `native_reference_status` 均保持 `NOT_VERIFIED`。未修改 `frozen_runtime.py` 的任何门禁。正式证明仍需独立可信的目标监督身份和不可由被测代码操纵的进程归属或等强度证据。 [原正式退出门禁](../phase8h/RUNTIME_CLEANUP_GATE.md)
