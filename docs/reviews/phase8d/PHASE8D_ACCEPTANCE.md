# Phase 8D 验收

基线 `fb36ff683c058b140a9c4b9fd84c8f41b7d941a5`。**匹配的最小 SDK 和编译链接验收 PASS，阶段整体为 CONDITIONAL PASS**，SQLite 全量索引仍受工作卷约束。生产检测代码保持原样。

| 验收项 | 结果 |
| --- | --- |
| VD 原生 SDK | PASS。Tizen GCC/G++ 14.2.0 和 GNU ld 2.43，Base Dev ARMv7l Sysroot，绑定 VD 运行镜像。 |
| LLVM 原生 SDK | PASS。Clang 22.1.8 / LLD 22.1.8，Base Toolchain ARMv7l Sysroot，绑定 LLVM 运行镜像。 |
| 真实直接探针 | 12 项，10 项编译并链接成功，2 项编译成功后按预期因指定的不存在版本链接失败。0 个非预期失败。 |
| Skill 真实集成 | run_matrix 配置两个独立 SDK，重复基础 C/C++ 各两项，四项构建完整通过。计划生成 12 个唯一 ID，缺失的 8 个全是未执行的 runtime，重复和意外 ID 均为 0。 |
| 产物离线核对 | 对四组构建/镜像配对各做 A、B、C 正例和 D 文件核对，合计 16 次。192 次版本化导入检查在指定库中命中。VD C++ 的三个 R_ARM_COPY 对象在两个镜像额外逐项核对。 |
| Runtime | 两个产物来源已明确，部署、执行、原生行为参照仍为 NOT VERIFIED。 |
| SQLite | NOT VERIFIED。空间低于既有预算，未启动构建。 |

验收探针合计 16 项真实编译链接尝试，包含集成层对基础 C/C++ 的四次重复验证。其中 14 项成功，另 2 项为预期链接失败。初始 Rootstrap、头文件补齐和本地封装诊断另记，未计入正式结果。VD 基础 C 产物为 ET_EXEC，LLVM 为 PIE。两者都符合 ELF32 ARM、EABI5、Base PCS、解释器和目标库检查。原始两套归一化 TAR 的 SHA256 与 Phase 8C 记录一致。 [C 探针](C_COMPILE_LINK_RESULTS.md) · [C++ 探针](CPP_COMPILE_LINK_RESULTS.md) · [SQLite](SQLITE_FULL_ACCEPTANCE.md)

## 模型与指标范围

| 构建来源 | VD 原生参照 | LLVM 原生参照 |
| --- | --- | --- |
| GCC，绑定 VD SDK | 构建 PASS，指定文件匹配，未执行 | 指定文件匹配，未执行 |
| Clang，绑定 LLVM SDK | 指定文件匹配，未执行 | 构建 PASS，指定文件匹配，未执行 |

上表的构建 PASS 只适用于各自 SDK 编译和链接。各镜像上的固定库核对来自静态 ELF 文件，没有发出运行回执或宣称产品兼容。

## 自动化回归

```bash
python3 -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v
git diff --check
```

共 249 项，244 PASS、5 SKIP、0 FAIL，用时 79.222 秒。5 项跳过为 libabigail 集成、Clang AST/ARM 集成、依赖宿主 Clang 的显式探针调度、Clang ARMv6/v7/VFP、Clang hard/softfp/soft PCS。仓库回归需要其中某些宿主路径和配置。Phase 8D 的 Tizen 工具仅通过各自隔离入口执行，实际矩阵没有使用模拟回执。

正式直接探针墙钟 1.04 秒、峰值 RSS 16,916 KiB。Skill 目标编译与证据核对为 2.22 秒、29,476 KiB。此处来自 /usr/bin/time 的单次记录，包括驱动或调度进程及其可见子进程。SDK 提取产物合计约 2.4 GiB，RPM 约 633 MiB。真实全量 SQLite 的资源见单独记录。 [资源与来源](SDK_ACQUISITION.md) · [下一阶段准入](REMAINING_GAPS.md)

## 构建记录

| Expected Test ID | 编译器 / 原生 SDK | 语言 | 验证 |
| --- | --- | --- | --- |
| ET-6a364caf65f96a0d1b4cc16a | GCC / VD | C | COMPLETE |
| ET-5cdc6d54304c1467ab4df421 | GCC / VD | C++ | COMPLETE |
| ET-a30c22232ec1fb84befa821d | Clang / LLVM | C | COMPLETE |
| ET-fa83a4af8aa6b3cec9868adb | Clang / LLVM | C++ | COMPLETE |

| 原生构建 | 探针 | 直接产物 SHA256 |
| --- | --- | --- |
| vd | A-C | `8b9a99ab11fff447022618f796ee397cccd21fbaf4d30a29d9561647c3f687fc` |
| vd | B-CPP | `e667142e73f25ed285f81f0b6c4f8e681fb375cc3e6c054e5d20950b50c07d73` |
| vd | C-version-present | `bb99ce69059e76e0564e311906e83ff782381b161b5bc6380a621f4f1fd9c7bd` |
| vd | C-version-export | `3f516f393f52e6f108656b5ae549b164948de527dc576bd797e822fdc8f3b572` |
| vd | D-profile | `ea226865ed524e25b3d3a8125ad1467168d7f86dace2d8244bb6856e7ddf5cd0` |
| llvm | A-C | `e4987d1628770f2dfa5f6b13d95fc1ed3cdd235651d3ca26e3812aea41f01606` |
| llvm | B-CPP | `5c1cc3d271e9062291e02c39704f932ed8fe4ad41174816bb929cea27446517c` |
| llvm | C-version-present | `71ca0316aef7e662e8a36e6267137846cf35a1e8f49ea72b4d9ecb05a30f9b9b` |
| llvm | C-version-export | `8ed9567aec3b93c856b43470e0fa9fd14c06a36563798dbf7b7d28d67f3b706f` |
| llvm | D-profile | `df91b1ef2c6405f6776eb68c5f809b54c71ffdeefd8de7e70d7d2a27bc4e4821` |

完整的已校验 RPM、提取目录、实际 argv、链接 map、原始探针和审核记录保存在获准工作区，不随仓库上传。
