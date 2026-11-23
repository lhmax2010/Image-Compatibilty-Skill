# 临时 ARM 测试环境验收

**BLOCKED。** 当前无法通过本机的非交互 sudo 提权检查。任务只完成了创建前记录、冻结输入核查、脚本实现和可在当前权限下运行的验证。

| 事项 | 实际结论 |
| --- | --- |
| 专用账号和组 | 未创建。实际 setup 先在 sudo 凭据检查处退出 3。 |
| 独立 cgroup | 未配置或启动，无有效专用 cgroup。 |
| 资源限制 | NOT_VERIFIED。已有明确的实测取证路径。 |
| 宿主隔离 | NOT_VERIFIED。静态 x86-64 fixture 编译和 ELF 核对通过，未实际启动 fixture。 |
| 进程回收 | NOT_VERIFIED。无本轮专用服务和真实 cgroup 过渡证据。 |
| 可撤销性 | 演练和安全边界通过测试，真实系统撤销仍待实测。 |
| 实际撤销 | 已运行默认和显式 dry-run，输出一致。未运行 `--apply`，没有系统对象待撤销。 |
| ARM Step A | 不具备申请条件。没有执行 ARM 程序，正式 SR Runtime 仍为 0/8。 |

主要交付为 [setup](../../../.agents/skills/tizen-image-compatibility/scripts/arm_smoke_admission/setup.sh)、[cleanup](../../../.agents/skills/tizen-image-compatibility/scripts/arm_smoke_admission/cleanup.sh)、[宿主预检观察器](../../../.agents/skills/tizen-image-compatibility/scripts/arm_smoke_admission/preflight.py) 和 [隔离 fixture](../../../.agents/skills/tizen-image-compatibility/scripts/arm_smoke_admission/host_probe.c)。本地状态、日志及续接见 [环境搭建](ENVIRONMENT_SETUP.md)。独立判定见 [资源限制](RESOURCE_LIMIT_VALIDATION.md)、[宿主隔离](HOST_ISOLATION_RESULTS.md)、[回收验证](PROCESS_CLEANUP_RESULTS.md)、[撤销验证](ROLLBACK_VALIDATION.md) 和 [ARM 审批状态](ARM_STEP_A_APPROVAL.md)。

既有 ABI、Linking、Runtime 判定与 SQLite 门槛沿用现有实现。SHA256 身份经独立读回，原始冻结产物、镜像、SDK 与历史报告保存。

## 全量回归

```bash
python3 -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v
git diff --check
```

全量回归 **278 项，273 PASS、5 SKIP、0 FAIL**，退出 0。新增 15 项覆盖同名冲突、重复 setup、重启后旧快照、缺 sudo、部分创建记录、未归属 cgroup、目录链接和挂载、残留进程及只删除登记对象。五项 SKIP 与基线一致，涉及未启用的 libabigail 和 Clang/ARM 工具链条件。测试耗时 111.911 秒，峰值 RSS 101,420 KiB。日志 SHA256 为 `cd252ffdcb0cafebf5ba4fbe0172ba0bf2d7def69ba344f6748c1ddd10a18485`。
