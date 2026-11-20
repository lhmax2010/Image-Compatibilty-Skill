# 风险、假设与 PM 决策

## 需要 PM 决定

| 事项 | 推荐选择 | 影响或替代 |
|---|---|---|
| 首次交付范围 | 先批准 `RECORDED` 侧车和数据对账，再批准 root trace 与确认档位 | 把全部 root 的重放和 UI 放在第一切片会混合资源、证据及交互风险 |
| 公共接口权威来源 | 由产品方提供带版本/架构的精确 public 范围表与维护者；缺表默认 UNDETERMINED | “所有导出均产品 API”可供审查但不宜默认；范围分类与 ABI 原状态保持独立 |
| 确认及风险语义 | 确认限明确可比的直接静态契约，所有间接传播上限为潜在；风险用于排定验证优先级 | 将聚合当 CI 或产品门槛需单独政策。缺基线对照时仍保留 candidate 原失败 |
| 混合 C++ runtime 产品政策 | Phase 7B 仅标注边界和建议；由产品明确允许的 C ABI 及跨 Runtime 场景 | 对 libstdc++/libc++ 互换的通用保证需属于 8/9 的另行评审和真实证据 |
| 真实历史数据及性能验收 | 批准一份已校验历史输入与专用参考机，确认 Spark/大图依赖无必要，锁定资源与抽样门槛 | 仅合成验证不足以确认 SSD、索引策略和真实分布。历史输入和本机写入范围分开执行 |
| 运行环境与工具责任 | 产品方提供匹配 ARMv7 sysroot/debug、loader 环境/权限保真记录，后续设备运行另行授权 | 未取得资料时核心静态模式仍运行，确认和建议状态按前提降级 |

## 设计风险与尚未验证的假设

| 风险或假设 | 目前证据及化解方式 |
|---|---|
| 历史索引可独立重建多少角色和上下文 | 已读实际 DDL 与压缩对象入库代码。尚未对历史 898342 Finding 做新摄取。抽样检验旧版本的原 payload、scope 和已选路径保留率。摘要 fallback、缺 trace 将减少确认覆盖 |
| 基线对照可比性 | 当前无 baseline 原生解析。新增 observer 的等价性、settings 映射、原 root mode 与 candidate provider 生命周期需合成 fixture 验证；真实凭据和 AT_SECURE 仍待授权目标证据 |
| 7A 模型剩余边界 | 未知 hwcaps、命名空间、版本 fallback、interposition、IFUNC、非标准 interpreter、孤立 DSO 等不能用 reachability 推定。对歧义路径不授信 |
| Group 键覆盖率与过度合并 | 尚未验证历史数据中可信 equivalence 的占比。用 source group/原 Finding 校对并审查反例，不能因为分组数多而放宽等价前提 |
| 查询和磁盘预算 | 近百万输入下的行数、压缩和索引热度尚未实测。对高 fanout 设边界并报告缺口，不能以丢原 ID 换性能 |
| 恢复与跨源指纹 | 设计依赖稳定输入、同一文件系统的发布边界和可验证原索引来源。用故障注入验证 WAL/索引、checkpoint、发布以及并发读写 |
| 真实 ARMv7 | 历史输入架构和 7A 合成回归可参照。真实 ARMv7 SDK/build flags/RPM/运行 trace、可选 Clang 与 libabigail 集成并非本轮证据 |
| Package 角色口径 | 原关联含 provider/root/consumer 与候选 peer。已观察角色数不代表消费者确切数量。要求 per-role、distinct 与不完整状态分别核对 |

Phase 8 为编译与布局验证补输入。Phase 9 为设备、真实 loader、RTTI/EH/TLS/cancel 验证。Phase 10 才定义跨 run 变化和产品门槛，Phase 11 负责固定环境、保留和 CI 工程化。7B 的核心设计允许无 SDK、无设备、无 Rootfs 执行。

状态应为 **DESIGN READY FOR REVIEW** 或 **DESIGN INCOMPLETE**。PM 独立评审决定是否授权上述切片和参考机验收。
