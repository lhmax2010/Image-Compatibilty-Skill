# DWARF Finding ID 稳定性

旧 `debug_source()` 将宿主机绝对路径传入 `baseline.debug.path` 与 `candidate.debug.path`。`finding()` 对完整字段散列，因此仅替换临时解包目录就改变了 ID。Phase 8A 现场有 7 对这样的 UNKNOWN 记录。修改前用同一个 fixture 在两个临时目录重跑，复现同一类型的 ID 漂移。 [原始 Phase 8A 实证](../phase8a/SR_BEFORE_AFTER.md) · [Finding ID 入口](../../../.agents/skills/tizen-image-compatibility/scripts/compat/core.py)

现在宿主绝对路径只在定位和复制 debuginfo 时使用。报告保存虚拟路径、来源位置、构件种类、已核对的 build ID 和原始 Evidence 引用。DWARF 工具诊断中由 Skill 生成的 staging 前缀在报告内归一化。完整诊断以标准化的 stdout、stderr 和执行错误摘要参与 ID，原始字节及其 Evidence 路径继续保留。截断诊断仍使用原始 Evidence 身份，避免基于截断预览把两个结果误认为同一条。组件、接口、检测器、判定及其他契约字段仍参与 ID。普通 ELF、ABI 和 Linking 的通用哈希规则保持基线。 [DWARF 实现](../../../.agents/skills/tizen-image-compatibility/scripts/compat/debuginfo.py) · [路径、证据和去重回归](../../../.agents/skills/tizen-image-compatibility/tests/test_phase8a_final.py)

## History 与 Impact 兼容性

原始 schema 1.2 和 v1.3 增强索引保留每份输入中的原 ID。Impact Sidecar 继续按本次输入的 ID、载荷散列和原 Evidence 读取。History 先作精确 ID/载荷匹配。回退匹配仅适用于两侧都唯一的 DWARF 契约，要求组件、接口、检测器、状态、诊断、Evidence 与其余有效载荷等价。旧报告已知提取布局可映射到同一虚拟路径。新报告中原始诊断路径不同但标准化指纹一致时可配对。证据或语义有差异的观察保留未配对。UNKNOWN 的旧、新同一观察仍是 `PERSISTING_RISK`，类型为 `UNIQUE_DWARF_OBSERVATION`。 [History 匹配](../../../.agents/skills/tizen-image-compatibility/scripts/compat/history.py) · [Impact 源验证](../../../.agents/skills/tizen-image-compatibility/scripts/compat/impact_source.py)

## SR 逐条映射

下表的旧 ID 来自已验收的 903,383 条 Phase 8A 新版报告。新 ID 来自使用同一对输入的本轮复验。原报告未改写。

| 虚拟组件 | 旧 ID | 新 ID | 状态 |
|---|---|---|---|
| `/usr/lib/debug/lib/ld-linux.so.3.debug` | `TC-96dc0f17acde7f1b` | `TC-fc7d8f842d36aacd` | UNKNOWN |
| `/usr/lib/debug/lib/libc.so.6.debug` | `TC-04e5287e26c47aa8` | `TC-da6ccd1c43f27879` | UNKNOWN |
| `/usr/lib/ld-linux.so.3` | `TC-9dd308b2952bf379` | `TC-6947c192f75326a0` | UNKNOWN |
| `/usr/lib/libc.so.6` | `TC-9ffb5a490e203ef4` | `TC-01ee63c51142b348` | UNKNOWN |
| `/usr/lib/libstd-82981c869470ee41.so` | `TC-c2cd3538ebf7bc76` | `TC-a03ca6cb480cc5e4` | UNKNOWN |
| `/usr/lib/rustlib/dylib/libregex.so` | `TC-e34c86dababe6e7e` | `TC-f8704cb634d395fc` | UNKNOWN |
| `/usr/lib/rustlib/dylib/libregex_syntax.so` | `TC-a31e0547c1cf35dd` | `TC-6aa683f07ef3f779` | UNKNOWN |
