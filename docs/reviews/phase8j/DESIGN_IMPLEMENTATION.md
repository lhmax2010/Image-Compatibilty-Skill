# Phase 8J 设计与实现

新增单设备 SDB 运行入口、固定远端操作与只读观察验证器。`sdb_runtime.py` 复用原 `frozen_runtime.load_bundle()` 验证 Phase 8E 固定清单和冻结包，复用 `compat.core.Tools` 记录原始输出和限制宿主客户端。成功收到的进程退出与输出采用既有 `tizen-compat-runner/v1` 字段结构。新入口单独输出 profile-scoped 观察，未接入正式 headless 分类器。 [CLI](../../../.agents/skills/tizen-image-compatibility/scripts/sdb_runtime.py) · [生命周期](../../../.agents/skills/tizen-image-compatibility/scripts/compat/sdb_runtime.py) · [固定远端操作](../../../.agents/skills/tizen-image-compatibility/scripts/compat/sdb_protocol.py)

1. 计划阶段验证冻结清单、包及授权配置结构。设备准入读取实际 ARM 架构、两个发布文件、板级序列摘要、当前 boot ID、现有非 root UID、执行挂载、用户 manager 和五个已钉住的 Provider 摘要。
2. 每次只允许一个 Phase 8E 基础探针。授权配置的白名单和 CLI 执行开关都满足后，从现有 SDB 连接创建当前用户的 `0700` 唯一缓存子目录。上传后验证目标 owner、mode 和 SHA256。宿主复制品仅作为上传数据使用。
3. 启动用户级瞬态 scope，由观察会话证明 scope 及非 root 进程已就绪后放行执行。Shell 以 `exec` 保留进程身份，执行前再次校验冻结字节。只设置固定的环境和 glibc Loader 诊断，探针参数为空。
4. 返回实际退出码，二进制输出通过有界 Base64 抓取并逐文件对账 SHA256。Loader 的初始化路径和版本检查从同次执行采集，再核对实际 Provider 摘要。独立读取退出和目录清理证据。输入不符、见证缺失、传输失败或超限时返回不完整结果。
5. 输出分开记录进程成功、行为匹配、本次清理、正式原生参考、跨镜像结论。旧正式入口和冻结头文件、镜像身份、Finding 和 Expected Test 状态保持现有规则。

旧版 SDB 在设备首试拒绝过长的 shell 服务请求。适配器限制请求体为 1,900 B，拆开 cgroup 状态和 armed PID 详细读回。每个响应带随机完成标记。另实测 systemd 属性输出可折行，观察读取启用 `--no-pager --full`。这两个修正均发生在冻结 ELF 放行前。 [真实验证](LIVE_DEVICE_VALIDATION.md)
