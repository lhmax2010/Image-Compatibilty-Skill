# 真实 C++ 编译与链接

VD 使用 Tizen G++ 14.2.0 / GNU ld 2.43，LLVM 使用 Clang++ 22.1.8 / LLD 22.1.8。两侧的 GCC 系列目标开发头来自相应 Base RPM。产品 RPM DB 和运行时库的 SHA256 表明这两个镜像均采用各自的 libstdc++.so.6 与 libgcc_s.so.1。LLVM 侧 C++ 显式使用 -stdlib=libstdc++。已下载的 libc++/libc++abi 保留文件证据，本轮原生探针没有链接它们。 [Sysroot 证据](SYSROOT_VALIDATION.md)

| Probe B | VD | LLVM |
| --- | --- | --- |
| 编译 / 链接退出码 | 0 / 0 | 0 / 0 |
| 目标 | ELF32 ARM EABI5，Base PCS | ELF32 ARM EABI5，Base PCS |
| 解释器 | /lib/ld-linux.so.3 | /lib/ld-linux.so.3 |
| DT_NEEDED | libstdc++.so.6、libm.so.6、libgcc_s.so.1、libc.so.6 | 同 |
| 可核对的 C++ 证据 | CXXABI_1.3 的 __cxa_throw、__dynamic_cast，GLIBCXX 版本符号及 GNU libgcc 运行库 | 同，另从链接跟踪核对 ARM compiler-rt |
| Skill 正常矩阵的 C++ 构建 | COMPLETE | COMPLETE |

样例包含 cstdio、stdexcept、string、typeinfo、vector，用有虚析构函数的基类和派生类访问 dynamic_cast、typeid、std::vector<std::string>，抛出并捕获 std::runtime_error。检查对象和链接结果的 readelf，确认 RTTI、异常符号及符号版本保持在声明的目标提供者上。程序未执行。

VD/LLVM 两侧的编译产物在两套原始镜像上另做了限定为指定文件的离线核对。GCC 和 Clang 的 C++ 样例分别有 33、38 个版本化导入，在每个镜像的指定库均能找到匹配符号。VD GCC 输出的三个 R_ARM_COPY 对象另按版本、OBJECT 类型和大小逐个核对。Skill 的现有采集完整性门槛对包含外部版本 Copy Relocation 的 ELF 保持保守，该观察不改变生产判定。运行时符号选择、RTTI 跨 DSO、异常传递和实际执行仍待目标验证。

```bash
readelf -W -h -l -d --dyn-syms -V -A -r "$CXX_ARTIFACT"
readelf -W --dyn-syms -V "$PINNED_LIBSTDCXX"
```
