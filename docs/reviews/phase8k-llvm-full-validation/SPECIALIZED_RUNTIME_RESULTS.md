# LLVM headed 专项探针

主 Bundle 20 项 GCC/Clang 编译链接全部退出 0。单独的常驻 Provider 探针补充 1 项成功编译链接。SDK 为 Phase 8D 已审核的 GCC/G++ 14.2.0 与 Clang/Clang++ 22.1.8，在 ARMv7 EABI5 Base PCS 下生成，私有 DSO 单独冻结。C++ 运行时路线为 libstdc++ 与 libgcc_s。

| 组别 | 实机用例 | 结果 |
| --- | ---: | --- |
| C ABI | 2 | GCC 与 Clang 均校验整型、浮点与结构体参数/返回值、内存分配释放 |
| TLS 与线程 | 2 | 两套编译器的 `behavior.c` 校验 `__thread`、隔离、pthread、互斥及条件变量 |
| Deferred cancellation / forced unwind | 2 | 两套编译器的 `cancel.cpp` 观察取消、RAII 析构及 `pthread_join` |
| C++ 跨 DSO | 4 | 交叉组合全通过 RTTI、dynamic_cast、异常、析构、创建释放、`thread_local` 生命周期和线程隔离 |
| C++ 契约负例 | 1 | 私有 DSO 行为变体按预期退出 14；装载与清理均有证据 |
| 版本化符号 | 3 | 匹配绑定退出 0；缺具体符号退出 127；缺版本节点退出 1 |
| 缺 DSO | 1 | 启动期未找到私有测试库，按预期退出 127 |
| 私有 DSO 动态加载 | 1 | 设备拒绝 `dlopen("./libsr_probe.so")`，退出 12，专项契约未达到 |
| 常驻 libc 动态句柄 | 1 | RTLD_NOLOAD、两种 flag 组合、dlsym、dlvsym、缺符号和 dlclose 通过 |
| 执行控制 | 2 | 预期非零退出 17，scope 超时退出 143，均经独立 SDB 观察清理 |
| Clang + libc++ | 1 | SKIP，标准库 Provider 缺失，0 次执行 |

最终矩阵 19 项实机专项，12 项正例观察成功，6 项预期失败，1 项设备策略拒绝导致契约未满足，另有 1 项 SKIP。四个跨 DSO 组合为 GCC–GCC、GCC–Clang、Clang–GCC、Clang–Clang，均在同一 LLVM headed 设备观察。输出包含 `cross-dso: rtti lifetime string exception unwind tls ok`。

留存的初轮记录包括未授权 Provider 进入实际装载集后被报告门禁拦截，以及两次 grant 前观察失效。修正可信 pin 后复验；相关提前停止与重复执行仍在原始 Evidence 中。本地按 `integrated-reviewed/`、`integrated-remainder/` 和 `integrated-supplement/` 保存对应回执。见 [动态链接证据](DYNAMIC_BINDING_EVIDENCE.md)。
