# 正式 Runtime 清理门禁

基线宿主负例用独立 PID 检查确认组外合成子进程仍活着。Controller 的格式正确的 Cleanup 回执被接受，`target_process_cleanup_status` 为 `NOT_VERIFIED`，然而 CLI 退出 0 且行为被提升为 `COMPATIBLE`。修复后相同宿主复现仍观测到组外合成子进程活跃且回执已接受，CLI 退出 3，行为观察为 SUCCESS，正式状态为 UNKNOWN，后续启动 0 次。修复后日志 SHA256 为 `559aabc349be6353a68e6f6819459818ea558ef7b479dde49cac5dfd3ffb1483`。基线复现日志 SHA256 为 `9dbb68674c91e45219513c1faeabf61a2df82a0af6679c9b978f780076e2a124`。

`compat/core.py` 已能限定和验证调用器的本地进程组。该 Linux 进程组的回收权限与观察范围不覆盖脱离组的目标进程或远端进程。修复位于冻结 Runtime 判定处。 [进程组实现](../../../.agents/skills/tizen-image-compatibility/scripts/compat/core.py) · [冻结入口](../../../.agents/skills/tizen-image-compatibility/scripts/frozen_runtime.py)

| 字段 | 证据与门禁 |
| --- | --- |
| `stages.behavior_status` | 已收到的执行观察和预期对比，可独立为 `SUCCESS` 或 `MISMATCH`。 |
| `cleanup_receipt_status` | Controller v1 声明通过已存在的运行 ID、计划 ID、环境身份和格式检查时为 `ACCEPTED`。Controller 的额外目标证明声称只保存在原始证据。 |
| `run_local_process_group_status`、`cleanup_local_process_group_status` | 宿主的本地组回收结果，各自必须为 `VERIFIED`。 |
| `target_process_cleanup_status` | 只能由独立的目标侧退出证据验证器给出。本版没有接入可信证明源，保持 `NOT_VERIFIED`。 |
| `cleanup_status`、`verification_status`、`status` | 总清理必须同时有回执、本地两组和目标退出证明。缺目标证据时，三者分别为 `UNKNOWN`、`NOT_VERIFIED`、`UNKNOWN`，CLI 退出 3。后续用例保持 `NOT_EXECUTED`，当前原生观察不会作为跨侧参考。中断仍退出 130。 |

计划模式退出 0，所有用例标记 `NOT_EXECUTED`。在已授权的正式执行模式下，本版可保留第一个原生观察，但因暂无独立目标证明源而停止。旧 schema 标识与原始快照保留。消费当前报告时，在行为之外还需读取 `verification_status` 和目标清理字段。

实际 CLI 的宿主合成负例覆盖组外遗留子进程、格式正确但自称有证明的回执、正常回执缺目标证明、cleanup 超时和断线。测试读回了本地证据并核对后续未启动。既有错误产物 SHA256、错误环境、陈旧回执和原生优先测试继续运行。测试代码只在进程内模拟独立验证成功以复核后续矩阵行为，生产入口和配置无此开关。 [定向回归](../../../.agents/skills/tizen-image-compatibility/tests/test_frozen_runtime.py)

## QEMU User 的本机退出证明

1. 在新建且仅供这次尝试使用的授权 cgroup 外放置独立观察员。固定 cgroup v2 挂载与目录的设备号、inode、尝试 ID、宿主 boot ID。启动前观测空组。子进程启动后记录 `populated 1`、实际 QEMU PID 和进程启动时间、所属 cgroup、私有 PID namespace inode 以及 namespace init 的宿主 PID 身份。确认任务无权迁移至组外，观察器覆盖子 cgroup。
2. 封闭本次尝试的新增任务入口。在正常退出、超时或中断情况下等待 namespace init 和 QEMU 的原进程身份退出。优先使用 pidfd，或结合宿主 PID 和 starttime，避免把 PID 重用误判为残留或退出。超时后由管理员批准的外层监督器回收控制组，回收触发和异常结果单列。
3. 观察员在组未移除前验证同一 cgroup 的 `cgroup.events populated 0`，确认无剩余任务。保存内核观察值、时间、退出、启动及回收证据。无法绑定同一组、组提前消失、看不到运行中占用或视野不完整时保持 `NOT_VERIFIED`。该证据只用于 `QEMU_USER_SMOKE`。 [Linux cgroup v2](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)

## 未来正式设备的回收回执

建议由预先注册且与 Controller 启动通道隔离的目标 Supervisor 负责。Supervisor 的身份或验证公钥应通过独立路径固定，仅凭 Controller 标准输出、JSON 字段或网络代理转发无法增加信任。Supervisor 应从执行 namespace、cgroup、独立进程租约或等价的内核可观察边界获得证据。

- 回执包含 schema 版本、目标/镜像身份和 boot ID、计划 ID、唯一尝试 ID、挑战 nonce、制品及部署摘要、Supervisor 身份、单次租约、实际执行边界身份、退出观察、停止后剩余运行任务数和原始证据摘要。将字段绑定至 Supervisor 签名与指定验证方。
- 校验签名/可信受认证通道、请求与返回绑定、时间或单调计数和 nonce 未重放。验证目标进程曾进入受控边界，暂停新增任务后直接检查所有相关成员退出。附上超时、断线回收和清理后的结果。无法证明退出、签名或边界不完整、存在残留、无目标反馈一律保持 `NOT_VERIFIED`。
- 标准 Controller 清理回执维持兼容，独立证明采用单独 schema 与来源。正式部署需要真实目标及双通道验证，当前仅有协议设计和宿主测试。产品状态不因 QEMU User 冒烟变化。
