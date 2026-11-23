# libc++ 独立轨道的 Runtime 依赖

Phase 8E 的 `libcxx-probe.elf` SHA256 仍为 `35db28f26938b0ad397882404ee396d9420cbf3b2e904ec009e699c73cb829ae`。本轮用 `readelf -W -h -l -d --dyn-syms -V -A -n` 逐项检查该探针及闭包。探针是 ARM ELF32、EABI5、Base PCS/softfp 的 PIE，解释器为 `/lib/ld-linux.so.3`。已有 Clang 加 libstdc++ 基础探针继续依其冻结字节进入正式矩阵。 [构建来源与原始链接](../phase8e/LIBCXX_FEASIBILITY.md)

| 对象 | 直接 `DT_NEEDED` |
| --- | --- |
| libcxx-probe.elf | libc++.so.1、libc++abi.so.1、libm.so.6、libc.so.6 |
| libc++.so.1 | libc++abi.so.1、libgcc_s.so.1、libm.so.6、libc.so.6、ld-linux.so.3 |
| libc++abi.so.1 | libgcc_s.so.1、libm.so.6、libc.so.6、ld-linux.so.3 |
| libgcc_s.so.1 | libc.so.6 |
| libm.so.6 | libc.so.6、ld-linux.so.3 |
| libc.so.6 | ld-linux.so.3 |
| ld-linux.so.3 | 无 |

两侧原始 RPM 清单都缺 libc++ 和 libc++abi。留存 Rootfs 的 `/usr`、`/lib`、`/opt` 也未找到对应 SONAME 路径。当前独立探针必须在获批测试环境额外提供 LLVM Base 同快照的两个 ARM 文件及原 SONAME 链接。

| 目标 SONAME | 同快照文件 | SHA256 |
| --- | --- | --- |
| libc++.so.1 | libc++.so.1.0 | `d6bbcbd7ad1bf4790ef73202109cd28237d528d668b5a09caae7594ff163651e` |
| libc++abi.so.1 | libc++abi.so.1.0 | `d86ed91d465a5064e28195da653988e7917f24cfb34dbdc98f07aff08c8fa8cf` |

用现有 `Image.resolve` 解析各侧的映像内文件。检查指定的 Provider 的 `.gnu.version_d` 和 `.dynsym`，以请求方 `.gnu.version_r` 和版本索引关联 SONAME，再逐一核对版本化导入。原始两侧仅有 8 个命中的版本需求和 43 个版本化导入，两个缺库对应缺少两个 `LLVM_22` 节点和 30 个版本化导入。对每侧只进行离线指定库模拟，加入上表的两个识别文件后，32 个版本需求、361 个版本化导入均在指定的文件中命中。这些包括两个 libc++ DSO 对原 SR `libgcc_s.so.1` 的 18 个版本化导入。两项无显式版本的强引用 `__aeabi_unwind_cpp_pr0/1` 也在两侧 `libgcc_s.so.1` 找到 `@@GCC_3.5` 默认导出。其余 21 个闭包中无显式版本的弱引用单列为静态观察。 [原始 Loader 和 GNU 运行库身份](TARGET_ENVIRONMENT_READINESS.md)

Phase 8E LLD 跟踪出现 `/sysroot/usr/lib/libunwind.so`，两侧镜像也有 `libunwind.so.8`。本探针的 `DT_NEEDED` 递归闭包未请求 `libunwind.so.8`。现有离线结果只支持部署上表新增 DSO 并使用已有 GNU 依赖的设计，实际绑定、Unwind、异常和跨 DSO 行为仍需执行证据。从模型出发的部署方案应使用单独的受审库目录并记录实际加载路径，保持产品目录不变。

未运行冻结 ELF，无运行结果。离线检查日志 SHA256 为 `f264d96af8bddf92bbe91856a15471b5f565ca54d6b3e32072e8d4ce68655d05`。 [LLVM Base 包身份](../phase8d/SDK_PROVENANCE.md)
