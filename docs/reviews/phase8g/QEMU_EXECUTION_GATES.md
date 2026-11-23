# 首次 QEMU User 执行准入

**首个 ARM 执行 BLOCKED。** 冻结身份、VD 两文件库投影和当前账号下的宿主合成隔离已核对。当前账号是日常账号，具有补充组权限，未发现已授权的专用低权限测试账号。当前任务 cgroup 的 `memory.max=max`、`cpu.max=max 100000`、`pids.max=34352`，未取得独立授权的限额 cgroup。当前 UID 已有约 1,784 个线程，超出拟议的 32 任务上限。目标执行尚无授权。

| 准入 | 本轮结果 |
| --- | --- |
| 模拟器 | **VERIFIED**。宿主静态 x86-64 `qemu-arm-static` 5.2.0，SHA256 `cdfc34eccbfd6d46bca8983713845aa04bfb9c5505abb6e6ae6ea85bed6ef22e`。`-cpu help` 包含 `cortex-a9`。 |
| 冻结原始字节 | **VERIFIED**。Phase 8E 清单中的 `vd-A-C`，13,348 B，ET_EXEC、ARM ELF32 EABI5、Base PCS/softfp，CPU v7、Thumb-2、VFPv3。文件未重新编译。 |
| VD 解释器与依赖 | **VERIFIED** 的静态身份。只读检查并创建同侧投影，精确文件见 [冒烟记录](QEMU_SMOKE_RESULTS.md)。 |
| 隔离 | **VERIFIED** 的宿主合成边界。Bubblewrap 0.9.0 实际绑定投影和模拟器，最后执行静态 x86-64 检查程序，ARM 文件仅打开读取 ELF 头。网络命名空间与宿主不同，仅有独立 loopback，独立 PID 根，`NoNewPrivs=1`，有效和上界 capabilities 为零，嵌套 userns 被拒。文件和根目录不可写，`/home`、`/sys`、宿主 `/usr/bin`、Loader cache 和 preload 文件不可见。 |
| 资源和回收 | CPU 10 秒、单进程虚拟地址 8 GiB、FD 64、单文件 1 MiB 与 16 MiB tmpfs 均在替代程序内读回。2 秒合成超时及正常退出的 PID namespace 子进程回收实测通过。专用账号下的任务数和硬物理内存上限仍 **NOT_VERIFIED**。 |
| 授权 | **BLOCKED**。准入齐备后需要针对该原始 ELF、模拟器、账号、输入和写入范围的明确执行授权。 |

## 仅申请第一项的执行范围

- 目标为 `vd-A-C`，SHA256 `8b9a99ab11fff447022618f796ee397cccd21fbaf4d30a29d9561647c3f687fc`，无参数，stdin 关闭。模拟器使用上表固定二进制和 `-cpu cortex-a9 -L /`。第一次只提交 GCC C → VD。
- 由用户提供专用非 root 账号。候选配置为每次运行独立 cgroup，最多 32 个任务、单核 CPU 配额和 256 MiB 物理内存硬上限。保留每进程 CPU 10 秒、AS 8 GiB、FD 64、单证据文件 1 MiB 和 15 秒墙钟限制，超时最多 2 秒内升级终止。需在专用账号复核限制和实际挂载。 [Linux cgroup v2](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)
- 沙箱只读取探针、模拟器、VD `/lib/ld-linux.so.3` 和 `/lib/libc.so.6`。使用空的 `/usr/lib`，私有 `/proc` 供本命名空间观察。工作目录为私有 16 MiB `/tmp`，沙箱其他路径只读。宿主仅在 workspace 内新建报告目录写有界 stdout、stderr、退出、进程证据和加载日志。需由授权操作员给专用账号提供投影的只读访问。
- Bubblewrap 使用 `--unshare-all --unshare-user --disable-userns --die-with-parent --new-session --cap-drop ALL --clearenv`，将文件绑定至 `/runner` 和 `/lib`，再用 `--remount-ro /` 和 `--chdir /tmp`。执行前核对父层 argv、cgroup 配置、输入 SHA256 和环境无继承。监督器实施组合 1 MiB stdout/stderr 上限。拟用单独有界的宿主系统调用跟踪，记录 QEMU 打开和映射的解释器及库，探针原始 stderr 单独保留。运行后复核加载路径、文件身份和 cgroup/PID namespace 的进程归零。 [Bubblewrap](https://github.com/containers/bubblewrap) · [QEMU User](https://www.qemu.org/docs/master/user/main.html)
- 静态预期是 stdout `536768647\n`、退出 0、stderr 为空。实际结果必须独立观察。任何身份、隔离、依赖、启动、超时、输出或清理异常都停止扩展。

本地 `projection.json` SHA256 为 `f5dfbf3e0f4b5aa41af705092d164bfcc61815981c0ceab1b98f369ddcb82ff4`，`isolation.stdout` SHA256 为 `10a1911bfac73ed6fc2b5a90ca01d14d9f2f8cb383e1e9ce656d118ff0040db2`，宿主替代程序退出 0。记录和投影均留在 `.local-backups/phase8g/`。
