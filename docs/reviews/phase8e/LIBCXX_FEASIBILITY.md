# libc++ 独立迁移轨道

**离线编译与链接 PASS。目标执行 NOT_EXECUTED。** 使用 Phase 8D 已固定的 LLVM Base Toolchain Sysroot 和受控 C++ 源码，在新输出目录中进行一次真实 Clang++ 22.1.8 / LLD 22.1.8 构建。SDK 只读，工具在独立无网络隔离内执行，运行原始 ARM 产物的步骤仍未发生。原有 Clang + libstdc++ 产物通过全量 SHA256 冻结核对。 [产物身份](FROZEN_ARTIFACT_MANIFEST.md)

| 项目 | 观察 |
| --- | --- |
| SDK 内包 | libc++ 和 libc++abi 22.1.8-1.1、libunwind 1.6.2-1.1、compiler-rt 22.1.8-1.6，来自固定 LLVM Base |
| 真实退出码 | 编译 0，链接 0 |
| 产物 | ARM ELF32 EABI5、softfp/Base PCS、PIE，PT_INTERP 为 /lib/ld-linux.so.3 |
| 产物 SHA256 | `35db28f26938b0ad397882404ee396d9420cbf3b2e904ec009e699c73cb829ae` |
| 同源码 SHA256 | `359d05f2acd21d2a8d225ce49d96fc88d8796b6e420db2f6de403e77a26f506e` |
| 直接 DT_NEEDED | libc++.so.1、libc++abi.so.1、libm.so.6、libc.so.6 |
| 动态契约 | __cxa_throw@LLVM_22 及 C++ 库 LLVM_22 版本需求。未出现直接 libstdc++.so.6 需求。 |

编译固定 ARMv7-A、Thumb、NEON、softfp，并明确使用 `-std=c++17 -stdlib=libc++ -nostdinc++ -isystem /sysroot/usr/include/c++/v1`。链接使用 `-fuse-ld=lld --rtlib=compiler-rt --unwindlib=libunwind`，ARM compiler-rt 提供启动对象，LLD 跟踪记录了目标 libunwind.so 的解析。最终 ELF 的直接 DT_NEEDED 没有 libunwind.so.8。本次探针只证明该选项和链接输入可用，实际 Unwind 实现及行为仍待目标确认。两个 libc++ 系列 DSO 都直接依赖 libgcc_s.so.1，因此其运行依赖仍包含 GNU libgcc_s。 [包锁定](../phase8d/SDK_PROVENANCE.md)

两套原始 SR RPM 清单均未列出 libc++ 或 libc++abi。该新产物需要专门的目标依赖、装载路径及原生参照；本轮冻结的 Clang 基线仍为 libstdc++。标准库迁移带来的 ABI、异常和 C++ 对象跨 DSO 风险应作为独立轨道验收。 [四象限计划](FOUR_QUADRANT_EXECUTION_PLAN.md)
