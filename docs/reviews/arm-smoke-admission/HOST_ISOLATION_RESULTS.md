# 宿主 x86-64 隔离验证

**NOT_VERIFIED。** 本轮宿主替代程序已完成带警告门禁的静态 x86-64 编译，ELF 架构与静态链接已读回。实际专用账号和独立 cgroup 尚未建立，替代程序未在本轮启动。

预检最后的可执行文件固定为 `/runner/host-only`。它检查实际 UID/GID、补充组、`NoNewPrivs`、capability、PID/网络/挂载命名空间、除 loopback 外无其他接口、私有 16 MiB tmpfs、可见根只读和实际文件只读挂载。QEMU 和 ARM 文件仅作为只读输入，宿主替代程序读取 ELF 头部。没有从测试环境连接公网、启动 ARM ELF 或使用外部设备。 [宿主替代程序](../../../.agents/skills/tizen-image-compatibility/scripts/arm_smoke_admission/host_probe.c)

输入 SHA256 已重新匹配，没有建立特权投影副本。任务附件的 VD Loader 摘要少了一个 `b`，只有 63 位。本轮以 Phase 8H 已冻结的 64 位摘要 `0b1fe895ab844a3dfb04a2ab034a6fca9aeadb570abd49b36bf4be16a676f4df` 重新核对了实际文件。Phase 8H 的只读身份、Phase 8G 的共享账号宿主测试仍属各自历史记录。 [既有身份表](../phase8h/QEMU_SMOKE_RESULTS.md) · [本轮管理员准入](ENVIRONMENT_SETUP.md)
