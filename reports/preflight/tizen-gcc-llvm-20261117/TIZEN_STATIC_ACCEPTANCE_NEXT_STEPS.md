# 后续下载、提取和静态验收计划（尚未执行）

当前输入状态 **INSUFFICIENT_EVIDENCE**。此计划不是下载或执行授权。

1. **输入审查 — 需要用户/PM 决定。** 从同名 `tizen-headed-armv7l` 或 `tizen-headless-armv7l` 中选择一个验收范围；如两个都要，分别记录/运行，不混用。boot-rpi 只是独立组件。如纳入 HAL/kernel 范围，另行明确匹配组件及组装关系。确认产品/硬件、方向 baseline 消费者→candidate。
2. **补来源证据 — 需要构建方信息。** 提供实际包→编译器 family/version/flags/instrumentation 映射；解释 GCC 五个 KS 校验不符、可变 Base/reference 和 build.xml 时间歧义，给出与已发布归档一致的冻结元数据。不要仅以 libgcc/Clang 包存在或 URL 名称认定构建编译器。用户/PM 决定接受源码 revision 混杂的镜像比较，还是另行授权使用匹配源码/配置的精确构建；当前未替换任何 URL。
3. **确定静态范围 — 需要用户/PM 决定。** 提供 required contracts、最低覆盖率和允许的 UNKNOWN。确定匹配 SDK/开发包 inventory 与 debuginfo/build-id 来源；缺失时明确保留 API/type-layout UNKNOWN。允许继续部分静态检查不代表这些维度通过。暂不包含编译探针、runtime、性能/硬件执行。
4. **准备后批准下载 — 下一项需要显式授权的操作。** 审查 JSON 中选定 profile 的两个精确 archive URL、HEAD 字节、发布 SHA256，以及批准后的磁盘目录和容量预算。用户授权后才允许下载这两个文件和选定的配套元数据；不得扩展为递归 mirror、下载其他构建或批量 RPM。下载完验证 SHA256 和长度，保存 immutable source record；校验不符立即停止，不忽略错误。
5. **检查归档并批准/执行离线提取范围。** 在外部临时工作区先列出成员、尺寸、路径和文件类型，检查空间/文件数量，不运行 recipe、包 scriptlet 或镜像二进制。确认真实 filesystem magic：外层 loop tar 是分区容器，不能直接交给 checker 并当 rootfs。对 ext4 采用宿主用户态只读提取到新目录，不 mount/losetup/chroot/sudo；不得用 debugfs 写模式。headed 的 F2FS user.img 需要另行确认合适提取工具，或产品方明确排除该分区并记录缺口。initrd 的 recipe cpio 与 XML ext4 表述需在授权后以实际 magic 确认，不盲信后缀。保留权限/链接/xattr/特殊节点的原始元数据及无法保真的缺口；提取工具不完整不得静默略过。
6. **组装一致逻辑 rootfs。** 分别映射 /、/opt、必要时 /opt/usr 与已批准的配套组件；记录每个分区、挂载点来源和冲突，不覆盖原始分区/归档。不能把只提取 rootfs.img 的结果冒充完整所有分区镜像。建立前后内容哈希/清单以验证源不变。
7. **静态运行前最终检查。** 检查实际 /etc/os-release、ELF armv7l/EABI/PCS、RPM DB backend/独立已安装 NEVRA/file list、debug build-id、SDK 关联与 loader 配置；对 RPM 数据库使用副本，不把 source DB 打开写入。实际 installed counts 才可用于对账。重新检查 disk/inodes/RAM/swap；实际容量超预算则暂停。显式配置现有 abidiff 路径或保留 UNKNOWN，不默默安装工具。metadata completeness 只能来自 collector 实际证据。
8. **单独获准静态执行后运行既有 checker。** 填写根目录 `V1_2_STATIC_ACCEPTANCE_INPUT.json` 的副本，再将其中 `static_config` 导出为独立 CLI config。保留 runtime.enabled=false、runtime.authorized=false、cross_compilation.enabled=false；mode=static，输出新目录，cache 在源之外。已有本地 RC 不做代码修改；不以本 Phase 0 JSON 直接充当 CLI config。确切命令在路径/范围批准后固定。本任务未执行任何 checker 命令。
9. **静态结果审查。** 完整 JSON/CSV/HTML 数量与 ID、RPM 数量/归属、loader UNKNOWN、覆盖率分母和 Expected Test Manifest 应一致。检查源码哈希不变，保留 raw evidence。确认失败与证据缺口分开报告；exit 0 不等于全兼容。四向矩阵和真实目标行为仍未验证。进入后续阶段不能自动授权发布/合并代码。

可以先提供 profile/产品选择与构建来源资料供 reviewer 审查。Phase 0 到此停止；下载、提取和实际静态分析均等待后续明确授权。
