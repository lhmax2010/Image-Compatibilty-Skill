# 冻结 ARMv7 产物执行入口

新增独立 `frozen_runtime.py`，复用 `execute_target()` 和 `tizen-compat-runner/v1`。Phase 8E 发布清单的 10 个实体文件均通过本轮大小及完整 SHA256 校验。计划涵盖原定四个基础产物和八个目标组合。执行与编译入口分离。 [实现](../../../.agents/skills/tizen-image-compatibility/scripts/frozen_runtime.py) · [冻结清单](../phase8e/ARTIFACT_MANIFEST.json) · [原生与跨镜像安排](../phase8e/FOUR_QUADRANT_EXECUTION_PLAN.md)

## 默认计划模式

`ARTIFACT_BUNDLE` 指发布清单所列的原始产物目录。输入摘要来自发布记录。报告目录需为新目录并与输入分离。

```bash
python3 .agents/skills/tizen-image-compatibility/scripts/frozen_runtime.py \
  --manifest docs/reviews/phase8e/ARTIFACT_MANIFEST.json \
  --manifest-sha256 fe59f50a2501d0c165b5e7a3b037e969b418e06bbb8951e917412a4a06713c32 \
  --bundle "$ARTIFACT_BUNDLE" --output "$NEW_RUNTIME_REPORT"
```

真实冻结输入的实际 dry-run 得到 8 条 `NOT_EXECUTED`。计划未绑定环境时，`plan_id` 为空。旧 `ET-…` 仅保留为历史证明引用。新 `FR-…` 将清单、产物摘要、目的环境、原生环境和 controller 摘要绑定在一起。更换环境身份会改变依赖该环境的计划 ID。

## 获批后接入

未来执行需要 `--execute --enrollment operator-local.json`，且配置中两个授权开关都是 JSON `true`。操作员在授权前只需生成计划。路径和摘要由操作员从准入证据填写。

```json
{
  "scope": "SR_RUNTIME",
  "enabled": false,
  "authorized": false,
  "timeout_seconds": 30,
  "controller": "/approved/host-controller",
  "controller_sha256": "<64 lowercase hex>",
  "targets": {
    "vd": {
      "id": "<authorized VD environment ID>",
      "target_identity_sha256": "<sha256 of enrolled target identity record>",
      "image_sha256": "<VD released archive SHA256>",
      "rootfs": "/approved/reference/vd"
    },
    "llvm": {
      "id": "<authorized LLVM environment ID>",
      "target_identity_sha256": "<sha256 of enrolled target identity record>",
      "image_sha256": "<LLVM released archive SHA256>",
      "rootfs": "/approved/reference/llvm"
    }
  }
}
```

controller 为操作员提供的可信宿主工具。入口检查其路径、摘要和执行权限，拒绝直接用 ARM/ARM64 ELF 或输入、产物树中的程序当 controller。工具运行前必须在目标侧独立核对实时身份记录和镜像摘要。配置中的 `rootfs` 仅为本地参考路径。 [目标准入](TARGET_ENVIRONMENT_READINESS.md)

- `run --environment-id … --target-identity-sha256 … --image-sha256 … --run-id … --plan-id … --artifact … --sha256 … --timeout-seconds …` 接受新报告中固定 SHA256 的只读字节副本。每次尝试使用新的 `run_id`。controller 应在目标专用目录部署，复核部署后的摘要，只执行无额外 argv 的获批探针，再记录目标退出码、stdout、stderr 和实际环境。正常 v1 JSON 回执增加 `target_identity_sha256`、`plan_id` 和 `run_id`。受信的失败回执可使用 `deployment: failed` 或 `execution: failed|timeout|disconnected`。原始回执及外层工具状态一并保留。 [v1 回执](../../../.agents/skills/tizen-image-compatibility/references/execution.md)
- `cleanup --environment-id … --target-identity-sha256 … --image-sha256 … --run-id … --plan-id …` 在每次尝试的 finally 调用。应按 token 回收目标进程组和临时部署，并保持幂等。确认后退出 0，返回包含 `schema: tizen-compat-runner-cleanup/v1`、`cleanup: ok`、`environment_id`、`target_identity_sha256`、`plan_id` 和 `run_id` 的 JSON。未确认清理时停止后续用例。
- 宿主有界收集在超时或 SIGINT 后杀死本地进程组并保留已写入的输出。目标 controller 仍须建立独立超时租约和断线回收，覆盖宿主 SIGKILL、网络断线和无法收到 cleanup 的情形。 [有界收集实现](../../../.agents/skills/tizen-image-compatibility/scripts/compat/core.py)
- `runtime.json` 分别记录冻结构建证明、部署、执行、行为和清理。先跑四个原生组合，逐产物只有成功的原生实际回执与准确预期才能建立参考。跨镜像观察须与该原生结果对比。未证实运行或保留基础设施退出码留为 `UNKNOWN`，缺原生参考的跨镜像项保留 `NOT_EXECUTED`。跨镜像有效回执中的真实行为差异为 `INCOMPATIBLE`。退出码 0 表示生成计划或所有运行匹配，1 表示完整运行且观察到不匹配，2 是输入错误，3 是执行证据不完整，130 是中断。查看报告中的 `execution_requested` 及各阶段状态。
- 这个入口接受 `SR_RUNTIME` 注册。QEMU User 冒烟独立于正式矩阵。已有矩阵、静态判断和报告 schema 继续沿用原入口。

新增 7 项自动化测试使用宿主合成 controller，fixture 字节从未作为程序执行。用例覆盖默认关闭、授权、篡改及越界输入、镜像及构建身份、计划 ID、原生优先、错身份/错摘要/陈旧回执、部署和执行失败、断线、行为差异、保留退出码、清理拒绝、进程组超时和中断及原始证据。目标 controller 和真实远端回收仍待环境准入后的验证。 [回归](../../../.agents/skills/tizen-image-compatibility/tests/test_frozen_runtime.py)
