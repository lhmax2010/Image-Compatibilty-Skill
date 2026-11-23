# 正式 SR Runtime 环境准入

**未找到已授权且已核实运行对应 SR 镜像的实体设备或 Guest。正式四象限 0/8。** 本轮在 x86-64 宿主只读盘点了设备相关工具与进程。可见 `/dev/kvm`、QEMU User、Bubblewrap 及已有 SDB 进程。未发现可用的 QEMU System ARM/aarch64、Docker、Podman 或 libvirt CLI。SDB 进程只能说明有本地 daemon，实际设备和接入事实未核实。两侧留存 Rootfs 的 `/boot` 均为空。Phase 8E 已检查发布归档内 rootfs、system-data 与启动/恢复 ramdisk 内容，缺少已匹配的 Kernel/DTB、板型和启动参数。 [历次盘点](../phase8e/RUNTIME_ENVIRONMENT_OPTIONS.md) · [QEMU Arm System 的板型要求](https://www.qemu.org/docs/master/system/target-arm.html)

## 已有的静态 Loader/库参考

下表来自留存 Rootfs。原始解释器请求为 `/lib/ld-linux.so.3`。使用 `Image.resolve` 仅在映像内解析链接，再以 `readelf -n` 和 SHA256 记录已检查的文件。上机后还需观测实际选择的路径和加载文件。

| 映像 | 目标组件 | 已解包文件 SHA256 |
| --- | --- | --- |
| VD | ld-linux.so.3 | `0b1fe895ab844a3dfb04a2ab034a6fca9aeadb570abd49b36bf4be16a676f4df` |
| VD | libc.so.6 | `f5a377a3121928d31111fa3a556a5ffe16014dc75254620bf2257d5ab7c1e4d4` |
| VD | libstdc++.so.6.0.33 | `52926e5bed922340320697b451689e51ed7ff45f0099d606c7f7c449a5e58520` |
| VD | libgcc_s.so.1 | `d05fc30b89f48f4154bb125978a9e55f68c0eed8aa4faf2084839d2c735eb9e0` |
| LLVM | ld-linux.so.3 | `b011ebe723dc6e8115f4eb44c964817f7d61878e44d6de3a9367e7359b5bf7da` |
| LLVM | libc.so.6 | `9f2ae4ee0d10374c7681a33b09b5a84dbfca82c3d1bc012edf81483f11202b96` |
| LLVM | libstdc++.so.6.0.33 | `871c24ae874b77d767cffff6933886566985326e20fd787bdd9892816284ae53` |
| LLVM | libgcc_s.so.1 | `904b67964d3e751b9d9213fdb0b7643bf18d5e15294a0fb50782c580610cdb25` |

源码包和实际启动身份分别校验。冻结清单提供两套发布镜像与 SDK 摘要，静态检查日志提供参考库摘要和 Build-ID。日志 SHA256 为 `42cbf51ed43d4aa8398fd8b8ef5b7c5e33ef928782283b13829391e5e25bacae`。 [镜像身份](../phase8e/ARTIFACT_MANIFEST.json)

## 目标侧缺失的证据

1. 取得用户对具体设备或匹配 Guest 的授权，固定快照、设备/Guest ID、实际 Kernel/DTB/启动配置及恢复方式。Guest 可直接使用的板型和内核支持还缺实测。普通 x86-64 KVM 观察无法证明 ARM Guest 能启动。
2. 在目标侧采集 ARMv7-A、Thumb-2、VFP/NEON 所需的 CPU/HWCAP 与执行配置。明确 ARM EABI5/Base PCS 探针的权限、UID/GID、挂载范围和加密/隔离传输。
3. 绑定实际 Loader 和上表运行库的解析路径、SHA256、Build-ID 与搜索配置。核对专用写入目录、只读产品挂载、租约超时、部署 digest、断线回收及原始回执存储。
4. 用可信 controller 对获批目标完成一次部署及强制失败清理验证，再执行各产物的原生参考。Kernel 级行为、Smack、AT_SECURE 和 Namespace 需要独立目标证据及授权。

可行路线依次是已授权且匹配的设备或 Guest、补齐启动件和资源后使用隔离 QEMU System、独立授权的 QEMU User 冒烟。后者只覆盖受控用户态投影。 [冻结入口](FROZEN_RUNTIME_ENTRY.md) · [限定冒烟](QEMU_USER_SMOKE_READINESS.md)
