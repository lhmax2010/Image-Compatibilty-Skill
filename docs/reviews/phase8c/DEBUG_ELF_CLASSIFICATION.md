# Split Debuginfo 与运行时 ELF 分类

旧流程通过 ELF magic 入库，再从 ELF 类型和 readelf 的解释器文本建立消费者。VD 与 LLVM 的 /usr/lib/debug/lib/libc.so.6.debug 保留 ELF 类型、程序头、Build-ID 和 DWARF，.interp、.dynsym、.dynamic 及代码节却是 NOBITS。旧解析把 PT_INTERP 引用位置的内容当成解释器路径，在 candidate 原生闭包和 baseline-on-candidate 闭包中产生 TC-4ab4968318d673cf 和 TC-f4217cd52a2e94b3。两侧 /usr/lib/libc.so.6 的运行节有真实文件内容。 [旧报告和可复现样本](../phase8b/REAL_SAMPLE_VALIDATION.md)

| Manifest 字段 elf_runtime_role | 判据和处理 |
| --- | --- |
| DEBUG_ONLY | DYN/EXEC 的 GNU readelf 程序头、节头及计数可核对。存在文件范围内的 DWARF、保留的执行 LOAD 和空占位执行节，非空分配节只有 NOBITS 或 NOTE。保留采集和 DWARF，从运行时闭包中排除。 |
| RUNTIME | 可执行 PROGBITS 或 DYNAMIC 节有文件支撑。文件区间和对应 LOAD 的 VA/文件偏移映射一致。 |
| RUNTIME_WITH_DEBUG | 同时有已确认的运行内容和内嵌 DWARF。 |
| UNKNOWN | 工具输出不足、结构异常或布局超出模型。保留对象和相关观察，角色不给链接验证加分。 |

当已满足分离布局且 .interp 是 NOBITS 时，允许 GNU readelf 的单条 “Unable to find program interpreter name” 诊断。动态符号和版本完整性仍有独立门槛。 [GNU objcopy 的分离调试布局](https://www.sourceware.org/binutils/docs/binutils/objcopy.html)

collect_elf 保留 DWARF、Build-ID、原始 Evidence 和符号采集结果，递增采集缓存版本。dependency_checks 排除已证明的调试消费者和 Provider，搜索命中这类文件时保留 UNKNOWN。compare_elf 不输出调试对象的 SONAME 和 DT_NEEDED Linking 观察，也不把它安排为 runtime ELF 的 SONAME 对照。Linking 覆盖登记为不适用，DWARF 保持独立。新字段可选，历史 schema 1.2 manifest 可读，使用新判据需重新采集。 [ELF 采集](../../../.agents/skills/tizen-image-compatibility/scripts/compat/elf.py) · [Linking](../../../.agents/skills/tizen-image-compatibility/scripts/compat/linker.py) · [静态对比](../../../.agents/skills/tizen-image-compatibility/scripts/compat/compare.py) · [覆盖逻辑](../../../.agents/skills/tizen-image-compatibility/scripts/compat/coverage.py) · [DWARF](../../../.agents/skills/tizen-image-compatibility/scripts/compat/debuginfo.py)

```bash
readelf -W -h -l -d --dyn-syms -V -S -A -n -r "$ROOT/usr/lib/debug/lib/libc.so.6.debug"
readelf -W -h -l -d --dyn-syms -V -S -A -n -r "$ROOT/usr/lib/libc.so.6"
python3 -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -p test_phase8c.py -v
```

回归用 GCC/objcopy 生成内嵌 DWARF、分离 DWARF 和去调试的 ELF，交叉安排路径与后缀。覆盖 Build-ID 匹配、Evidence、截断和异常、合法 Provider、仍可确认的真实缺失、模糊 Provider 和解释器，以及保留 DWARF 覆盖。 [Phase 8C 测试](../../../.agents/skills/tizen-image-compatibility/tests/test_phase8c.py) · [真实对账](COVERAGE_BEFORE_AFTER.md)

分离文件与对应运行文件的 Build-ID 一致。VD libc 为 `a91fd88503ac5874d098e0271f68757baa489eb4`，LLVM libc 为 `2b5a33ab7b7c71e2a1df0b9741c93a654f93ad7d`。第二组 `/usr/lib/debug/lib/ld-linux.so.3.debug` 与运行加载器也分别匹配，VD 为 `ea82b530d45842e6aadf046ea0635608946c1a51`，LLVM 为 `131b954c1c28b3c2a62de3cd229719a830c8b426`。Build-ID 用于关联 DWARF，运行角色仍由文件内容布局判定。

真实 LLVM 的 mdnsd、libbackend_cpu.so 等正常对象的 GNU_STACK 对齐字段由 GNU readelf 显示为十进制 0。回归覆盖这一输出格式，避免使有效的 LLD 运行对象脱离确认路径。最终角色盘点为 VD 2,048 个 RUNTIME、3 个 RUNTIME_WITH_DEBUG、2 个 DEBUG_ONLY、1 个 UNKNOWN，LLVM 分别为 2,114、3、2、1。两侧的 UNKNOWN 均是原有 toybox 采集不完整。
