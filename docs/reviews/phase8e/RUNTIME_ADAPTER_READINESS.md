# Runtime Adapter 准备情况

**协议和错误处理的合成验证通过。真实执行未准入。** 本轮使用仓库既有合成回执、授权门禁、行为差异、超时和 Podman 控制面测试。该测试的模拟清理证明控制面尝试发出清理操作，目标端进程回收、权限和证据采集仍待实测。 [现有接口](../../../.agents/skills/tizen-image-compatibility/references/execution.md) · [冻结清单](ARTIFACT_MANIFEST.json)

## 计划入口

操作员提供两套已批准的环境映射。先核对固定环境 ID、实际快照、设备/Guest 身份、公钥或本地隔离绑定、允许运行路径和目标 UID。只接受清单中对应组合的产物 SHA256。部署前检查本地副本，部署后让目标侧独立重新计算 SHA256，并确认没有 setuid/setgid、File Capability 或其他特权启动请求。

已有 run_matrix 在 full/runtime 模式中会调度构建，因此冻结方案下后续执行需走独立的已审核入口。计划把只读冻结副本按原字节放入新的报告 build 目录，验证 SHA256 后通过既有 execute_target / run_target 入口，使用真实隔离 Adapter 并严格应用授权门禁、已校验原生参照和原有比较规则。任何新构建必须登记为另一个待验收身份。 [实现入口与路径判定](../../../.agents/skills/tizen-image-compatibility/scripts/compat/testing.py)

## 回执、错误和清理

| 阶段 | 应记录的事实 |
| --- | --- |
| 身份与部署 | Manifest 摘要、artifact SHA256、环境 ID、部署位置和目标处实测摘要。部署失败单独记阶段，缺回执、ID/哈希不符保留 UNKNOWN。 |
| 启动和结果 | 目标进程标识和预期普通用户、开始/结束、stdout/stderr 原始字节及各自哈希、实际退出或信号。对于成功采集的执行返回 schema、environment_id、binary_sha256、deployment、execution、returncode、stdout、stderr。外层退出 0 需要配套有效回执。 |
| 超时与中断 | 目标侧看门狗、同次运行所有进程的会话或专用进程组、限时终止升级、确认无残留。目标无法复位时标记不可重用，保留中断和清理日志。宿主超时不能替代目标端清理证据。 |
| 基准与差异 | 原生参考成功后，对相同 bytes 比较目标真实退出码、stdout/stderr。实际行为不同才给既有兼容差异分类。124–127 等用现有基础设施门槛保留 UNKNOWN。 |
| Evidence | 主机与目标分别记录阶段信息、完整回执、日志和哈希。只支持受控工作区输出。读取 stdout 超界、协议损坏、无证据或远端断开保留 UNKNOWN。 |

使用 `tizen-compat-runner/v1` 现有回执契约。本轮没有添加生产 Adapter，也没有创建设备执行回执。

## 既有合成回执复核

确认有效 v1 回执、错误环境或摘要、部署失败、空回执、直接目标调用拒绝、未授权与维度排除阻断、原生参考失败阻断、候选自身参照、行为差异、重复性、输出上限和超时。真实 Adapter 还需在获准目标上补充部署后哈希、真实进程退出、可重复 stdout/stderr、断线/超时清理和 write-scope 五类证据。 [回执与原生参考用例](../../../.agents/skills/tizen-image-compatibility/tests/test_correctness.py) · [授权和行为用例](../../../.agents/skills/tizen-image-compatibility/tests/test_execution.py) · [清理和上限用例](../../../.agents/skills/tizen-image-compatibility/tests/test_final_release.py)
