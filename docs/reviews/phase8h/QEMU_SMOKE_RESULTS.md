# 首次 GCC C → VD 冒烟记录

**QEMU_USER_SMOKE BLOCKED，ARM 实际执行 0 次。** 专用账号、独立资源 cgroup 与 Step A 明确授权均缺失。本轮只执行 QEMU 自身的版本和 CPU 模型查询及宿主 Controller 合成测试。未运行冻结 ELF、Loader 或 libc。 [准入记录](EXECUTION_ADMISSION.md)

| 静态核查对象 | 本轮重新匹配的 SHA256 |
| --- | --- |
| 原始 GCC C 字节 `vd-A-C` | `8b9a99ab11fff447022618f796ee397cccd21fbaf4d30a29d9561647c3f687fc` |
| QEMU `qemu-arm-static` 5.2.0，模型候选 `cortex-a9` | `cdfc34eccbfd6d46bca8983713845aa04bfb9c5505abb6e6ae6ea85bed6ef22e` |
| VD `/lib/ld-linux.so.3` | `0b1fe895ab844a3dfb04a2ab034a6fca9aeadb570abd49b36bf4be16a676f4df` |
| VD `/lib/libc.so.6` | `f5a377a3121928d31111fa3a556a5ffe16014dc75254620bf2257d5ab7c1e4d4` |

实际打开或映射的库、退出码、stdout、stderr、目标超时和目标清理均无实测。若准入及获批，只运行 Step A，使用有界且独立的宿主系统调用证据记录 QEMU 实际打开和映射的文件，对照冻结摘要。预期 stdout `536768647\n`、退出 0、stderr 为空，比较时应以实际记录为准。任一证据缺失或发现异常均停止。本轮无 C++、跨镜像或正式产品执行，正式 SR Runtime **0/8**。 [Phase 8G 静态输入与预期](../phase8g/QEMU_SMOKE_RESULTS.md) · [目标清理证明方案](RUNTIME_CLEANUP_GATE.md)
