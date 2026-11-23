# 进程回收与回执边界

**本地受控回收 VERIFIED。目标进程退出 NOT_VERIFIED。**

Phase 8F 原代码按 `drain_bounded` 是否报错决定是否 killpg。子进程若提前关闭继承的 stdout/stderr，父 Controller 退出后管道可正常结束。原代码会回收父进程并跳过结束进程组。基线上分别以父 Controller 退出 0 和 19 复现，两个子进程在 harness 返回之后仍处于 R。修复后重复执行，两个子进程已退出，父进程退出 0 和 19 均被保留。基线及修复后本地日志 SHA256 分别为 `2a04aa845222cc7d1cce1514fb044fcbcf9aa451610884d3145fdf68dc948213`、`42edb0894ccc972713de2cb4fe73fdf9bf4b57d0c26ece11cfadb4be26bfe1fe`。

有界启动为 Controller 建立新会话和进程组。正常读取后用 `waitid(WNOWAIT)` 观察领头进程退出，保持该 PID 尚未回收。无论 Controller 成功、异常还是输出或时间超限，均向该进程组发 SIGKILL，检查 `/proc` 是否仍有活成员，再回收直接子进程。僵尸状态只作为已终止观察，组外进程超出这个验证范围。启动交接和本地回收期间延后处理默认 SIGINT，确保取得进程句柄和保存已收到的有界字节。不能验证本地回收时记录 `NOT_VERIFIED`。 [本地收集实现](../../../.agents/skills/tizen-image-compatibility/scripts/compat/core.py)

| 受控场景 | 复核证据 |
| --- | --- |
| Controller 正常结束，子进程关闭管道后继续运行 | 返回码 0，独立读取 PID 状态确认子进程已退出。 |
| Controller 被 SIGTERM 中止 | 保留返回码 -15，组内子进程已退出。 |
| 超时或运行中 SIGINT | 错误类型分开记录，保留已写入的证据，组内子进程已退出。 |
| stdout 或 stderr 突发超量 | 分别测试两个流，达到总上限即中止，原始证据合计恰为测试上限 4,096 B，组内子进程已退出。 |
| 启动交接中、宿主组回收中或 cleanup 命令期间中断 | 受控注入 SIGINT，检查获取的启动句柄、实际进程状态和已有日志。cleanup 命令中断让当前矩阵停止。 |
| cleanup 回执已接受、子进程在另一会话 | 合成反例验证本地进程组状态与目标退出状态分开。独立检查时该合成进程仍在运行，报告保持目标清理 `NOT_VERIFIED`。测试随后清理自己的合成进程。 |

冻结 CLI 在 `runtime.json` 分别输出 `run_local_process_group_status`、`cleanup_local_process_group_status`、`cleanup_receipt_status` 和 `target_process_cleanup_status`。旧 `cleanup_status` 继续用于门禁，仅在本地两组回收确认且回执有效时为成功。本接口的 JSON 回执本身无法确认远端进程退出，目标字段保持 `NOT_VERIFIED`。 [冻结回执实现](../../../.agents/skills/tizen-image-compatibility/scripts/frozen_runtime.py) · [定向回归](../../../.agents/skills/tizen-image-compatibility/tests/test_frozen_runtime.py)

Bubblewrap 另用静态 x86-64 工具创建私有 PID namespace 中的不同会话子进程。独立从宿主 `/proc` 确认它此前活跃，检查正常结束和实际 2 秒超时后均无活成员。日志 SHA256 为 `ae7e843eccff5359ba40311854f97b6cb8890bc150d2a72ce2ce68669a5d34f5`。这项实验只验证当前环境的宿主合成回收。实际 ARM target、远端 Controller 和未来专用账号/cgroup 仍需独立验收。 [目标准入](QEMU_EXECUTION_GATES.md)
