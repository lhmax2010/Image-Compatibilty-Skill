# 取得匹配的 SR ARMv7 SDK 或 Rootstrap

Profile 为 tizen-headless-armv7l。本机 GCC/G++ 为 13.3.0，目标为 x86_64-linux-gnu。PATH 可见 GBS、SDB、GNU readelf、rpm 和 debugfs。本轮未找到 Clang、ARMv7 交叉编译器、MIC、QEMU、Docker/Podman 和 libabigail。现有 Studio/SDB 线索尚无法建立与任一 SR 快照匹配的 SDK 身份。

## 官方索引验证

根据 Unified 快照的 build.xml 定位各自 Base 快照。通过 HTTPS 获取目录索引和 repomd.xml，逐个核对仓库记录的长度与 SHA256，验证 primary.xml.gz、Base filelists.xml.gz 和 build.conf.gz。同时查看 Unified 标准源码 manifest、headless 镜像目录和 .ks。 [VD Unified](https://download.tizen.org/RBS/TIZEN/Tizen/Tizen-Unified-Dev/tizen-unified-dev_20261119.012448/) · [LLVM Unified](https://download.tizen.org/RBS/TIZEN/Tizen/Tizen-Unified-Toolchain/tizen-unified-toolchain_20261120.082536/) · [VD Base repomd](https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Base-Dev/tizen-base-dev_20261117.165532/repos/standard/packages/repodata/repomd.xml) · [LLVM Base repomd](https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Base-Toolchain/tizen-base-toolchain_20261119.042539/repos/standard/packages/repodata/repomd.xml)

| 已核实的发布组件 | VD | LLVM |
| --- | --- | --- |
| Base 快照 | tizen-base-dev_20261117.165532 | tizen-base-toolchain_20261119.042539 |
| x86_64 端工具 | gcc-armv7l 14.2.0-1.1、binutils-armv7l 2.43-1.1 | 同版本，分别固定各自仓库摘要 |
| x86_64 Clang 和 LLVM | 22.1.8-1.5，名录包含 clang++、ld.lld | 22.1.8-1.6，同类工具 |
| ARMv7l GCC、GCC C++、libstdc++-devel | 14.2.0-1.8 | 14.2.0-1.7 |
| ARMv7l libc 开发包 | glibc-devel 2.40-1.8、linux-glibc-devel 6.6-1.8 | 同版本 |
| ARMv7l LLVM 运行库和 C++ 开发包 | compiler-rt 22.1.8-1.6、libc++-devel 和 libc++abi-devel 22.1.8-1.1 | 同版本 |
| Unified ARMv7l Rootstrap RPM | native-dev-rootstrap 10.0-1、app-rootstrap 和 app-rootstrap-devel 11.0.1-1、app-rootstrap-product 和 hal-rootstrap 10.0.0-1 | 同版本 |

Base filelists 把 stdio.h、crt1.o/crti.o/crtn.o、libc.so 映射到 glibc-devel，把 linux/version.h 映射到 linux-glibc-devel，把 crtbegin*.o/crtend*.o 映射到 ARM GCC。两种 iostream 和对应的链接时库分别属于 libstdc++-devel、libc++-devel。ARM compiler-rt 包含 libclang_rt.builtins-arm.a。两套 Unified 源码 manifest 将 sdk/tools/native-dev-rootstrap 固定为 `80698ca9a00ce487c957be940c2735494d5293c3`，platform/core/system/app-rootstrap 固定为 `a033f2a81d193c98ce1f7ae7fd4a418960951bb8`。这些元数据给出可追踪的构建来源。完整 SDK 发布物及 Rootstrap 对 headless 系统接口的覆盖仍待验证。 [VD 源码 manifest](https://download.tizen.org/RBS/TIZEN/Tizen/Tizen-Unified-Dev/tizen-unified-dev_20261119.012448/builddata/manifest/tizen-unified-dev_20261119.012448_standard.xml) · [LLVM 源码 manifest](https://download.tizen.org/RBS/TIZEN/Tizen/Tizen-Unified-Toolchain/tizen-unified-toolchain_20261120.082536/builddata/manifest/tizen-unified-toolchain_20261120.082536_standard.xml)

## 获取路线

| 路线 | 可获得性 | 所需依赖 | 风险 | 推荐程度 |
| --- | --- | --- | --- | --- |
| 已有匹配 SDK | 本机未确认 | 两侧 SDK 和构建身份 | 通用 Studio SDK 可能出现架构、发行版或运行库错配 | 有构建方同快照 SDK 时优先 |
| 官方工具链与 Rootstrap | 已核实固定快照的包及源码 | 对应的 Base/Unified、构建配置、Rootstrap RPM、经授权工作区 | Rootstrap 可能侧重应用，需要验收 headless 专有接口 | 首选下一步核验 |
| 使用发布 RPM 建立 Sysroot | 核实了基本开发包和文件名录 | 固定各侧 glibc、linux-glibc-devel、crt、C++ 开发包和编译器运行库，加 profile 专有开发包、pkg-config、对应宿主编译器和链接器 | 依赖闭包、绝对软链接、链接器脚本、浮点 ABI 和 C++ runtime 需要单独验收 | Rootstrap 覆盖不足时采用 |
| 继续静态分析 | 输入可复用 | 文件证据和现有报告 | 结论限于文件契约和静态模型 | 当前可用 |

后续获准时为两侧分别固定原镜像、快照、仓库和 RPM 摘要、源修订、build.conf、目标 triple、宿主工具版本及 Sysroot 包清单。ARMv7l GNU 工具名含 armv7l-tizen-linux-gnueabi。VD 的 build.conf 明确使用 softfp，实镜像 ABI 另见静态证据。不能混用仓库中的 armv7hl、宿主库或任意 C++ ABI。先用仅编译和链接的 C/C++ 探针验证头文件、crt、ELF 浮点 PCS、解释器、符号版本和 DT_NEEDED，再在获准环境检验四象限。官方 GBS 文档描述了固定 RPM 仓库和 build.conf 的构建路径。 [GBS build](https://github.com/Samsung/tizen-docs/blob/master/docs/platform/reference/gbs/gbs-build.md)

复核时解析上述 repomd.xml 的 data 条目，按 location 取得元数据并核对 size 和 checksum，再用 primary 的包身份与 filelists 的 pkgid 关联文件清单。每侧 Base 的 primary、filelists 和 build 文件合计低于 2 MiB，每侧 Unified 的 primary 约 1.5 MiB。本轮范围仅到发布元数据，RPM 签名、依赖闭包、编译器执行和实际链接待下一阶段授权验证。

元数据所列 native-dev-rootstrap、app-rootstrap、app-rootstrap-devel 三包的下载体积为 VD 581,510,884 B、LLVM 549,749,372 B。代表性 Base 核心包的下载体积为 VD 70,861,284 B（交叉 GCC、交叉 Binutils、glibc-devel、libstdc++-devel），LLVM 116,813,923 B（Clang、LLVM、glibc-devel、compiler-rt、libc++-devel）。这些是所列包的下限。审批时需先确定要提取的包、完整依赖闭包、下载和解压空间以及隔离构建位置。

Tizen Git 服务请求这两个固定修订的原始 spec 时返回 HTTP 502。本轮确认了发布的 build.conf、镜像配方、Rootstrap 包和源码修订。Rootstrap spec 的具体构建步骤仍需从可访问的可信源码核对。
