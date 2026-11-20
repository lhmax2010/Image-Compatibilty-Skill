# 安全验收

- 镜像采集、历史和影响分析只读取输入。正常流程不修改 RPM 数据库、Rootfs、原报告或原 Evidence。镜像程序不由宿主直接执行。
- Runtime 要求显式配置、授权及目标身份。同一产物和伴随 DSO 必须有实际哈希回执。目标能力缺失、超时及身份不匹配保留 UNKNOWN。
- Podman 具备 rootless、固定本地镜像、网络禁用、只读根、本机私有挂载、capability drop、no-new-privileges、限资源和独立容器清理。宿主和容器仍共享内核，完整设备测试依赖单独隔离的 VM 或专用设备。 [Podman run](https://docs.podman.io/en/latest/markdown/podman-run.1.html)
- Web 绑定 loopback，使用精确资产名、参数化分页、文本渲染和同源 CSP。绝对路径和越界 Evidence 被拒绝。测试还验证公式转义、过量输出限制和未发布索引拒绝挂载。

调用者应信任其 SDK、Podman controller、guest 验证工具和外部适配器。任意外部脚本的回执不是远程证明。此模型支持隔离试验，不承诺抵御具有宿主控制权的恶意操作者。
