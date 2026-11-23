# SR ARMv7 SDK 获取与组装

## 输入与准入

工作区在 x86_64 Linux 上，宿主 GCC 为 13.3.0，glibc 为 2.39，有 GBS、RPM 4.18.2、rpmkeys、rpm2cpio、readelf 和 bwrap。开始时项目 main 指向 `fb36ff683c058b140a9c4b9fd84c8f41b7d941a5`，工作树干净。工作区所在 ext4 卷初始可用 8,407,785,472 B，空闲 inode 93,187,265，可用内存 22,155,792,384 B，Swap 空闲 125,562,880 B。任务文件保存在该工作区的独立 Phase 8D 目录中。归档、分区、历史报告及旧 SQLite 输出保留。

| 用途 | 计算口径 |
| --- | --- |
| SDK 下载 | 两套 Rootstrap 375,339,288 B，宿主工具和依赖 212,668,613 B，目标开发及运行库 74,709,925 B，共 662,717,826 B |
| SDK 解压 | 用全部包宣告的 archive 大小作上限预估，2,524,554,260 B（约 2.35 GiB）。Rootstrap 实际只取 app-rootstrap 目录。工作卷留出 1 GiB 空闲余量，逐包检查。 |
| SQLite | 直接使用已解压原始报告时约需 12.28 GiB 独立可用空间。最终 gzip 版还需要物化其输入文件。 [计算与状态](SQLITE_FULL_ACCEPTANCE.md) |

## 官方 Rootstrap 路线

两边都下载并离线抽取 armv7l app-rootstrap-devel 11.0.1-1。只提取 /opt/data/app-rootstrap 数据，未安装 RPM 或运行脚本。libc.so.6 与 ld-linux.so.3 和相应 SR 镜像逐字节一致，包含 C 库头和部分启动对象。未发现完整 GCC C++ 头、GCC crtbegin/crtend 或 headless 的 libtzplatform-config.pc。Rootstrap 自带的 libstdc++.so.6 和 libgcc_s.so.1 与产品文件的 SHA256 存在差异。两个原始 Rootstrap 的 C 启动试跑分别在 GCC stddef.h 和 Clang 所需 GCC 安装数据处停止，记录了具体诊断。

Unified 的 native-dev-rootstrap 文件名录包含四个 device/emulator、public/private ZIP。由于本轮的 headless 探针可由已匹配的 Base 和 Unified 开发包覆盖，未下载这组额外归档。

## 构建 headless 最小 Sysroot

逐侧从固定 Base 取得目标 glibc-devel、linux-glibc-devel、GCC 的公共/内部头及 crt、libgcc、libstdc++-devel，从对应 Unified 取得 libtzplatform-config-devel 及依赖。LLVM 侧另取 compiler-rt 和可供核查的 libc++、libc++abi、libunwind。宿主只运行各自 Base 的 x86_64 工具及所需宿主库。目标头与库限 armv7l 和相关 noarch 数据。每侧的 RPM 提取和文件哈希独立。

解析器按 RPM capability、版本、架构和文件提供关系锁定探针载荷，计划内无未解析的载荷依赖。LLVM 选择同仓库 lldb 和 terminfo-base-mini 以解决重复 capability，其用途是闭合工具包依赖，实际行为探针未运行 LLDB。安装脚本依赖和 Linux 头包的安装用 coreutils 另列在本地计划，离线提取从不执行相关脚本。闭包的范围是本次构建所需的离线载荷。 [逐 RPM 锁定结果](SDK_PROVENANCE.md)

解包验证名称、路径、数据边界和链接目标。合并 usrmerge 时只允许解析到当前提取根内。保留可用权限和包内链接，禁止执行 RPM scriptlet。编译使用 bwrap 只读绑定快照工具链和 Sysroot，隔离网络，仅将本次探针输出目录设为可写。 [验证细节](SYSROOT_VALIDATION.md)
