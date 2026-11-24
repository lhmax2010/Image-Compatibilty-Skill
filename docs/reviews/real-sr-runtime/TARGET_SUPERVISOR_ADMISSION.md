# 目标监督和独立退出验证

**VERIFIED，适用于本轮实际执行的受控探针。** 设备上用户级 systemd 244 可用。当前 SDB shell 对检查过的 cgroup v1 控制器目录和 `cgroup.procs` 无直接写权限，但已有用户 manager 能为调用方创建临时 `.scope`。本轮仅使用 `systemd-run --user --scope` 管理调用方进程。设备上没有新建或启动服务，也没有修改全局控制策略。另核对设备上有 Toybox `timeout`、`setsid`、`ps` 和可读 `/proc`。实际外层超时与回收由 scope 管理。 [systemd 244 scope 定义](https://raw.githubusercontent.com/systemd/systemd/v244/man/systemd.scope.xml)

每项使用独立 Attempt ID、私有目录、scope 和第二个 SDB 观察会话。观察员从内核 `cgroup.procs` 与 `/proc` 记录实际受测 PID、PPID、PGID、SID、权限、starttime、工作路径和 cgroup 的设备号、inode。每个控制实验的子 `sleep` 通过 `setsid` 进入与父 Shell 不同的 Session，实测仍在相同 cgroup。运行中读回 `RuntimeMaxUSec=5s`、`TimeoutStopUSec=1s`、`KillMode=control-group`。

| 无害控制实验 | 实际远端退出 | 独立清理观察 |
| --- | --- | --- |
| 正常退出 | 0 | 观察到主进程与子进程。退出后原进程未存活，cgroup 和私有目录不存在。 |
| 非零退出 | 17 | 同上，保留实际非零行为状态。 |
| 在 scope 内等待有限长任务 | 143，scope 的 Result 为 `timeout`，外层观察耗时约 5.43 秒 | 观察到两个 Session 的任务均进入 cgroup。随后无原进程残留，cgroup 和目录不存在。 |

真实探针分别用上限 10 秒和 1 秒终止宽限，运行中读取同样的控制属性。待执行 Shell 必须先被独立会话验明身份、cgroup 和期限，才开放一次性执行许可。Shell 使用 `exec` 保持 PID，Loader 日志文件名与该进程 PID 一致。探针退出后再次读回内核路径和起始时刻记录。清理按已知文件名删除，再删除空私有目录，第二会话确认不存在。

最终定向复核覆盖 3 个控制实验与 4 个真实探针的目录和 cgroup，均不再存在。对唯一的本次超时控制 scope，先确认 `Transient=yes`、`Result=timeout` 且无内核 cgroup，再清除该临时单元的失败状态，复查为 inactive。最终保留原始超时证据。本地 `final-device-cleanup.stdout` SHA256 为 `67e811605781ff0b37a125c6fe5225295dedab2034b4f20fd5fbb62a9555cdea`，单元复查记录为 `owned-timeout-scope-release.stdout`。 [实际运行结果](HEADED_RUNTIME_RESULTS.md)

本轮监督证据来自设备内核和独立会话。正式 Adapter 未集成此流程，已有 Runtime 门禁继续保持不变。 [既有清理门禁](../phase8h/RUNTIME_CLEANUP_GATE.md)
