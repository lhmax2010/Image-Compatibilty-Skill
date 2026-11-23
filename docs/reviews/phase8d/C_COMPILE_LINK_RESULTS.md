# 真实 C 编译与链接

## 正式验收

两侧分别使用各自最小 Sysroot。GCC 运行 Tizen GNU ld，LLVM 运行 LLD，分别保留编译 .o 和链接 .elf/.so、argv、退出码、链接跟踪、map、readelf 和 SHA256。两次链接失败均为有意构造的符号版本负对照。

| Probe | VD GCC 编译 / 链接 | LLVM Clang 编译 / 链接 | 核验事实 |
| --- | --- | --- | --- |
| A 基础 C | 0 / 0 | 0 / 0 | stdint.h、stdio.h、features.h。64 位除法实际触发目标编译器运行库，都会从 libc 需求 printf@GLIBC_2.4。 |
| C 真实版本 | 0 / 0 | 0 / 0 | 显式引用 confstr@GLIBC_2.4，.gnu.version_r 将要求关联到 libc.so.6，两侧发布镜像中的 libc 均提供该符号。 |
| C 不存在的版本 | 0 / 1 | 0 / 1 | 只把符号版本改成 PHASE8D_ABSENT_1.0，两侧链接器都诊断该未定义符号，未生成输出 ELF。 |
| C 版本化导出 | 0 / 0 | 0 / 0 | 共享库的 SONAME 为 libphase8d_contract.so.1。version script 生成 PHASE8D_1.0 定义及 phase8d_public_contract@@PHASE8D_1.0。 |
| D headless 接口 | 0 / 0 | 0 / 0 | 使用 Tizen pkg-config 提供的目标 flags，编译 tzplatform_config.h 并链接 tzplatform_getenv，DT_NEEDED 包含 libtzplatform-config-2.0.so.2。 |

基础 C 的 VD DT_NEEDED 为 libc.so.6，LLVM 为 libc.so.6 和 libgcc_s.so.1。GCC 链接跟踪实际读取 ARM libgcc.a。LLVM 链接跟踪记录 ARM compiler-rt 的 aeabi_uldivmod.S.o 等，从而证明使用了指定目标资源。两个基础 C 程序均为 ARM ELF32/EABI5、Base PCS，PT_INTERP 为 /lib/ld-linux.so.3。

## 复核方法

从匹配的 SDK 调用 C 驱动，使用 -march=armv7-a -mfloat-abi=softfp -mfpu=neon -mthumb，以及 [Sysroot 和链接项配置](SYSROOT_VALIDATION.md)。真实版本样例声明 `extern size_t demanded_confstr(int, char *, size_t);`，用 `__asm__(".symver demanded_confstr,confstr@GLIBC_2.4");` 绑定入口并调用 demanded_confstr(_CS_PATH, 0, 0)。负例只换成 `confstr@PHASE8D_ABSENT_1.0`。导出样例将单个 C 函数 phase8d_public_contract 编入共享库，version script 中的全局节点为 PHASE8D_1.0。Profile 样例包含 tzplatform_config.h 并调用 tzplatform_getenv(TZ_SYS_RO_SHARE)。

```bash
readelf -W -h -l -d --dyn-syms -V -A "$ARTIFACT"
readelf -W --dyn-syms -V "$PINNED_TARGET_LIBC"
```

另用已有 Skill 的 run_matrix 和显式 probes 重做基础 C，两侧各取得一个 COMPLETE 构建记录。未发送或执行目标 ELF。 [矩阵结果](PHASE8D_ACCEPTANCE.md)
