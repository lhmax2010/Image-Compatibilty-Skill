# SDK 与目标运行验证

四象限分别记录 `compile_status`、`link_status`、`deployment_status`、`execution_status` 和 `behavior_status`。编译和链接分开执行，运行前先核对产物 ELF 目标、产物及伴随 DSO 哈希。期望测试记录编译器、SDK、来源技术栈、目标身份及重试配置。自身参考没有成功时，其他目标上的单次成功不能给该探针提供 PASS。

真实本机 GCC 控制用例成功编译、链接因刻意缺少库而失败，执行没有发生。可信仓库源码在本机完成了 C 行为、C++ DSO 和 forced unwind 测试。替换 DSO 中的异常消息后，跨库探针按预期以 14 退出。无镜像程序在本机被执行。

Podman 支持本地镜像 ID、生效的 rootless 检查、只读绑定、退出码、受限 stdout/stderr 和临时容器清理。单元测试以明确标记的替代回执注入 Controller，验证完整命令和身份约束。真实 Podman 及隔离 Tizen 设备在本轮不可用。按时限和输出上限终止以及重复不一致分支均有测试。 [Podman run](https://docs.podman.io/en/latest/markdown/podman-run.1.html)

发现的现有 Tizen ARM 构建根中，GCC 程序自身属于 ARM EABI5，无法作为此 x86_64 主机的已配置 SDK driver 使用。两套匹配的宿主交叉编译器、SDK/sysroots 和经授权的运行环境仍缺。没有使用主机 SDK 代替真实 ARM 验证。真实 SDK/设备状态为 **NOT VERIFIED**。
