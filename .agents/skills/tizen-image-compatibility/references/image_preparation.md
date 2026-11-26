# Tizen 镜像准备

普通 Rootfs 目录、Rootfs TAR/TAR.GZ、SquashFS 和 RPM 集合继续使用现有 CLI。烧录包应先核对内层格式。准备层在本地工作目录中处理数据副本，原始镜像只读打开。GPT 分区通过主、备表的 CRC32、几何、可用扇区、分区重叠和最大允许长度校验后，才按字节范围复制。XZ 采用有内存上限和输出上限的流式解压。支持一个 XZ 流及四字节对齐的零填充。VDFS 依据超级块位置的魔数和布局字段识别。识别记录不代表文件系统完整性验证。 [UEFI GPT 规范](https://uefi.org/specs/UEFI/2.11/05_GUID_Partition_Table_Format.html) · [VDFS 磁盘布局](https://github.com/HinTak/vdfs-tools/blob/master/include/vdfs4_layout.h)

## 检查及准备烧录包

```bash
SKILL=.agents/skills/tizen-image-compatibility
python3 "$SKILL/scripts/prepare_image.py" "$IMAGE" \
  --inspect --output ./reports/image-inspection
python3 "$SKILL/scripts/prepare_image.py" "$IMAGE" \
  --config ./compat-config.yaml --output ./reports/prepared-image
```

两条命令使用不同的新输出目录。`--inspect` 读取 TAR 内容、校验已识别的 GPT/XZ，并记录分区及文件系统标识。它不调用文件系统提取器。GPT 存在多个可识别候选分区时，可设置 `preparation.platform_partition`，默认为 `pltf_t.img`。分区名称只用于选择已经按内容识别的候选项。多个容器候选无法确定时会显式停止。ext、EROFS 等识别结果可用于选择厂商提供的离线提取环境或下面的替代输入。

`extraction-manifest.json` 记录源 SHA256、识别的各层、分区偏移和长度、XZ 校验类型和大小、适配器版本、覆盖范围及输出身份。`READY` 的 `runtime-rootfs` 可将整个准备目录传入 `--baseline` 或 `--candidate`。比较时重新校验输出目录和元数据身份。`PARTIAL`、`FAILED` 和中断留下的 `PREPARING` 发布标记均会拦截分析。普通 Rootfs 若直接输入，仍按原有 Rootfs 输入语义处理。已知不完整的目录应通过带 `complete: false` 的准备凭据保留其范围。

准备回执的 `coverage.evidence_scope` 和分析清单的 `image.input_evidence_scope` 分别记录路径、内容、UID/GID/mode、xattr、ACL、Smack、file capabilities、硬链接、ramdisk 和特殊文件证据。TAR 中保存的 UID/GID/mode 与设备节点声明属于归档元数据。普通 TAR 提取不证明安全属性或硬链接仍完整。对外部提取的输入，用 `analysis.input_scope.baseline` 和 `analysis.input_scope.candidate` 声明已知缺口，例如 `{ramdisk: false, xattrs: false, file_capabilities: false, hardlinks: false}`。除 ramdisk 是否纳入外，配置只接受明确缺口，不提升提取器的证据等级。文件路径盘点与 ELF/符号/安全证据独立核对。

## VDFS 适配器

配置由操作方审核的宿主机工具，或包装厂商只读提取器的程序。工具需要在不提权、不挂载、不执行镜像程序的条件下读取输入文件并输出 TAR 与 JSON。应在隔离的低权限环境中运行可信工具并核对具体 VDFS 布局。公开的 Samsung 衍生工具可作为候选，版本匹配、完整文件提取与错误处理需由操作方验证。配置中的命令通过 argv 直接启动。没有配置或宿主工具不可用时，准备返回 `VDFS_EXTRACTOR_UNAVAILABLE`。 [Samsung 衍生 VDFS 工具](https://github.com/HinTak/vdfs-tools)

```yaml
preparation:
  platform_partition: pltf_t.img
  xz_memory_mib: 256
  adapter_timeout_seconds: 1800
  vdfs_adapter:
    command: [/path/to/trusted/tizen-vdfs-adapter, "{input}", "{output}", "{receipt}"]
    version_args: [--version]
```

`--version` 应返回 0 并在 stdout 打印工具和布局支持版本。三个占位符必须作为独立 argv 项出现。适配器输入是工作区的 VDFS 副本。输出 TAR 由准备层安全解包。回执示例如下。

```json
{
  "schema": "tizen-vdfs-receipt/1",
  "input_sha256": "<SHA256 of the VDFS copy>",
  "output_tar_sha256": "<SHA256 of the emitted TAR>",
  "scope": "runtime-rootfs",
  "complete": true,
  "excluded_partitions": {}
}
```

完整回执须覆盖运行时根文件系统。若 GPT 有其他分区，`excluded_partitions` 必须逐个按分区 GUID 提供确认无需用于该 Rootfs 的理由。仅提取单一分区、失败或遗漏文件时用 `complete: false`。归档和复制输入的所有权与模式有元数据记录。xattr、ACL、硬链接关联与设备节点等依赖具体提取证据，默认不提供完整受信任的运行时安全上下文。回执是显式操作方信任依据，框架会核对记录的哈希和完整度声明。

## 同构建替代输入

可提供预提取 Rootfs、原始 RPM 集合或 Rootstrap。用 `--identity-only` 获取文件 SHA256 或目录树身份。目录树身份绑定相对路径、类型、模式、链接文本与文件内容。构建方提供的受信任记录需绑定原始烧录包、替代输入和构建 ID。例如用以下字段记录匹配的 Rootfs。

```json
{
  "schema": "tizen-build-replacement/1",
  "build_id": "<expected build identifier>",
  "kind": "rootfs",
  "source_sha256": "<original image SHA256>",
  "replacement_sha256": "<replacement SHA256 or tree-v1 identity>",
  "complete": true
}
```

```bash
python3 "$SKILL/scripts/prepare_image.py" "$IMAGE" \
  --replacement ./same-build-rootfs --replacement-kind rootfs \
  --provenance ./build-receipt.json --build-id "$BUILD_ID" \
  --output ./reports/prepared-rootfs
```

RPM 替代输入使用 `rpm-repository`，支持包清单和归属范围内的证据。它不会给出完整已安装清单或运行时根文件系统覆盖。Rootstrap 使用 `rootstrap`，将准备目录传给 `--baseline-sysroot` 或 `--candidate-sysroot`。它只用于 SDK 环境。`full` 和 `runtime` 模式会核对准备后的 Rootstrap 所绑定的原始镜像身份与对应侧运行时输入一致。已预提取的运行时目录也可通过同源准备凭据建立这项关联。构建 ID 与两侧内容身份均须与记录匹配。

## EROFS

The inspection receipt records the EROFS superblock offset and block size, raw feature masks, recognized compression algorithms and the declared extra device count. Standard extraction needs host `fsck.erofs` with `--extract` and `--no-preserve`, Bubblewrap with size-limited tmpfs, and host `tar`. The image remains read-only. The extractor operates in a private bounded scratch directory, records version and stderr evidence, and the output is revalidated by the existing safe TAR path. It does not re-establish original ownership, modes, xattrs, capabilities or complete multi-partition product coverage.

`EROFS_EXTRACTOR_UNAVAILABLE` identifies missing tools. `EROFS_FEATURE_UNSUPPORTED` retains unrecognized feature or compression bits. `EROFS_EXTRA_DEVICES_REQUIRED` identifies an unbound external-device requirement. A trusted `preparation.erofs_adapter` can use the same argument structure as the VDFS adapter, with receipt schema `tizen-erofs-receipt/1`. It declares integer `supported_compat_mask`, `supported_incompat_mask` and `supported_compression_mask` fields covering the detected bits. The receipt binds the input and TAR SHA256 and attests scope and any excluded GPT partitions. For multiple external devices, supply a verified same-build replacement or use the corresponding RPMs.

Samsung KantSU2e vendor features need a matching trusted extractor for that build and any required companion data, or a verified same-build rootfs. Standard and vendor EROFS actual extraction remain unverified on the v1.5.1 development host. See the [RPM fallback](rpm_repository.md#when-erofs-extraction-is-blocked).
