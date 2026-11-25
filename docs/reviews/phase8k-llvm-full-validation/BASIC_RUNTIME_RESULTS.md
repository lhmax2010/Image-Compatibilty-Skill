# 四项冻结产物复验

目标为 Tizen Unified Toolchain 20261120.082536、`tizen-headed-armv7l`、Raspberry Pi 4。四项都使用来自 Phase 8E 的原始产物字节。每项经正式 SDB 入口运行三次，部署前后摘要一致，Boot ID 在本轮保持同一身份。

| 产物 | 冻结 SHA256 | 行为与观测清理 | 每次入口耗时秒 |
| --- | --- | --- | --- |
| Clang C / llvm-A-C | `e4987d1628770f2dfa5f6b13d95fc1ed3cdd235651d3ca26e3812aea41f01606` | 3/3 | 5.27 / 6.31 / 3.61 |
| Clang C++ / llvm-B-CPP | `5c1cc3d271e9062291e02c39704f932ed8fe4ad41174816bb929cea27446517c` | 3/3 | 4.32 / 4.18 / 3.91 |
| GCC C / vd-A-C | `8b9a99ab11fff447022618f796ee397cccd21fbaf4d30a29d9561647c3f687fc` | 3/3 | 4.66 / 6.81 / 3.61 |
| GCC C++ / vd-B-CPP | `e667142e73f25ed285f81f0b6c4f8e681fb375cc3e6c054e5d20950b50c07d73` | 3/3 | 4.73 / 12.64 / 3.85 |

12 项均退出 0，stderr 为空，stdout 逐字节匹配冻结契约。C 输出 `536768647`，C++ 输出 `N12_GLOBAL__N_16WidgetE`。设备观察了实际 `/lib/ld-linux.so.3`、实际 Provider 和 GNU 版本检查。C++ 两侧使用 `libstdc++.so.6` 和 `libgcc_s.so.1`。常规 `LD_DEBUG=libs,versions,files` 记录没有全符号绑定覆盖。

本地证据位于 `basic-*/runtime.json`、对应 Evidence 以及 `basic-*.seconds`。SHA256、Loader 文件、版本条目、计划与运行身份、stdout/stderr 和 scope 退出状态保存在每一份回执。四项 headed 观察的正式原生参考和跨镜像状态仍保持 NOT_VERIFIED / UNKNOWN。参见 [Phase 8E 冻结清单](../phase8e/ARTIFACT_MANIFEST.json)。
