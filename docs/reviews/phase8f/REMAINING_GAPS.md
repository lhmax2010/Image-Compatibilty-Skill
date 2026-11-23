# Phase 8F 剩余缺口

| 工作 | 当前状态 | 恢复条件 |
| --- | --- | --- |
| Phase 8E 磁盘差额的源头分摊 | UNKNOWN | 新运行时同步采集具名 inode、已打开匿名文件、卷级增减及阶段时间。历史样本无法补出缺失证据。 |
| 真实 SQLite 全量验收 | NOT VERIFIED | 提供至少 25 GiB 稳定可用、明确授权的卷，再保留资源门禁运行，并独立核对全部数据和只读查询。 |
| 冻结入口接真实 adapter | 仅合成验证通过 | 给两侧真实目标登记镜像身份与 controller。验证目标侧可信回执、租约、断线和回收。 |
| QEMU User 冒烟 | NOT_EXECUTED | 取得单独目标执行授权，准备专用低权限账号和同侧库投影，在实际参数与边界下先通过宿主预检。 |
| 正式 SR 四象限 | 0/8 NOT_EXECUTED | 获批匹配设备或 Guest，具备 Kernel/DTB、启动配置、CPU、Loader、挂载和运行证据。 |
| libc++ 标准库迁移 | 指定文件的静态依赖检查通过，Runtime 未执行 | 单独部署两份同快照库，观测实际 Provider、异常/Unwind 和确定性行为。 |

现有静态 Linking UNKNOWN 沿用 Phase 8C 报告。真实执行前缺少的加载作用域、动态 Namespace、安全上下文及内核证据持续为未验证。 [静态对账](../phase8c/COVERAGE_BEFORE_AFTER.md) · [目标准入](TARGET_ENVIRONMENT_READINESS.md)
