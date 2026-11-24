# 实际设备验证

本轮复核上一轮四份证据及本地哈希清单，原四个冻结程序的 SHA256 均保持。新 Adapter 在同一授权 LLVM headed ARMv7l 设备上完成本地计划和只读准入。仅再次运行 **Clang C（llvm-A-C）一次**，其余三个按上一轮实测保留。

| 观察项 | 实测值 |
| --- | --- |
| 目标 Profile | `tizen-unified-toolchain_20261120.082536_tizen-headed-armv7l`，运行期 boot 与发布身份已绑定。 |
| 部署后 SHA256 | `e4987d1628770f2dfa5f6b13d95fc1ed3cdd235651d3ca26e3812aea41f01606`，与本地一致。 |
| 退出与输出 | 退出 0，stdout `536768647\n`，stderr 0 B。 |
| 实际 Loader/Provider | `/usr/lib/ld-linux.so.3`、`/usr/lib/libc.so.6`、`/usr/lib/libgcc_s.so.1` 的实际摘要均与准入钉住值一致，诊断含 8 条版本检查。 |
| 清理 | 独立 SDB 观察实际 PID、starttime 与 cgroup，退出后原成员与 cgroup 不再存在，临时目录消失。本轮观察清理 VERIFIED。 |
| 正式结果 | 正式目标退出和原生参考 NOT_VERIFIED，跨镜像 UNKNOWN，原 headless 矩阵 0/8。 |

首次和修正中的准入尝试均在 ARM ELF 放行前停止。诊断包括旧 SDB 请求过长、长度预算拒绝及 systemd 属性折行。为应对 scope 的成员接口可以被同 UID 修改，报告保留实测事实。失败尝试创建的空目录已定向移除，等待中的 scope 到其 10 秒上限后回收，随后仅清除该次已验证无任务的临时失败记录。

本地 `.local-backups/phase8j/live-release/runtime.json` SHA256 为 `ca81fee6463f65fc590200507b8a6a2516b249af87e047c8767eed6f861abf44`。同目录 stdout SHA256 为 `034c45d1eadbea52df3b5195139d22052872b9208c4f58fcc8fb54592d2abaf1`，实际 Loader 日志 SHA256 为 `c9486cec0d676d8640f9a17e01305ee0c837fcedad6beea7acd55325dee6c8f1`。具体目标、账号和路径、原始日志及二进制留在本地。后续小幅错误日志和输入检查调整通过宿主测试，最终版另重跑了只读准入。 [上一轮结果](../real-sr-runtime/HEADED_RUNTIME_RESULTS.md)
