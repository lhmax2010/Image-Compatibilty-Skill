# SR 静态证据与可确认范围

复用 Phase 8B 的根目录和原始 ext4 分区。readelf 读取 ELF，debugfs 以默认只读方式查询分区，ldconfig -p -C 只打印指定缓存。 [源文件、哈希和复现路径](../phase8b/REAL_SAMPLE_VALIDATION.md)

| 证据 | 独立复核 | 完整性与边界 |
| --- | --- | --- |
| 动态符号 | VD Getconf 有 FUNC GLOBAL DEFAULT UND confstr@GLIBC_2.4 (2)。LLVM libc 有 FUNC GLOBAL DEFAULT confstr@@GLIBC_2.4。 | 完整性取决于动态表计数、序号、类型、绑定、可见性及版本能否核对，工具输出无异常或截断。 |
| GNU 版本 | VD Getconf 的 version requirement 将索引 2 与 libc.so.6:GLIBC_2.4 关联。LLVM libc 定义该节点。LLVM ld-linux.so.3 也定义 GLIBC_2.4，但其完整动态表无 confstr。 | 版本定义、版本需求和实际符号项分别验证。 |
| 加载器配置 | 两侧 /etc/ld.so.conf 和现有 ld.so.conf.d 配置从 ext4 读出，与副本按字节核对，包括 HAL 与 Rust 库目录。 | 真实启动环境、运行时有效配置和默认目录仍未知。 |
| ld.so.cache | 与原始 ext4 字节一致。宿主解码器列出 VD 884 项、LLVM 906 项，二者的 libc.so.6 候选均为 /lib/libc.so.6。 | 记录候选、标志和顺序。有效搜索顺序和 HWCAP 仍未知。 |
| 权限与 xattr | 两侧 su 的 inode 为 UID/GID 0/0、04755。toybox 为 0/0、0755，原始 inode 有 security.capability 和 security.SMACK64。 | 源分区样本可核对。归档证据范围仍不覆盖全量 xattr、ACL、Smack、capability、硬链接或 Ramdisk。凭据、挂载策略及 AT_SECURE 未验证。 |
| Consumer / Provider | 已指定的 LLVM libc 文件满足 Getconf 接口。真实负例 TC-0c35c4e6fcae1a62 中，LLVM systemd 仍提供 SD_SHARED 节点，但实际缺少 VD 的 __start_SYSTEMD_BUS_ERROR_MAP@@SD_SHARED 导出。 | Linking 还需要实际进程作用域、Namespace 与依赖闭包。 |

缓存 SHA256 分别为 VD `a2949b62bfff4c0ff207d85fedc9eb5c88433d74b1fb50fd281948a359790edb`、LLVM `0f76b13f227dc796ef102d92c53017be83d9472772bd4be1f8d348a4bb25df7e`。 [输入身份](../phase8a/SR_EVIDENCE_EXCERPTS.json)

报告已有 candidate.lookup_candidates、provider_path 和 candidate.scope_proven，可表达候选存在但绑定未证实。Getconf 的 TC-690df44183e7650a 保留 UNKNOWN。插件 activation_dm.so 的 GCC_3.5 和 pop_epc_event 是文件级观察，仍缺已证实的进程根和 dlopen 作用域。 [Linking 逻辑](../../../.agents/skills/tizen-image-compatibility/scripts/compat/linker.py) · [真实样本](../phase8b/REAL_SAMPLE_VALIDATION.md)

```bash
readelf -W -h -l -d -V --dyn-syms "$VD/usr/libexec/getconf/getconf"
readelf -W -h -l -d -V --dyn-syms "$LLVM/usr/lib/libc.so.6"
readelf -W -h -l -d -V --dyn-syms "$LLVM/usr/lib/ld-linux.so.3"
debugfs -R 'cat /etc/ld.so.conf' "$LLVM_EXT4"
debugfs -R 'cat /etc/ld.so.cache' "$LLVM_EXT4" | sha256sum
ldconfig -p -C "$LLVM/etc/ld.so.cache"
debugfs -R 'stat /usr/bin/su' "$LLVM_EXT4"
debugfs -R 'ea_list /usr/bin/toybox' "$VD_EXT4"
```
