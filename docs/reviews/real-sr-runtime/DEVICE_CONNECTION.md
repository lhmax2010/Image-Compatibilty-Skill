# 真实设备连接

通过现有 SDB 会话成功连接授权目标 T1。开始和结束的在线表均含该授权序列，`sdb devices` 返回 0。随后只对该序列使用 `sdb -s <authorized-serial> shell`，三项只读采集的 SDB 返回码均为 0。服务端与客户端版本分别为 4.2.25 和 4.2.36，客户端报告版本告警，采集脚本正常打印结束标记和实际远端命令退出码。已有连接保留，SSH 回退未使用。

| 远端采集 | 观察 |
| --- | --- |
| 型号与架构 | Raspberry Pi 4，`armv7l`，4 个 ARMv7 核，具备 Thumb、VFPv3/VFPv4 与 NEON。 |
| 系统 | Tizen 11.0.0，内核 6.12.80。启动约 1,149 秒，1/5/15 分钟 load average 为 1.06 / 1.06 / 0.80。 |
| 会话 | 已读取实际 UID/GID，确认是非 root 的 SDB shell。详细账号与设备标识只保存在本地。 |
| 内存与挂载 | MemAvailable 3,423,280 KiB。根为只读 ext4，`/opt` 为可读写 ext4。具体可写性和执行边界见清理记录。 |
| 命令异常 | `hostname` 返回 127。使用 `/proc/sys/kernel/hostname` 成功读取主机名并留存本地。 |

原始连接表、每段命令、stdout/stderr、退出码、开始和结束时间在 workspace 的 `.local-backups/real-sr-runtime/`。连接表可能含其他已登记设备的标识，仅保存本地。本轮所有目标命令均明确绑定 T1。 [镜像身份](DEVICE_IDENTITY.md) · [目标边界](TARGET_CLEANUP_VALIDATION.md)
