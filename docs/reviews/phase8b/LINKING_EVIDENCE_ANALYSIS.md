# 真实 SR Linking UNKNOWN 证据分析

输入使用 Tizen Unified `tizen-headless-armv7l`，方向为 SR VD 消费者迁至 SR LLVM。保留的 Phase 8A 原始报告共有 903,383 条 Finding。流式读取全部记录后，未压缩 JSON 的 SHA256 仍为 `6aaf52f97041441bd1090ca40132949c30146d0ab652ee9d516df3e97cee3d99`，与 Phase 8A 对账一致。 [输入及历史哈希](../phase8a-final/SR_REVALIDATION.md)

| 解析原因 | baseline 根 | candidate 根 | 无根记录 | 合计 | 尚缺的证据或当前边界 |
|---|---:|---:|---:|---:|---|
| `unknown_symbol_scope` | 217,854 | 224,195 | 0 | 442,049 | 明确 Root Consumer、启动时实际加载的有序对象闭包及作用域。独立 DSO 不提供此证据。 |
| `unknown_symbol_semantics` | 157,730 | 156,455 | 0 | 314,185 | 确定的选择次序、绑定、可见性和类型，兼顾弱符号、IFUNC、版本回退、插桩、同名 Provider 和 Namespace。 |
| `unknown_version_requirement` | 28,612 | 28,495 | 0 | 57,107 | 核对依赖指定的实际 Provider、版本需求及其提供的版本节点，闭合启动上下文。 |
| `unknown_search_environment` | 21,483 | 22,306 | 0 | 43,789 | 目标有效搜索路径、缓存、动态标签和软链接、hwcaps、启动凭据、预加载及 AT_SECURE。 |
| `unknown_loader_abi` | 740 | 746 | 0 | 1,486 | 记录要求的解释器路径、实际解析到的加载器及相关 ELF 完整度、ABI 和执行上下文。该原因也包括文件存在但上下文未完成的记录。 |
| `DT_NEEDED` 差异 | 0 | 0 | 1,060 | 1,060 | ELF 自身依赖表发生变化。需要验证变化后的闭包与消费者，才能判断影响。 |
| `unknown_loader_feature` | 304 | 314 | 0 | 618 | 需要证明目标加载器对未建模动态标志和过滤、审计等机制的实际处理。 |
| `missing_provider` | 1 | 1 | 0 | 2 | 两条来自 split `libc.so.6.debug` 的不可用解释器字段，原始报告均保留 UNKNOWN。 |
| `unknown_collection` | 1 | 1 | 0 | 2 | 两侧 `toybox` 的 ELF 工具采集不完整。 |
| 全局覆盖提示 | 0 | 0 | 2 | 2 | 缓存、命名空间、动态加载与符号解析的整体适用边界。 |
| 合计 | 426,725 | 432,513 | 1,062 | 860,300 | |

根的列取自原始 Finding 的 `root_consumer_image`。candidate 根列是候选自身根检查。表中的条数是观察数，同一根可以产生多条记录。基线 Linking 完整度的分母是 2,054 个适用检查单元。已复跑的四条原始 Finding 和实际缺失条件见 [真实案例](REAL_SAMPLE_VALIDATION.md)。模型边界见 [依赖闭包代码](../../../.agents/skills/tizen-image-compatibility/scripts/compat/linker.py) 和 [加载器证据契约](../../../.agents/skills/tizen-image-compatibility/references/correctness.md)。

## 原盘可以恢复的事实

- 用 `debugfs` 只读核对 ext4 中的 `ld.so.cache`、`ld.so.conf` 及两条 include 文件。分区内字节与已提取副本逐文件 SHA256 一致。两侧主配置相同，记录 `/usr/local/lib` 和 `include /etc/ld.so.conf.d/*.conf`，两个片段记录 HAL 目录及 Rust dylib 目录。两侧原始根都未发现 `/etc/ld.so.preload`。这些是磁盘事实，执行进程的环境和替代配置仍需现场记录。
- 宿主 `ldconfig -p -C` 只读取指定归档缓存。两侧分别有 VD 884、LLVM 906 条输出，观察到的条目名无重复，均标为 `libc6,soft-float`。两侧都把 `libc.so.6` 指向 `/lib/libc.so.6`，把 `libgcc_s.so.1` 指向 `/lib/libgcc_s.so.1`。缓存 SHA256 分别为 `a2949b62bfff4c0ff207d85fedc9eb5c88433d74b1fb50fd281948a359790edb`、`0f76b13f227dc796ef102d92c53017be83d9472772bd4be1f8d348a4bb25df7e`。解码结果证明缓存的记录内容。生效顺序、目标架构和 hwcaps 的取舍、默认搜索目录以及作用域仍需目标加载器证据。
- 两侧原始 `toybox` 的 mode 为 0755，inode 含 `security.capability`（20 字节）及 `security.SMACK64`。两侧 `su` 为 04755。VD 的 `getconf` 为普通权限，所查 inode 有 Smack 标签，未列出 file capabilities。此类记录可以与 SHA256 和 inode 关联并做成独立源证据。实际凭据、挂载策略、LSM 与 `AT_SECURE` 仍取决于获授权环境中的启动现场。 [ext4 扩展属性](https://www.kernel.org/doc/html/latest/filesystems/ext4/attributes.html) · [Smack 标签](https://www.kernel.org/doc/html/latest/admin-guide/LSM/Smack.html)
- 两侧 `actd.service` 都记录 `ExecStart=/usr/sbin/actd`，这是可验证的启动配置线索。它不足以证明插件的实际调用、打开顺序和 Namespace。后续可从授权的 SR guest 内记录进程的实际可执行文件、加载库和 link-map、脱敏搜索变量、凭据、挂载和 auxv `AT_SECURE`。需要根、文件与目标环境标识的绑定。 `LD_DEBUG` 仅适用于受控普通执行，安全模式数据需要能观测真实进程的授权路径。 [glibc 调试变量](https://snapshots.sourceware.org/glibc/trunk/latest/manual/html_node/Dynamic-Linker-Environment-Variables.html) · [glibc link-map 与 Namespace](https://snapshots.sourceware.org/glibc/trunk/2026-04-01_23-23_1775085781/manual/html_node/Dynamic-Linker-Introspection.html)

### 复现计数

对保留的 `findings.csv.gz` 执行。压缩文件由 Phase 8A 验证流程在序列化时生成，里面是完整 CSV。

```python
from collections import Counter
import csv, gzip
with gzip.open("findings.csv.gz", "rt", newline="") as stream:
    all_rows = 0
    reasons = Counter()
    for row in csv.DictReader(stream):
        all_rows += 1
        if row["dimension"] != "linking":
            continue
        assert row["status"] == "UNKNOWN"
        _, marker, suffix = row["potential_impact"].partition("Resolution state: ")
        reason = suffix.split(".", 1)[0] if marker else (
            "DT_NEEDED_delta" if row["interface"] == "DT_NEEDED" else "coverage_notice"
        )
        reasons[reason] += 1
assert all_rows == 903383 and sum(reasons.values()) == 860300
print(reasons.most_common())
```

组合报告根字段来自同一次 JSON 流式读取，`resolution` 无字段时依据 `interface == 'DT_NEEDED'` 或覆盖提示分类。
