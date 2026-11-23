# 真实 SR VD → LLVM Finding 对账

基准是 Phase 8A Final 的同向报告。复验使用同一对 tizen-headless-armv7l 归一化 TAR 和相同配置，两侧输入只读，模式 static，排除 performance。输入 TAR 的采集前后 SHA256 一致。历史报告保留。 [原始身份和流程](../phase8a-final/SR_REVALIDATION.md) · [发布输入 SHA256](../phase8a/SR_EVIDENCE_EXCERPTS.json)

| 指标 | Phase 8A Final | Phase 8C |
| --- | ---: | ---: |
| 全部 Finding | 903,383 | 903,377 |
| INCOMPATIBLE | 11,490 | 11,490 |
| UNKNOWN | 868,075 | 868,069 |
| COMPATIBLE | 23,486 | 23,486 |
| IDENTICAL | 332 | 332 |
| Linking UNKNOWN | 860,300 | 860,294 |
| ABI 完整覆盖 | 1,866/4,108（45.42%） | 1,866/4,108（45.42%） |
| API 完整覆盖 | 0/1（0%） | 0/1（0%） |
| Linking 完整覆盖 | 0/2,054（0%） | 0/2,052（0%） |
| VD / LLVM 已安装 RPM | 719 / 736 | 719 / 736 |

两个分离调试对象各从基线 Linking 覆盖的适用分母移出，继续作为 ELF、DWARF 及包证据采集。

| 历史 ID | 对象 | 去向 |
| --- | --- | --- |
| TC-4ab4968318d673cf | libc.so.6.debug | 从 candidate 闭包去除虚假的解释器查询 |
| TC-f4217cd52a2e94b3 | libc.so.6.debug | 从 baseline-on-candidate 闭包去除虚假的解释器查询 |
| TC-50e5b0965a09dda9 | libc.so.6.debug | 从 candidate 闭包去除调试对象的搜索上下文 |
| TC-68b576750fe5a725 | libc.so.6.debug | 从 baseline-on-candidate 闭包去除调试对象的搜索上下文 |
| TC-8f33b19191552cb2 | ld-linux.so.3.debug | 从 candidate 闭包去除调试对象的搜索上下文 |
| TC-22e484ab078b65b5 | ld-linux.so.3.debug | 从 baseline-on-candidate 闭包去除调试对象的搜索上下文 |

旧行的状态均为 UNKNOWN。新报告通过 Manifest 的 DEBUG_ONLY、覆盖不适用记录和原始 readelf Evidence 保留原因。 [分类判据](DEBUG_ELF_CLASSIFICATION.md)

复验的 CLI 退出码为 1，兼容性门禁 FAIL，采集执行 PARTIAL。两侧均保留 toybox ELF 不完整诊断，RPM 采集 COMPLETE。复验耗时 4 分 21.50 秒，峰值 RSS 3,868,380 KiB，原报告用只读 Rootfs backing 对账并压缩输出，记录为 3 分 51.95 秒、3,869,716 KiB。两次输入一致，采集和报告输出方式不同，耗时记录适用于各次执行。

```bash
skill=.agents/skills/tizen-image-compatibility/scripts
python3 "$skill/tizen_compat.py" --baseline "$VD_TAR" \
  --candidate "$LLVM_TAR" --config "$CONFIG" --mode static --exclude performance \
  --output "$NEW_REPORT"
```

归一化 TAR SHA256 为 VD `cb34620e5d21b3bba1e5276f987c5b0026ed064bdf6e16e0d60df0b272bb921d`，LLVM `8ed19e697d14ecef98cdfb6a4688571d9674eda815e955225a66cf4979ec1d35`。配置设定两个 worker，并为两侧明确保留 Ramdisk、xattr、ACL、Smack、File Capability 和硬链接证据缺口。

| Linking UNKNOWN 原因 | Phase 8A Final | Phase 8C |
| --- | ---: | ---: |
| unknown_symbol_scope | 442,049 | 442,049 |
| unknown_symbol_semantics | 314,185 | 314,185 |
| unknown_version_requirement | 57,107 | 57,107 |
| unknown_search_environment | 43,789 | 43,785 |
| unknown_loader_abi | 1,486 | 1,486 |
| 其他既有静态检查 | 1,062 | 1,062 |
| unknown_loader_feature | 618 | 618 |
| unknown_collection | 2 | 2 |
| missing_provider | 2 | 0 |

独立流式复核比较了所有 Finding 的 ID 与完整规范化 JSON 载荷，按行对照 CSV，并把 HTML 预览的 1,000 个 ID 与机器报告顺序对齐。排除上述六条后，其余 903,377 个 ID、状态和载荷一致，无新增 Finding，未分配 Finding 保持 10,258 条。两版均有 4,086 个 Finding Evidence 文件引用，对应文件 SHA256 已校验。配置 SHA256 为 `485e8042d09f4a39e14fb13bebde2ca2bb1e4e85265bd65d7094b5e97ad77c45`。

基线包的完整 CSV 对账中，唯一一项维度状态变化是 tizen-debug 的 Linking 从 UNKNOWN 变为 NOT_APPLICABLE，移除六个对应引用。其 ABI、API、总体状态和验证状态均保持。未分配项及 Provider/Consumer 包关联保留。

最终复验包含 GNU_STACK 十进制对齐字段修复，重新只读处理同一对归档，并把体积最大的 JSON/CSV 报告保存为 gzip。最终采集和报告生成用时 3 分 27.24 秒，峰值 RSS 3,869,200 KiB。最终原始 JSON 解压 SHA256 为 `e56b9aff1f0c8272d303e9c510469244ed94a75f27676cf5abf17ffa50199ddc`。最终 Findings CSV、Package CSV 和 HTML 与已独立对账的同阶段原始输出按字节一致。最终报告的 4,832 份 Evidence 文件均按文件名 SHA256 核对，包含两种报告使用的 4,086 份 Finding 引用证据。

两次 Phase 8C JSON 的序列化差异仅来自 RPM provenance 中的临时数据库副本和解包路径。首个差异在包来源字段，差异之前的 3,032,440,040 字节完全一致。剩余部分只规范化上述两类路径，各出现 2,191 次，整段 SHA256 均为 `d36f7fef804d618225a6cc2e3947c007ecd05d21c5b061826c45d1dbc5e74ffd`。最终文件保留原始 provenance。
