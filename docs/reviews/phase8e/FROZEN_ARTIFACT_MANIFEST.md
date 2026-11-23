# 已冻结的 Phase 8D 产物

阶段基线 `3f7f32364fef47223cbae07e28cfbac8c4ff7e70`。从 Phase 8D 已验证的原生构建读取产物，逐个对照当时的 SHA256，复制到独立本地目录并设为只读。十个唯一字节对象包含四个四象限主程序、四个附加测试程序和两个共享库。Phase 8D Skill 矩阵的四个产物与四个主程序逐位一致，使用已有 Expected Test ID 绑定到同一对象。两个预期链接失败的负例没有可执行产物。 [Phase 8D 构建证据](../phase8d/PHASE8D_ACCEPTANCE.md)

机器清单使用 `tizen-compat-frozen-artifacts/v1`，文件 SHA256 为 `fe59f50a2501d0c165b5e7a3b037e969b418e06bbb8951e917412a4a06713c32`。它包含十个对象的完整编译和链接 argv、源文件与对象的 SHA256、实际 linker input 摘要、include 索引摘要、ARM 属性、版本化导入和重定位、工具二进制 SHA256、SDK 快照、原生镜像归档 SHA256 和八个运行计划 ID。实际 ELF、逐头文件摘要和原始证据仍在本地。公开清单中的工作路径是隔离环境内的虚拟路径。 [机器 Artifact Manifest](ARTIFACT_MANIFEST.json) · [SDK 包锁定记录](../phase8d/SDK_PROVENANCE.md)

| 原生镜像 | 四象限产物 | ELF 角色 | SHA256 |
| --- | --- | --- | --- |
| VD | GCC C | ET_EXEC | `8b9a99ab11fff447022618f796ee397cccd21fbaf4d30a29d9561647c3f687fc` |
| VD | GCC C++ | ET_EXEC | `e667142e73f25ed285f81f0b6c4f8e681fb375cc3e6c054e5d20950b50c07d73` |
| LLVM | Clang C | ET_DYN + DF_1_PIE | `e4987d1628770f2dfa5f6b13d95fc1ed3cdd235651d3ca26e3812aea41f01606` |
| LLVM | Clang C++ | ET_DYN + DF_1_PIE | `5c1cc3d271e9062291e02c39704f932ed8fe4ad41174816bb929cea27446517c` |

四个主程序均为 ELF32 ARM、EABI5、softfp/Base PCS，解释器为 /lib/ld-linux.so.3。两侧 C++ 均直接依赖 libstdc++.so.6 与 libgcc_s.so.1，带 CXXABI 和 GLIBCXX 版本引用。GCC C++ 还保留三个 R_ARM_COPY 对象的静态记录。ET_EXEC 与 PIE 身份分别来自 ELF Header 与动态 PIE 标志。 [C++ 版本与重定位](../phase8d/CPP_COMPILE_LINK_RESULTS.md)

### 后续可授权的测试行为

- C 固定值 64 位除法并打印一行。根据源码，预期退出 0，stdout 为 `536768647\n`，stderr 为空。
- C++ 测试 RTTI、vector、string 和异常在同一进程内的捕获。根据 RTTI 字节和锁定的 libstdc++ 的 type_info::name 规则，预期退出 0，stdout 为 `N12_GLOBAL__N_16WidgetE\n`，stderr 为空。
- 两种预期都是离线推导。原生参考要以实际观测为准，出现偏差时先阻断跨镜像评价。
- 其他六个对象仅记录辅助身份。版本化 DSO 是依赖或静态夹具，缺少进程入口，八项初始计划不包含这些对象。

`run_authorized` 全部为 false，两个目标环境的实际 ID 都未填写。后续只能提交清单指明的同一 SHA256，新增授权、构建或任何字节变化都要另写记录并重新取得原生参考。 [八项计划](FOUR_QUADRANT_EXECUTION_PLAN.md)
