# SR ARMv7 Runtime 环境可行性

## 现场和启动材料

只读检查未发现已核实运行这两个 SR 快照的 Guest、已授权设备或设备接入记录。PATH 上有 Tizen qemu-arm-static 5.2.0-tizen20240722、bwrap 和 SDB。未找到 QEMU System ARM/aarch64、Podman、Docker 或 libvirt 管理工具。仅观察到已有 SDB 进程，未启动、连接或枚举设备。宿主为 x86_64，存在 /dev/kvm；这只表明宿主有 KVM 接口。未启动 ARM 代码或 Guest。

现有两个发布归档均记录 rootfs.img、system-data.img、ramdisk.img、ramdisk-recovery.img。两个根目录的 /boot 为空。对四份已有 gzip/newc Ramdisk 仅列目录，VD 启动/恢复分别 129/262 项，LLVM 128/259 项，未找到独立 Kernel/DTB 启动件。没有可用于认定 SR 镜像能直接启动的板型、内核、设备树、启动参数和验证回执。 [Phase 8C 输入身份](../phase8c/COVERAGE_BEFORE_AFTER.md)

## 候选路线

| 顺序 | 路线 | 可用性与所需资源 | 主要风险与验收边界 |
| --- | --- | --- | --- |
| 1 | 匹配 SR 的真实设备，或已验证的隔离 Guest | 需用户提供设备/Guest、镜像及启动件身份、访问方式、测试账号、隔离和清理授权 | 设备应确实运行相应 VD/LLVM 版本，须查 CPU/HWCAP、实际加载器、运行库、权限和挂载。 |
| 2 | 授权的 QEMU System ARM + 匹配 Kernel/Boot | 当前缺 System emulator、匹配 Kernel/DTB、兼容板型、启动配置和工作卷。需要额外授权安装或下载。 | QEMU ARM 的可启动性依赖板型和内核。若用支持 virt 的替代内核，只能按实际保真的 Guest 范围验收。保持产品 Rootfs 只读，系统写入和测试输出使用新覆盖层。 |
| 3 | 另行授权的隔离 QEMU User 冒烟 | 本机有 ARM 用户态模拟器。仍需在授权文件和权限边界内建立不可联网的隔离运行方以及两份经核对的用户态。 | 只能验证限定用户态行为。系统调用接到宿主内核，无法复用为完整设备、Tizen Kernel、Smack 或特殊加载行为的验证结论。 |

QEMU 的 ARM System 文档要求选择实际板型，并将不同硬件环境的 Kernel/DTB 兼容性作为启动前提。Linux User Mode 使用宿主内核，仍需独立隔离。 [QEMU ARM System](https://www.qemu.org/docs/master/system/target-arm.html) · [QEMU virt](https://www.qemu.org/docs/master/system/arm/virt.html) · [QEMU User Mode](https://www.qemu.org/docs/master/user/)

当前四份分区文件合计 VD 724,906,964 B、LLVM 703,351,896 B。若选择 Guest，申请的存储应分别覆盖只读输入、Kernel/DTB、可回收写入覆盖层和日志。单次启动的 vCPU、RAM 和覆盖层配额由匹配的内核配置及宿主预算确定，当前缺少真实启动数据。设备路线还需要批准设备接入与恢复流程，刷机另行审批。

## 目标一旦获准需要记录的字段

- 镜像来源、Rootfs/Opt 分区摘要、实际 Kernel 及 DTB 摘要、设备/Guest ID 和启动参数。
- 实际 ARMv7-A、Thumb-2、NEON/VFP 能力与探针的 ARM EABI5、Base PCS、softfp 证据。仅 ELF 元数据无法确认 CPU 能力。
- 实际 /lib/ld-linux.so.3、libc、libstdc++、libgcc_s 的解析路径、文件 SHA256 和 Build-ID。
- 实际普通测试用户、UID/GID、挂载只读边界、专用可写区、进程组清理机制及隔离传输。AT_SECURE、Namespace、特权和 xattr 验证另行准入。
