# 执行准入与目标退出验证

从授权的 SDB 会话读取了实际、有效和保存的 UID/GID。三者一致且为非 root，CapEff 与 CapPrm 均为零。当前 shell 的 NoNewPrivs 为 0，未验证未来探针执行时的独立权限约束。精确账号、UID/GID 和组列表只保存本地。

| 准入项 | 实测结果 |
| --- | --- |
| 可用内存和负载 | 只读检查完成。约 3.3 GiB MemAvailable，1 分钟负载 1.06。 |
| 临时目录 | `/tmp` 和用户的运行时目录对当前会话可写，对应 `/tmp` 和 `/run` 挂载均为 `noexec`。 |
| 其他候选 | `/opt` 为读写挂载，检查过的候选对当前会话均未通过 `test -w`。本轮未发现同时可写和可执行并经过授权的测试目录。 |
| 完整性与控制工具 | `sha256sum` 在只读库检查中成功。检测到 `timeout`、`setsid`、`ps` 和 `systemd-run`，其目标侧端到端行为未验证。 |
| 独立回收 | 当前会话位于 SDB 服务的 cgroup v1 边界，检查的 cgroup 及 `cgroup.procs` 对该身份不可写。未建立本次运行的独立边界、期限与退出观察。 |
| 清理结果 | NOT_APPLICABLE_NO_DEPLOYMENT。未创建测试目录或上传文件，未启动冻结程序，未触发目标清理。 |

Controller 回执和本地 SDB 退出均不授予独立目标退出证明。本轮未变更 Adapter 或正式清理门禁。以后必须在完整镜像身份核验通过后，由目标侧可独立观测的运行边界证明任务实际进入、受控并退出，然后才累计正式 Runtime。 [Phase 8H 清理门禁](../phase8h/RUNTIME_CLEANUP_GATE.md)
