# 真实 ELF 样本与局部复核

所有样本取自已验收的 SR 根目录和 manifest，未重下载或重新提取镜像。下面的确认结果限于指明的镜像文件和检查项。实际加载结果在原报告中保持 UNKNOWN。 [来源与镜像 SHA256](../phase8a/SR_EVIDENCE_EXCERPTS.json)

## 正例，基线 Getconf → LLVM libc

VD `/usr/bin/getconf` 解析到 `/usr/libexec/getconf/getconf`。ELF 为 ARM32，解释器 `/lib/ld-linux.so.3`，`DT_NEEDED` 为 `libc.so.6`。动态符号是强引用 `FUNC GLOBAL DEFAULT UND confstr@GLIBC_2.4 (2)`，`.gnu.version_r` 把索引 2 关联到 `libc.so.6:GLIBC_2.4`。LLVM 缓存的同名条目指向 `/lib/libc.so.6`，镜像内解析到 `/usr/lib/libc.so.6`。该对象具有相同 SONAME、匹配的 ARM ABI 元数据、`.gnu.version_d` 中的 `GLIBC_2.4` 和 `FUNC GLOBAL DEFAULT confstr@@GLIBC_2.4`。以上确认指定文件的符号契约满足。

| 证据文件 | SHA256 |
|---|---|
| VD Getconf ELF | `f0e106b6582e1b29e0562968187210df32eb6e6574e7856b16f30a7786b60336` |
| LLVM libc ELF | `9f2ae4ee0d10374c7681a33b09b5a84dbfca82c3d1bc012edf81483f11202b96` |
| LLVM `ld-linux.so.3` ELF | `b011ebe723dc6e8115f4eb44c964817f7d61878e44d6de3a9367e7359b5bf7da` |

## 负例，真实文件的定向检查

1. 用同一个真实 Getconf 强引用检查实际解释器 ELF `/usr/lib/ld-linux.so.3`。它也定义 `GLIBC_2.4`，但 SONAME 是 `ld-linux.so.3` 且完整动态符号表无 `confstr`。候选文件有同名版本节点仍无法满足这个已指定的 libc 符号契约。此为真实对象组成的受控负对照。
2. 真实 VD 与 LLVM 的 `/usr/lib/systemd/libsystemd-shared-244.so` 有相同 SONAME 和 `SD_SHARED` 版本节点。VD 导出 `__start_SYSTEMD_BUS_ERROR_MAP@@SD_SHARED`，LLVM 在完整动态表中缺此导出。对应 ABI Finding `TC-0c35c4e6fcae1a62`。未得到有确证绑定的消费者，因此原始 Linking 保持 UNKNOWN。
3. 两条旧 Linking `missing_provider`（`TC-4ab4968318d673cf`、`TC-f4217cd52a2e94b3`）都来自 `/usr/lib/debug/lib/libc.so.6.debug`。两侧的 `.interp`、`.dynsym`、`.dynamic` 都是 NOBITS，历史解析的解释器字段不可用。运行时的 `/usr/lib/libc.so.6` 对应三节分别为 PROGBITS、DYNSYM 和 DYNAMIC。负例确认 debug 文件没有可用的解释器路径，原始观察继续保持 UNKNOWN。现有真实运行时加载器仍可在镜像中定位。

## 证据缺口的原始样本

| Finding ID | 已观察 | 保持 UNKNOWN 的原因 |
|---|---|---|
| `TC-063f63c2674b34ea` | `activation_dm.so` 需要 `pop_epc_event`。 | DSO 无已证实进程根、启动或插件作用域。 |
| `TC-000be73b4a4e552a` | `/etc/alternatives/halt` 的 `gethostname_malloc@SD_SHARED` 有候选。 | 原记录 `scope_proven=false`，没有加载作用域证明。 |
| `TC-1f8a019a1fcbc848` | `activation_dm.so` 要求 `libgcc_s.so.1:GCC_3.5`。 | 需求存在，原根的实际 Provider 和闭包仍未证实。 |
| `TC-1164a6c8dfac4200` | `activation_dm.so` 可读取原盘 mode 和 xattr 名称。 | 文件证据不足以确定启动凭据、AT_SECURE 或插件 Namespace。 |
| `TC-690df44183e7650a` | Getconf 的 `confstr@GLIBC_2.4`，局部对象正例已核实。 | 原始报告缺真实有效搜索上下文和符号作用域。 |

四条选定原始案例和 Getconf 的五条根检查均在原有 CSV 内按 ID 回查。共 9 条原始 ID 核对状态，校验 6 个样本引用的内容寻址 Evidence 文件 SHA256。 [原因分布](LINKING_EVIDENCE_ANALYSIS.md) · [局部回放及变化](COVERAGE_BEFORE_AFTER.md)

## 复现命令

`VD`、`LLVM` 使用已有只读根目录。 `VD_EXT4`、`LLVM_EXT4` 使用对应的原始 `rootfs.img`。直接使用已核对的虚拟路径解析结果，避免沿绝对软链接访问宿主。

```bash
readelf -W -h -l -d -V --dyn-syms "$VD/usr/libexec/getconf/getconf"
readelf -W -h -l -d -V --dyn-syms "$LLVM/usr/lib/libc.so.6"
readelf -W -h -l -d -V --dyn-syms "$LLVM/usr/lib/ld-linux.so.3"
readelf -W -d -V --dyn-syms "$VD/usr/lib/systemd/libsystemd-shared-244.so"
readelf -W -d -V --dyn-syms "$LLVM/usr/lib/systemd/libsystemd-shared-244.so"
readelf -W -S "$LLVM/usr/lib/debug/lib/libc.so.6.debug"
readelf -W -S "$LLVM/usr/lib/libc.so.6"
debugfs -R 'ea_list /usr/bin/toybox' "$VD_EXT4"
debugfs -R 'stat /usr/bin/su' "$LLVM_EXT4"
debugfs -R 'cat /etc/ld.so.cache' "$LLVM_EXT4" | sha256sum
ldconfig -p -C "$LLVM/etc/ld.so.cache"
```

`debugfs` 使用默认只读打开。 `ldconfig` 只打印指定缓存。测试全程不调用目标 `ldd`、加载器或目标 ELF。GNU 版本关系见 [ELF 版本表规范](https://refspecs.linuxfoundation.org/LSB_5.0.0/LSB-Core-generic/LSB-Core-generic/symversion.html)。
