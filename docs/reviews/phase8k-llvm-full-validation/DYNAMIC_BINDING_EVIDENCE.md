# 真实动态链接证据

| 用例 | 实际证据 | 结论 |
| --- | --- | --- |
| version-present | 消费者 readelf Version Needs 包含 `SR_PROBE_1`。Loader 对试验 DSO 检查该版本，并记录主程序将 `sr_contract` 绑定到独立冻结的 `libsr_probe.so [SR_PROBE_1]`。stdout 含 `versioned: SR_PROBE_1 ok` 和 DSO 析构输出 | 成功 |
| version-missing-symbol | 替换件保留 `SR_PROBE_1` 版本定义但不导出所需函数。真实 stderr 含 `undefined symbol: sr_contract, version SR_PROBE_1` | 预期启动拒绝，127 |
| version-missing-node | 替换件仅提供另一个版本。真实 stderr 含 `version 'SR_PROBE_1' not found`，保留 Loader 原文 | 预期启动拒绝，1 |
| library-missing | 同一消费者缺少私有 Provider。Loader 明确报 `cannot open shared object file` | 预期启动拒绝，127 |
| dlopen | Loader 原文为 `glibc: dlopen blocked for object … attempting to load './libsr_probe.so'`；未观察到私有库构造、两版本动态调用或正常 dlclose | 当前镜像策略阻断 |
| resident-provider | 对已装载的 libc 通过 `RTLD_NOLOAD` 获取句柄。真实行为观察包括 dlsym、dlvsym、缺符号与 dlclose。Loader 记录 `getpid` 无版本和 `GLIBC_2.4` 两条绑定 | 成功，范围为已装载系统库 |

启动正例的 DSO SHA256 为 `5b219a8695c9613b99e31f11d3d9878f326b33b1b851721545d8e465fc3f0753`。其导出同时包含 `sr_contract@SR_PROBE_1` 与默认 `sr_contract@@SR_PROBE_2`，主消费者实际绑定前者。原始 Loader 日志、readelf 输出和回执保存在本地。正常的启动校验、实际绑定、静态候选和可能尚未发生的 Lazy Binding 仍分别记录。专项目标的 `LD_DEBUG=bindings` 有输出上限。历史 `860,294` 条 Linking UNKNOWN 不因这些观测改变。
