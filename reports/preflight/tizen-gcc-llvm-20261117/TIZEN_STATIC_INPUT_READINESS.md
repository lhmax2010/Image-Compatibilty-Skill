# Tizen GCC/LLVM 输入预检 — Phase 0

决策：**INSUFFICIENT_EVIDENCE**。检查时间 2026-11-17T09:22:43.850452+00:00。

两侧均有实际发布的 armv7l rootfs 分区归档元数据，归档 HEAD 200；不是只有 RPM 仓库。可以形成 headed/headless 两个独立候选对，但尚不能作为来源已验证的 GCC-versus-LLVM 受控验收输入。未选 profile，未下载镜像、RPM，未解包、执行测试或 checker。此判断不否定框架 RC 的本地准备状态，也不是镜像兼容性结论。

## 1. 精确 URL 状态

- GCC 声明候选：[tizen-unified_20261115.233954](https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Unified/tizen-unified_20261115.233954/)，HEAD/GET **200/200**，无重定向；存在 images/standard、images/emulator、repos、builddata、build.xml。emulator 索引只列 emulator64-wayland，没有 armv7l profile。
- LLVM 声明候选：[tizen-unified-toolchain_20261113.065522](https://download.tizen.org/RBS/TIZEN/Tizen/Tizen-Unified-Toolchain/tizen-unified-toolchain_20261113.065522/)，HEAD/GET **200/200**，无重定向；存在 images/standard、repos、builddata、build.xml；images 索引没有 emulator，未据此断言直接 URL 必定 404。
- 请求及最终 URL、HTTP Content-Type/Length/Last-Modified、错误、元数据正文均保存在证据日志和 JSON。全部仅访问 download.tizen.org；未访问 latest、reference 或替代构建。

## 2. armv7l 镜像候选

| 侧 | 精确 profile | 压缩归档大小（HEAD） | 内容范围（发布元数据） | 证据 |
|---|---|---:|---|---|
| gcc | tizen-armv7l-generic-hal | 6,472,130 (6.2 MiB) | 无 / rootfs | [HEAD 200](https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Unified/tizen-unified_20261115.233954/images/standard/tizen-armv7l-generic-hal/tizen-unified_20261115.233954_tizen-armv7l-generic-hal.tar.gz) · [SHA256](https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Unified/tizen-unified_20261115.233954/images/standard/tizen-armv7l-generic-hal/SHA256SUMS) |
| gcc | tizen-boot-armv7l-rpi | 28,693,787 (27.4 MiB) | 无 / rootfs | [HEAD 200](https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Unified/tizen-unified_20261115.233954/images/standard/tizen-boot-armv7l-rpi/tizen-unified_20261115.233954_tizen-boot-armv7l-rpi.tar.gz) · [SHA256](https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Unified/tizen-unified_20261115.233954/images/standard/tizen-boot-armv7l-rpi/SHA256SUMS) |
| gcc | tizen-boot-armv7l-rpi-rt | 28,854,412 (27.5 MiB) | 无 / rootfs | [HEAD 200](https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Unified/tizen-unified_20261115.233954/images/standard/tizen-boot-armv7l-rpi-rt/tizen-unified_20261115.233954_tizen-boot-armv7l-rpi-rt.tar.gz) · [SHA256](https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Unified/tizen-unified_20261115.233954/images/standard/tizen-boot-armv7l-rpi-rt/SHA256SUMS) |
| gcc | tizen-headed-armv7l | 612,275,524 (583.9 MiB) | 含 / rootfs | [HEAD 200](https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Unified/tizen-unified_20261115.233954/images/standard/tizen-headed-armv7l/tizen-unified_20261115.233954_tizen-headed-armv7l.tar.gz) · [SHA256](https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Unified/tizen-unified_20261115.233954/images/standard/tizen-headed-armv7l/SHA256SUMS) |
| gcc | tizen-headless-armv7l | 300,322,412 (286.4 MiB) | 含 / rootfs | [HEAD 200](https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Unified/tizen-unified_20261115.233954/images/standard/tizen-headless-armv7l/tizen-unified_20261115.233954_tizen-headless-armv7l.tar.gz) · [SHA256](https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Unified/tizen-unified_20261115.233954/images/standard/tizen-headless-armv7l/SHA256SUMS) |
| llvm | tizen-boot-armv7l-rpi | 28,676,367 (27.3 MiB) | 无 / rootfs | [HEAD 200](https://download.tizen.org/RBS/TIZEN/Tizen/Tizen-Unified-Toolchain/tizen-unified-toolchain_20261113.065522/images/standard/tizen-boot-armv7l-rpi/tizen-unified-toolchain_20261113.065522_tizen-boot-armv7l-rpi.tar.gz) · [SHA256](https://download.tizen.org/RBS/TIZEN/Tizen/Tizen-Unified-Toolchain/tizen-unified-toolchain_20261113.065522/images/standard/tizen-boot-armv7l-rpi/SHA256SUMS) |
| llvm | tizen-headed-armv7l | 575,392,175 (548.7 MiB) | 含 / rootfs | [HEAD 200](https://download.tizen.org/RBS/TIZEN/Tizen/Tizen-Unified-Toolchain/tizen-unified-toolchain_20261113.065522/images/standard/tizen-headed-armv7l/tizen-unified-toolchain_20261113.065522_tizen-headed-armv7l.tar.gz) · [SHA256](https://download.tizen.org/RBS/TIZEN/Tizen/Tizen-Unified-Toolchain/tizen-unified-toolchain_20261113.065522/images/standard/tizen-headed-armv7l/SHA256SUMS) |
| llvm | tizen-headless-armv7l | 294,165,770 (280.5 MiB) | 含 / rootfs | [HEAD 200](https://download.tizen.org/RBS/TIZEN/Tizen/Tizen-Unified-Toolchain/tizen-unified-toolchain_20261113.065522/images/standard/tizen-headless-armv7l/tizen-unified-toolchain_20261113.065522_tizen-headless-armv7l.tar.gz) · [SHA256](https://download.tizen.org/RBS/TIZEN/Tizen/Tizen-Unified-Toolchain/tizen-unified-toolchain_20261113.065522/images/standard/tizen-headless-armv7l/SHA256SUMS) |

全部 manifest 声明 `format: loop`，归档为 tar.gz，XML 声明 `arch=armv7l`。manifest 的 `version: 2.1.3` **不是 Tizen OS 版本**。所有归档的完整 SHA256 已逐文件记入 JSON；它们是发布值，尚未核对归档字节，也未核验签名。

同名交集是 `tizen-headed-armv7l`、`tizen-headless-armv7l`、`tizen-boot-armv7l-rpi`，不能互换。只有前两项包含 `/` rootfs。boot-rpi 是 boot/HAL/modules 组件，不能单独承担用户态镜像验收；generic-hal 和 rpi-rt 只在 GCC 发布镜像索引中出现。配置模板存在不代表对应镜像已发布。

headed 两侧各有 ext4 rootfs/system-data、F2FS user 分区及 ramdisk 元数据；headless 没有 user 分区。不能把这些 loop tar 直接当成已展开 rootfs 输入。rootfs 内实际 ELF 架构、分区文件魔数和可启动性仍 UNKNOWN；静态分析无需启动。

## 3. 发行版、工具链与来源

两侧 headed/headless `.packages` 都发布 `tizen-release.armv7l 11.0.0-0` 及相同源码 revision。这是 **VERIFIED 的发布元数据事实**，实际 `/etc/os-release`、产品型号和运行配置尚未验证。对应 .packages 链接在 JSON 每个 profile 中。

GCC / LLVM 身份均 **DECLARED_ONLY**（用户声明），实际各包编译器 family/version、flags、ASAN/GCOV/LTO 等 **UNKNOWN**。两侧出现 `libgcc 14.2.0` 只是运行库清单证据；不能证明镜像由 GCC 构建，也不否定 Clang 可使用 libgcc。未找到足以建立包→编译器映射的轻量元数据。

[baseline build.xml](https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Unified/tizen-unified_20261115.233954/build.xml) 当前指向 `tizen-base_20261116.220421`；[candidate build.xml](https://download.tizen.org/RBS/TIZEN/Tizen/Tizen-Unified-Toolchain/tizen-unified-toolchain_20261113.065522/build.xml) 指向 `tizen-base-toolchain_20261111.130848`。GCC KS 使用可变 `Tizen-Base/reference`，candidate KS 使用固定 Base-Toolchain build。GCC 当前 Base ID 的日期晚于镜像 manifest 创建时间（2026-11-16 05:09:05）；这是需解释的时间/来源歧义，不能拿当前 build.xml 证明镜像当时消费了该 Base。

**额外发现：5 个 GCC armv7l profile 的 `.ks` 内容与各自 SHA256SUMS 不符，已用有界原始字节 GET 复核。** 其他已读取且列在 checksum 中的元数据未发现不匹配。未下载归档，因此不能据此断言归档损坏，也不能宣称归档校验已通过。完整 expected/observed SHA256 在 JSON 和日志中；需发布方提供一致的 recipe 与来源说明。

## 4. Profile / 源码配置可比性

headed 和 headless 的同名对分别具有相同分区结构与已读取 `%packages` 选择文本；KS 差异涉及 repo/Base URL、build date 和 build ID。GCC KS 校验问题使这种文本一致性仍不能证明实际构建配置一致。

两份 [baseline standard source manifest](https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Unified/tizen-unified_20261115.233954/builddata/manifest/tizen-unified_20261115.233954_standard.xml) / [candidate standard source manifest](https://download.tizen.org/RBS/TIZEN/Tizen/Tizen-Unified-Toolchain/tizen-unified-toolchain_20261113.065522/builddata/manifest/tizen-unified-toolchain_20261113.065522_standard.xml) 有 **176 个共同项目 revision 不同**，另有 baseline 独有 1 个、candidate 独有 3 个。这是源码项目差异，**不是已安装包计数**。例如发布包清单中 glibc 分别为 `2.40-17.6` / `2.40-1.9`，源码 revision 也不同。后续若接受这对镜像，只能先作为有源码/版本混杂因素的跨快照对比，不能将差异因果归于编译器。

## 5. 本机工具与权限

主机 x86_64，Ubuntu 24.04.5 LTS，Python 3.12.3；项目路径 `/home/linhao/lss/Image-compatibility-skill`，uid/gid 1000，有目录读写/遍历权限。本次没有使用 sudo、安装软件或改动配置。

| 工具 | 版本/状态 | 当前能力中的角色 |
|---|---|---|
| python3 | Python 3.12.3 | core static ELF/package analysis |
| readelf | GNU readelf (GNU Binutils for Ubuntu) 2.42 | core static ELF/package analysis |
| objdump | GNU objdump (GNU Binutils for Ubuntu) 2.42 | optional or format-dependent helper |
| nm | GNU nm (GNU Binutils for Ubuntu) 2.42 | optional or format-dependent helper |
| rpm | RPM version 4.18.2 | core static ELF/package analysis |
| abidiff | PATH 中不可用 | optional or format-dependent helper |
| file | file-5.45 | acquisition/extraction/checksum utility |
| tar | tar (GNU tar) 1.35 | acquisition/extraction/checksum utility |
| gzip | gzip 1.12 | acquisition/extraction/checksum utility |
| xz | xz (XZ Utils) 5.4.5 | optional or format-dependent helper |
| unsquashfs | unsquashfs version 4.6.1 (2023/03/25) | optional or format-dependent helper |
| debugfs | debugfs 1.47.0 (5-Feb-2023) | acquisition/extraction/checksum utility |
| bsdtar | PATH 中不可用 | optional or format-dependent helper |
| cpio | cpio (GNU cpio) 2.15 | optional or format-dependent helper |
| curl | curl 8.5.0 (x86_64-pc-linux-gnu) libcurl/8.5.0 OpenSSL/3.0.13 zlib/1.3 brotli/1.1.1 zstd/1.5.5 libidn2/2.3.7 libpsl/0.21.2 (+libidn2/2.3.7) libssh/0.10.6/openssl/zlib nghttp2/1.59.0 librtmp/2.3 OpenLDAP/2.6.10 | acquisition/extraction/checksum utility |
| sha256sum | sha256sum (GNU coreutils) 9.4 | acquisition/extraction/checksum utility |
| clang | PATH 中不可用 | optional or format-dependent helper |
| gcc | gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0 | optional or format-dependent helper |
| pkg-config | PATH 中不可用 | optional or format-dependent helper |
| pahole | PATH 中不可用 | optional or format-dependent helper |

现有 `/tmp/tizen-correctness-tools/abidiff` 2.4.0、`clang` 14.0.6 已通过 `--version`，不在 PATH，需明确配置；这是既有宿主测试工具，**不是匹配的 Tizen SDK**。PyYAML 6.0.1 可用。bsdtar、pkg-config、pahole 缺失并非基础静态采集阻断。F2FS 用户态工具 dump.f2fs/fsck.f2fs 不可用，若选 headed 且包含 user 分区，需先解决提取方案。debugfs 仅能处理相应 ext 文件系统；不替代 F2FS 工具。boot vfat 的提取方案未在本次验证。

## 6. 磁盘、内存与预算

`/home` 为 ext4，当前空闲 **191.9 GiB**，可用 inode **95,690,223**。内存总计 **30.8 GiB**，当前可用 **8.9 GiB**；swap 总计 4 GiB，仅余 **48 MiB**。

已验证下载体积：headed 对共 **1.11 GiB**（以 JSON 精确字节为准）；headless 对共 **0.55 GiB**。归档解压后占用、文件数、debug 总量均 UNKNOWN，不能由压缩体积推算。

单个已选 profile 对的初步容量预算（估计，不是测量）：rootfs 4–12 GiB，分区/临时空间 6–12 GiB，ELF cache 5–10 GiB，原始证据 5–15 GiB，ABI debug staging 10–30 GiB，JSON/HTML 5–10 GiB，加下载及余量建议预留 **50–100 GiB**。完整 SDK 另计，容量 UNKNOWN。XML 的 rootfs size 字段 headed=3500、headless=2048 是构建配置值，不能代替实际解压体积和文件占用。

当前磁盘满足这一暂定预算，但不构成完整运行的容量保证。实际峰值内存 UNKNOWN；建议重型分析前留出 16–24 GiB 可用余量作为规划目标，目前约 8.9 GiB 且 swap 几乎用尽，需要阶段前复查，不能保证不会 OOM。没有分配大文件测试。

推荐后续使用 `/home/linhao/lss/tizen-static-acceptance/20261117/<profile>/` 下独立的 `downloads/`、`partitions/`、`rootfs/baseline/`、`rootfs/candidate/`、`work/`、`cache/`、`debug/`、`reports/`；**这些目录未创建**，不把 cache/report 写进镜像目录。

## 7. Installed RPM、SDK、debug 和 loader

- `.packages` 已提供并读取，仅作为发布清单，实际 installed count 全部为 **null / UNKNOWN**。不得数远端 RPM 文件来替代 installed inventory；完整 epoch/NEVRA 和 DB 查询结果尚无。
- headed/headless `.files` 列表存在，但均超过 256 KiB，未 GET；未验证它是否包含包归属。RPM DB/backend、完整文件 ownership 和数量对账必须在以后提取后验证。
- 两侧 debug 仓库存在，部分 armv7l debuginfo 条目可见；目录 GET 到限即停。没有获取 RPM，matching build IDs、DWARF 和 split .dwo/.dwp 可用性 UNKNOWN。
- 匹配 SDK/sysroot、开发包归属清单尚未证实。仅 runtime rootfs 不足以给出完整 API 兼容结论。
- 动态 loader 路径、有效 cache/search paths、scope 尚未读取。未来可做 ELF 依赖采集；不能预先声明 loader 环境完整。

## 8. 下一阶段决定

需要先解决 profile 选择、实际编译器来源、GCC KS/checksum/Base 一致性、是否接受源码版本混杂、产品/覆盖率门槛、SDK/debug 范围与分区提取方案。详见 [下一阶段计划](TIZEN_STATIC_ACCEPTANCE_NEXT_STEPS.md)。本次不判 BLOCKED_ACCESS 或缺镜像；核心结论是 **INSUFFICIENT_EVIDENCE**，不满足 READY_FOR_AUTHORIZED_DOWNLOAD。

本阶段交付 [机器清单](TIZEN_STATIC_INPUT_MANIFEST.json) 和 [完整证据](TIZEN_PREFLIGHT_EVIDENCE.log)。前后检查 139 个既有文件内容未变化；branch/HEAD/main 未变。未 commit/push、未跑兼容性或单元测试。日志中公共 recipe 的 credential 相关行已脱敏；校验针对原始字节。
