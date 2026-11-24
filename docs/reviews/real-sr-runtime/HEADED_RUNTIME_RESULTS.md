# SR_HEADED_RUNTIME 实测结果

当前 LLVM headed 设备上共执行 **4 项**，全部退出 0、stdout 与冻结预期逐字节一致、stderr 为空，并通过独立退出及文件清理验证。先执行 Clang C，再执行 Clang C++，两者完整验证后再依次运行 GCC C 和 GCC C++。源文件和目标部署文件的 SHA256 每项一致。

| 产物 | 实测部署 SHA256 | 目标退出 | stdout | 实际版本检查记录数 |
| --- | --- | ---: | --- | ---: |
| Clang C | `e4987d1628770f2dfa5f6b13d95fc1ed3cdd235651d3ca26e3812aea41f01606` | 0 | `536768647\n` | 8 |
| Clang C++ | `5c1cc3d271e9062291e02c39704f932ed8fe4ad41174816bb929cea27446517c` | 0 | `N12_GLOBAL__N_16WidgetE\n` | 35 |
| GCC C | `8b9a99ab11fff447022618f796ee397cccd21fbaf4d30a29d9561647c3f687fc` | 0 | `536768647\n` | 5 |
| GCC C++ | `e667142e73f25ed285f81f0b6c4f8e681fb375cc3e6c054e5d20950b50c07d73` | 0 | `N12_GLOBAL__N_16WidgetE\n` | 35 |

本轮以普通执行路径运行原始 ARM ELF，每项只运行一次。同一次运行里用 glibc 的 `LD_DEBUG=libs,versions,files` 采集动态诊断，诊断写入独立文件。根据实际 PID 和 Loader 记录关联对应进程，结合 `calling init` 路径重新解析并哈希实际加载文件。每项的 stdout、stderr 和 Loader 日志通过 SDB 二进制拉取，目标与宿主 SHA256 逐个一致。

| 实测已加载接口 | 最终解析文件 | SHA256 | 覆盖 |
| --- | --- | --- | --- |
| Loader | `/usr/lib/ld-linux.so.3` | `b011ebe723dc6e8115f4eb44c964817f7d61878e44d6de3a9367e7359b5bf7da` | 4 项 |
| libc | `/usr/lib/libc.so.6` | `9f2ae4ee0d10374c7681a33b09b5a84dbfca82c3d1bc012edf81483f11202b96` | 4 项 |
| libgcc_s | `/usr/lib/libgcc_s.so.1` | `904b67964d3e751b9d9213fdb0b7643bf18d5e15294a0fb50782c580610cdb25` | Clang C 和两项 C++ |
| libm | `/usr/lib/libm.so.6` | `3ed8dbce48a46dd38779d7aba07acf90404ae9a6a8ba5e6104577f357136adf1` | 两项 C++ |
| libstdc++ | `/usr/lib/libstdc++.so.6.0.33` | `871c24ae874b77d767cffff6933886566985326e20fd787bdd9892816284ae53` | 两项 C++ |

版本诊断实际包含 C 所需的 `GLIBC_2.4`、`GLIBC_2.34` 等检查；Clang C 还包含 `GCC_3.5`。C++ 诊断包含 `CXXABI_1.3`、`CXXABI_1.3.9`、`GLIBCXX_3.4.29` 等。计数包含当前进程依赖链的检查记录。四份 Loader 日志、逐版本明细、运行计划 ID、开始时刻、实际退出码、现场身份及清理证据保留在 workspace 的 `.local-backups/real-sr-runtime-headed/`。本地汇总 `headed-summary.json` SHA256 为 `7d50629f91034a4cda54489af21e987514cdc6569355f636bb0ed9339fe3b62a`。

LLVM headed 原生执行观察 **2/2**，GCC 在该设备上的行为观察 **2/2**，跨镜像兼容性结论 **0**。原始 headless 正式矩阵 **0/8**。未改动生产代码，基线工具回归结果保留。本轮通过实际设备实验、原始哈希对账和独立清理复核验证。 [独立退出证据](TARGET_SUPERVISOR_ADMISSION.md) · [下一步准入](NEXT_RUNTIME_STEPS.md)
