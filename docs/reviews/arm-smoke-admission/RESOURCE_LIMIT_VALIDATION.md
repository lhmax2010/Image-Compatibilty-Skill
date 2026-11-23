# 独立资源限制

**NOT_VERIFIED。** 实际启动次数为 0。当前共享 cgroup 的配置没有被当成专用环境证据。

| 独立服务限制 | 预期内核或外层值 |
| --- | --- |
| MemoryMax | `memory.max=268435456` |
| MemorySwapMax | `memory.swap.max=0` |
| CPUQuota | `cpu.max=100000 100000` |
| TasksMax | `pids.max=32` |
| 墙钟和终止升级 | `RuntimeMaxSec=15s`、`TimeoutStopSec=2s` |
| 私有临时空间 | 16 MiB tmpfs |
| 输出 | stdout/stderr 合计 1 MiB，单文件 1 MiB |

脚本在已授权的独立瞬态 Service 上设置这些值，要求运行中直接读取内核文件和任务归属。记录设备号、inode、实际 PID/starttime、CPU/内存/任务用量及 `populated`，并在观察到任务进入后复核同一 Slice 为空。每次宿主负载只有约 1 MiB 触碰内存、短 CPU 循环、少量子进程及固定的输出上限对照，不跑共享主机压力测试。生效证明取决于实际运行和内核读数，日志写入 workspace 私有目录。 [资源观察实现](../../../.agents/skills/tizen-image-compatibility/scripts/arm_smoke_admission/preflight.py) · [内核 cgroup v2](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)
