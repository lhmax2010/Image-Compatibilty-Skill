# ARMv7 QEMU User 限定冒烟准备

**隔离原语通过宿主合成检查，目标 ARM 冒烟为 NOT_EXECUTED。** 已安装的 `qemu-arm-static` 5.2.0 是 x86-64 静态工具，SHA256 为 `cdfc34eccbfd6d46bca8983713845aa04bfb9c5505abb6e6ae6ea85bed6ef22e`。只执行过宿主工具的 `--version`、`-cpu help` 及无目标程序的参数探测，CPU 列表包括 Cortex-A7/A8/A9/A15。Cortex-A9 作为 ARMv7-A、Thumb-2、NEON/VFP 的候选模型。EABI5 和 Base PCS 来自冻结 ELF 和目标库检查，模型的实际指令及系统调用覆盖仍待授权冒烟。 [QEMU User 文档](https://www.qemu.org/docs/master/user/main.html) · [冻结产物](../phase8e/ARTIFACT_MANIFEST.json)

Bubblewrap 0.9.0 在本机通过宿主 x86-64 合成探针。进程 UID 非零，`NoNewPrivs=1`，有效 capabilities 为零，网络接口仅有独立 loopback，容器看不到宿主 `/usr` 或 `/home`，根目录写入得到 EROFS，自有 16 MiB tmpfs 可写。宿主侧日志 SHA256 为 `3cad7b854b75cb5d813710744e5b41089d97020007535a759d9cca124bbe50c2`。此预检尚未在未来实际配置的专用测试账号或 SR 库投影中重测。 [Bubblewrap 参数与信任模型](https://github.com/containers/bubblewrap)

## 获得单独授权后的第一项

准备选定 SR 的只读库投影。只带实际需要的 `/lib/ld-linux.so.3`、`/lib`、`/usr/lib` 中经过审核的同侧库及必要配置，包含 SONAME 符号链接和对应备份文件。基础 C 需要该侧 libc。基础 C++ 还可能需要 libstdc++、libgcc_s、libm，按每个产物和各库的 `DT_NEEDED` 递归核对。明确是否带入目标 ld.so.cache、预加载配置或搜索路径，首项将它们排除并记录为受控库投影。所有投影文件按目标虚拟路径解析并冻结摘要，清除测试副本中多余的权限和元数据，只允许普通探针。以专用低权限账号核对 namespace、挂载、资源与清理后再启动。相关挂载点、输出目录和只读文件由已授权准备工作提供。

以下是获批后的 GCC C → VD 首项命令。变量须为已审核的绝对路径，`VD_C` 指哈希校验过的 Phase 8E 原始字节副本。执行前核对模拟器及产物和所有库的 SHA256，检查文件无 setuid/setgid/capability。账户的进程数、物理内存和日志限额由操作员额外限流，进程组由外层监督和收集。

```bash
timeout --kill-after=2 15 prlimit --cpu=10 --as=8589934592 \
  --nproc=32 --nofile=64 --fsize=1048576 -- \
  bwrap --unshare-all --unshare-user --die-with-parent --new-session \
    --cap-drop ALL --clearenv --proc /proc \
    --perms 1777 --size 16777216 --tmpfs /tmp \
    --dir /lib --dir /usr --dir /usr/lib --dir /runner \
    --ro-bind "$VD_LIB" /lib --ro-bind "$VD_USRLIB" /usr/lib \
    --ro-bind "$QEMU_ARM_STATIC" /runner/qemu-arm-static \
    --ro-bind "$VD_C" /runner/probe --remount-ro / --chdir /tmp \
    --setenv LC_ALL C --setenv TZ UTC \
    /runner/qemu-arm-static -cpu cortex-a9 -L / /runner/probe \
  </dev/null >"$NEW_SMOKE_DIR/stdout" 2>"$NEW_SMOKE_DIR/stderr"
```

基准 GCC C 预期退出 0、stdout 为 `536768647\n`、stderr 为空。行为运行和带 QEMU `-strace`、`-E LD_DEBUG=libs,versions` 的诊断运行分别保存，后者核对 Loader 搜索、目标虚拟路径、符号版本和读到的库摘要。宿主库路径不挂载进投影，可再核对实际打开记录。捕获外层退出、目标退出证据、超时、stdout/stderr、库和产物摘要，再逐项增加 C++ 和相同字节的跨侧投影。

| 后续对照 | 预期 |
| --- | --- |
| 产物、Loader 或 Provider 摘要变更 | 启动前被拒绝 |
| 去掉解释器或所需 Provider、选错 GNU 版本 | 得到可定位的模拟器或 Loader 启动失败 |
| 使用缺少所需 ISA 的模型、不可用系统调用 | 独立记录模拟限制，覆盖保持未知 |
| 保留有效启动证据但模拟行为输出不同 | 记录该投影上的观察差异 |
| 进程超时或断线 | 回收本地隔离进程，保留原始输出，避免授予行为完成 |
| 反向检查文件权限、网络与根目录 | 保持非特权、外部网络不可用和不可写根目录 |

报告标记 `QEMU_USER_SMOKE`。QEMU User 使用宿主 Kernel，结论只覆盖本次投影和模拟器下的非特权探针行为。产品 Kernel、真实 AT_SECURE、Smack、capabilities 和正式 SR 四象限仍待对应环境。 [正式环境准入](TARGET_ENVIRONMENT_READINESS.md)
