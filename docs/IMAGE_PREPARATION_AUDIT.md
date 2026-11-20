# Tizen 烧录包输入核查

## 普通 Rootfs TAR 回归

开发基线 `98e75cfb2b152c88b637bd14243a5fc9b0b30394` 中，`compat/images.py` 与首次发布提交 `b3291e3` 的 Git blob 都是 `6e0fc4fa00fda1633ac637cbd5867cba2fd035f0`。两版均支持直接包含根文件系统的 TAR 和 TAR.GZ。

另外将历史实现与本轮实现分别运行在同一对 TAR、TAR.GZ 夹具上。两者读取的文件内容、绝对软链接的镜像内解析、UID/GID、模式和 `walk()` 结果一致。独立准备入口也核对了其输出能够再经 `Image` 读取。记录为 `.local-backups/image-preparation/historical-tar-comparison.log`。

## 真实输入记录

用户确认本机没有本次 `TIZEN-ASAN-PUBLIC-*.tar.gz`。其 `platform.img → GPT → pltf_t.img → XZ → VDFS` 是待核对的产品链路。本轮实测对象为本机既有 headless 快照。先进行 TAR 流成员和原始签名检查，再通过新入口独立生成 Extraction Manifest。

| 真实归档 | SHA256 | 成员和结果 |
|---|---|---|
| `tizen-unified_20261115.233954_tizen-headless-armv7l.tar.gz` | `c4cb24c311c2d4907a180be23017a22a7115157aefe7e3574b0c2a9ec0c8c70b` | `rootfs.img` 614871040 B、`system-data.img` 63045632 B，均有 ext 超级块证据。另有两个 gzip ramdisk |
| `tizen-unified-toolchain_20261113.065522_tizen-headless-armv7l.tar.gz` | `4c3cc88a0854851dde6bbcfae71ae2a534d25e83b1778d2f9efeda7b4845d63e` | `rootfs.img` 625537024 B、`system-data.img` 62758912 B，均有 ext 超级块证据。另有两个 gzip ramdisk |

两个真实归档的 SHA256 均与历史公布值一致。它们各包含四个成员。准备层记录 `INSPECTED` 和 `FLASH_PAYLOAD_AMBIGUOUS`，保留两个 ext 候选的原始尺寸。完整 Rootfs 仍需经过该产品的实际挂载范围与分区组合核对。本轮没有部署、挂载或重新执行真实镜像分析。成员探测回执为 `.local-backups/image-preparation/real-tar-probe.log`，两份 `*-inspection/extraction-manifest.json` 保存完整准备层记录。

## 烧录准备层证据

合成归档封装 `platform.img`、GPT、`pltf_t.img`、XZ 和 VDFS 超级块标识。`tar -tvzf`、`sfdisk --json` 和 `xz --test` 独立核对归档与压缩。512 字节布局中分区从 LBA 6 开始，长 1 扇区，拷贝范围为偏移 3072 B、长度 512 B。XZ 流为 112 B，经 CRC64 校验后解出 7032 B。VDFS 魔数位于 0x400，布局字段为 `2007`。另有 4096 字节扇区的回归。合成数据只模拟磁盘结构和魔数，未实现或声称包含可由厂商工具读取的真实 VDFS 文件系统。记录在 `.local-backups/image-preparation/synthetic-evidence/`。 [GPT 长度与 CRC 规范](https://uefi.org/specs/UEFI/2.11/05_GUID_Partition_Table_Format.html) · [VDFS 布局与识别字段](https://github.com/HinTak/vdfs-tools/blob/master/include/vdfs4_layout.h)

本机有 `xz`、`sfdisk` 和 `sgdisk`。常用 VDFS 提取器名在 PATH 上不可用，已搜索的本地厂商工作目录也没有可用、经匹配的工具。公开 Samsung 衍生 `unpack` 可作为候选。其源代码明确校验超级块布局和校验和，本轮未下载或执行该工具。没有受信任配置时，正常比较返回 `VDFS_EXTRACTOR_UNAVAILABLE` 并保存失败回执，不生成兼容性结果。 [VDFS 上游工具](https://github.com/HinTak/vdfs-tools) · [unpack 完整性检查](https://github.com/HinTak/vdfs-tools/blob/master/unpack/unpack.c)

受控适配器夹具验证了合格回执、自动和显式准备、哈希不匹配、安全 TAR 解包、部分提取拦截及已准备根目录被篡改的分支。替代输入测试覆盖同构建 Rootfs、RPM 仓库、Rootstrap、错误构建 ID 和错配的 SDK 来源。对已声明的部分输入，`PARTIAL` 准备目录及其直接子根均不参与比较。候选没有完整目录证据时，命令缺失保持 UNKNOWN。

全量执行 `python3 -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v`。实现前 219 项，214 通过、5 跳过。实现后 228 项，223 通过、5 跳过、0 失败，覆盖既有 Phase 7A、v1.4 Impact 和最终 Release 回归。五项跳过仍是原本可选的 Clang/ARM、双编译器组合和 libabigail 测试。日志为 `.local-backups/image-preparation/baseline.log` 和 `verified-tests.log`。

## 结论与剩余验证

普通 Rootfs TAR/TAR.GZ 保持原有处理行为。旧版缺少烧录包内层处理。新版能识别并分离已支持的封装，VDFS 完整提取仍取决于匹配的可信提取器。本机没有本次 ASAN 样本和匹配提取器，真实产品的完整 GPT/XZ/VDFS 链路及真实 VDFS Rootfs 输出均未验证。

操作命令、提取器回执及构建身份绑定见 [镜像准备使用指南](../.agents/skills/tizen-image-compatibility/references/image_preparation.md)。
