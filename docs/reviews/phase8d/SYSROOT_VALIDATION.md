# 两侧最小 Sysroot 验证

VD GCC 和 LLVM Clang 各自绑定独立的 Base/Unified RPM 提取目录。编译时分别映射到虚拟 /sysroot，作为只读输入。环境使用对应 Tizen x86_64 RPM 中的工具和宿主侧依赖。真实目标产物生成在可写 /work，工作模式只涵盖编译和链接。

| 合同 | VD | LLVM |
| --- | --- | --- |
| 目标 | armv7l-tizen-linux-gnueabi，ELF32 little-endian ARM，EABI5 | 同 |
| PCS | -mfloat-abi=softfp，C/C++ 都记录 __ARM_PCS=1、__ARM_FP，均无 __ARM_PCS_VFP | 同 |
| ISA 编译标志 | -march=armv7-a -mfpu=neon -mthumb | 同 |
| 解释器 | /lib/ld-linux.so.3 | 同 |
| C 头文件 | 同快照 glibc-devel、linux-glibc-devel、GCC 目标内部头 | 同快照 glibc-devel、linux-glibc-devel、Clang 目标资源头 |
| C++ 头与链接时库 | Base Dev 的 libstdc++-devel 14.2.0-1.8 | Base Toolchain 的 libstdc++-devel 14.2.0-1.7 |
| glibc 启动与链接脚本 | crt1.o、crti.o、crtn.o、libc.so 的 GROUP 解析 | Scrt1.o、crti.o、crtn.o、libc.so 的 GROUP 解析 |
| 编译器启动对象和运行库 | ARM crtbegin/crtend、libgcc.a、libgcc_s.so.1 | ARM clang_rt.crtbegin/crtend、libclang_rt.builtins-arm.a、libgcc_s.so.1 |
| 代表性 Profile 开发文件 | tzplatform_config.h、libtzplatform-config.pc、对应链接时库 | 同 |
| 辅助 C++ 库 | 原生探针使用 libstdc++ | 已核对快照 ARM libc++.so.1 和 libc++abi.so.1 的文件身份。原生探针使用产品镜像实际安装的 libstdc++。 |

C++ include 搜索明确使用目标 GCC 的通用与 armv7l-tizen-linux-gnueabi 专用目录，VD 的 stddef.h 等来自同快照的目标 GCC RPM。LLVM 用原装 Clang 资源头与同快照 ARM compiler-rt 资源目录。pkg-config 只读 /sysroot/usr/lib/pkgconfig 和 /sysroot/usr/share/pkgconfig。GCC 的启动对象和 libgcc.a 从相应目标 RPM 复制到 /work/startfiles，libgcc_s.so 链接到 /sysroot/usr/lib/libgcc_s.so.1。真实链接跟踪逐条校验到 /sysroot、/sdk-resource、本次生成的目标对象或这些已比对的 startfiles。产物均无 RPATH/RUNPATH，也没有借用 Ubuntu 宿主头或目标库。

使用已验证的实际 SR 根目录，独立解析镜像内链接并逐字节比较下列运行文件。每一侧的六个组成文件均与其自己的 Sysroot 匹配。 [镜像历史哈希和报告](../phase8c/COVERAGE_BEFORE_AFTER.md)

| 对象 | VD SHA256 | LLVM SHA256 |
| --- | --- | --- |
| libc.so.6 | `f5a377a3121928d31111fa3a556a5ffe16014dc75254620bf2257d5ab7c1e4d4` | `9f2ae4ee0d10374c7681a33b09b5a84dbfca82c3d1bc012edf81483f11202b96` |
| ld-linux.so.3 | `0b1fe895ab844a3dfb04a2ab034a6fca9aeadb570abd49b36bf4be16a676f4df` | `b011ebe723dc6e8115f4eb44c964817f7d61878e44d6de3a9367e7359b5bf7da` |
| libstdc++.so.6 | `52926e5bed922340320697b451689e51ed7ff45f0099d606c7f7c449a5e58520` | `871c24ae874b77d767cffff6933886566985326e20fd787bdd9892816284ae53` |
| libgcc_s.so.1 | `d05fc30b89f48f4154bb125978a9e55f68c0eed8aa4faf2084839d2c735eb9e0` | `904b67964d3e751b9d9213fdb0b7643bf18d5e15294a0fb50782c580610cdb25` |

libm.so.6 和 libtzplatform-config-2.0.so.2 也逐侧匹配。运行文件 SHA256、开发文件 SHA256、真实 argv 和 linker map 保存在工作区的 OFFLINE_VALIDATION.json 和探针记录中。复核可用 `readelf -W -h -l -d --dyn-syms -V -A`，再将证据与驱动的 `-v -H`、宏输出及 `-Wl,-t,-Map=...` 对账。 [包和工具身份](SDK_PROVENANCE.md)

这些最小 SDK 覆盖本次探针。任意 headless 包的完整 API、构建分支全部选项、开发框架覆盖和目标硬件特性仍有各自的验收范围。
