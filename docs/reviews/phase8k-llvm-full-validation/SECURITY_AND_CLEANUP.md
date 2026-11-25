# 设备授权、异常与回收

本轮使用已有 SDB 非 root 会话和单一明确授权目标。执行采用用户级 systemd 临时 scope、私有执行目录、哈希固定的输入、空白环境、10 秒 scope 上限、1 秒停止升级、control-group 回收和有界捕获。伴随 DSO 与 executable 逐项验证。超时尝试的 stdout/stderr 实测为空，完整 Loader 日志仍已保存。

Adapter 使用单独 SDB 请求核对运行中的 PID/starttime、session、cgroup、进程身份，再取得结束后和目录移除后的状态。最终额外只读复核使用同一 boot 验证了 44 次尝试的 scope 与目录均已消失或处于 inactive，包含 42 次实际启动（40 次退出、2 次受控超时）和 2 次未放行尝试。原始逐项记录保存在本地 `cleanup-audit.json`。复核耗时 2.99 秒。

| 边界 | 证据 |
| --- | --- |
| 正常、非零、缺库、缺版本、超时 | 真机程序与原始证据 |
| 私有 DSO 加载策略拒绝 | 真实拒绝与独立 scope/目录回收 |
| 观察过期及 scope 在 grant 前到期 | 真实停止并安全收尾；后续重新准入后重测 |
| 摘要错误、输出上限、错误设备/Profile、陈旧或缺失回执、遗留进程、SDB 断线与中断处理 | 自动化宿主合成反例 |

同设备独立 SDB 观察支持本轮探针的受控清理结论。同时保留正式 `target_process_cleanup_status=NOT_VERIFIED`。其信任含义见 [Phase 8J 退出验证](../phase8j/TARGET_EXIT_VERIFICATION.md)。
