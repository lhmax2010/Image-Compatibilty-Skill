# 覆盖变化与候选改进

保留的 Phase 8A 基线用于生产报告统计。Phase 8B 运行的是六个真实 baseline 根的独立局部回放，补入可恢复文件证据后重新观察。没有宣称新的生产覆盖率，也没有修改任一已有 Finding。 [原始原因分布](LINKING_EVIDENCE_ANALYSIS.md) · [局部证据](REAL_SAMPLE_VALIDATION.md)

| 核对项 | Phase 8A | Phase 8B |
|---|---:|---:|
| 原报告总 Finding | 903,383 | 903,383 |
| Linking UNKNOWN | 860,300 | 860,300 |
| Linking 完整验证单元 | 0 / 2,054 | 0 / 2,054 |
| 升级为确认性 Linking 的原 Finding | — | 0 |

| 六个真实 baseline 根 | 原 manifest 局部观察 | 补入部分文件证据后 | 新确认性观察 |
|---|---:|---:|---:|
| `/usr/libexec/getconf/getconf` | 33 | 58 | 0 |
| `/etc/actd/available-modules/activation_dm.so` | 44 | 95 | 0 |
| `/etc/alternatives/halt` | 831 | 1,615 | 0 |
| `/usr/bin/su` | 155 | 244 | 0 |
| `/usr/bin/toybox` | 1 | 1 | 0 |
| `/usr/lib/debug/lib/libc.so.6.debug` | 2 | 2 | 0 |
| 合计 | 1,066 | 2,015 | 0 |

回放前的四个历史样本 ID 完全匹配。补入 LLVM 磁盘缓存观察以及 VD 个别 inode 的 mode/xattr 后，Getconf 的 `DT_NEEDED:libc.so.6` 已列出候选 `/usr/lib/libc.so.6`，仍是 `unknown_search_environment`。 `confstr@GLIBC_2.4` 从无候选观察变为候选存在但 `unknown_symbol_semantics`。回放产生的临时 ID 与额外依赖观察只用于分析。2,015 条全部保持 UNKNOWN。

## 最小改进评估

| 候选改进 | 现场正例与反例 | 允许确认的前提或结论 |
|---|---|---|
| 给缓存和绝对解释器结果附可追溯候选路径 | Getconf 的解释器和 libc 可由原镜像解析。split libc debuginfo 的 `.interp` 为 NOBITS，两个假解释器观察不能作为缺库证明。 | 解析必须绑定真实运行 ELF、Rootfs 和有效 cache 快照。需要已知目标 ABI、加载路径、已加载对象身份及启动上下文才可给 Linking 信用。原盘缓存不足以设置 `cache_complete`。 |
| 读取实际 inode xattr，解释 secure-execution 缺口 | Getconf 普通 mode、未见能力属性。反例是 `toybox` mode 0755 却含 file capabilities，`su` 为 04755。 | 可以确认 inode 事实。只有匹配的文件、真实凭据、挂载、LSM/执行上下文以及可核验 auxv 才能确认正常执行。在现有模型中保留相同门控。 |
| 将版本检查绑定实际命名 Provider 与闭包 | LLVM libc 定义 `GLIBC_2.4` 并导出 `confstr@@GLIBC_2.4`。同一节点也在真实解释器中，解释器却没有该符号。 | 文件内检查支持局部正反结论。确认实际绑定需完整根、加载器/有效路径、受支持 Namespace、版本关系和适用符号语义。 |
| 区分无关闭包缺口和具体版本义务 | 两侧 `actd.service` 指名主程序，实际插件加载证据仍缺。Getconf 解析到候选也无法推出 `halt` 或插件进程的绑定。 | 只有在具体根已验证、每个相关依赖和加载顺序已确认、且可排除其他命名空间和交错加载时才能考虑进一步收窄门控。 |

未采用生产实现变更。当前缺口是目标上下文。现有 resolver 可以表达局部候选并保留 UNKNOWN。完整闭包的正反例与故意撤掉前提的反例由 `test_bounded_linking_scope_and_required_version` 验证；SONAME、作用域和 mode 的控制由 Phase 7A `LoaderFixTests` 验证。 [完整性门控源码](../../../.agents/skills/tizen-image-compatibility/scripts/compat/linker.py) · [版本闭包回归](../../../.agents/skills/tizen-image-compatibility/tests/test_phase8a.py) · [Phase 7A 回归](../../../.agents/skills/tizen-image-compatibility/tests/test_static_fixes.py)

## 局部回放复现

使用 Phase 8A 的两份 `baseline-manifest.json.gz`、`candidate-manifest.json.gz`。用 [样本命令](REAL_SAMPLE_VALIDATION.md) 将 LLVM 的磁盘缓存打印到 workspace 内的 `llvm-cache.txt`，同时核验 VD 三个 inode 的 mode 和属性。以下以 Getconf 演示。 `SRC` 指向保留的原始报告目录。

```python
# PYTHONPATH=.agents/skills/tizen-image-compatibility/scripts
from collections import defaultdict
import gzip, json, os, re
from pathlib import Path
from compat.linker import dependency_checks

src = Path(os.environ["SRC"])
def load(side):
    with gzip.open(src / (side + "-manifest.json.gz"), "rt") as stream:
        return json.load(stream)

baseline, candidate = load("baseline"), load("candidate")
cache = defaultdict(list)
for name, path in re.findall(r"^\s+(\S+) \([^)]+\) => (/.*)$",
                             Path("llvm-cache.txt").read_text(), re.M):
    cache[name].append(path)
partial = candidate | {"loader_environment": {
    "model": "glibc", "environment_complete": False, "cache_complete": False,
    "cache": dict(cache),
}}
path = "/usr/libexec/getconf/getconf"
root = next(item for item in baseline["elf_objects"] if item["path"] == path)
file_facts = {"mode": "0o755", "security_metadata_complete": True,
              "has_file_capabilities": False}
baseline_inode = baseline | {"filesystem": [
    item | file_facts if item["path"] == path else item for item in baseline["filesystem"]
]}
label = "baseline consumers on candidate"
before = dependency_checks(candidate, label, [root], consumer_manifest=baseline)
after = dependency_checks(partial, label, [root], consumer_manifest=baseline_inode)
assert (len(before), len(after)) == (33, 58)
assert all(row["status"] == "UNKNOWN" for row in before + after)
for row in after:
    if row["consumer_path"] == path and row["check_id"].startswith(("DT_NEEDED:", "version:", "import:confstr")):
        print(row["check_id"], row["provider_path"], row["resolution"])
```
