# 自动化回归

基线共 278 项，273 PASS、5 SKIP、0 FAIL。新增 SDB Runner 10 项测试全部通过，总数 **288 项，283 PASS、5 SKIP、0 FAIL**，退出 0。测试耗时 128.292 秒。五项跳过仍是此前未启用或不可用的 libabigail 与实机 Clang/ARM 工具链条件。 [既有回归基线](../arm-smoke-admission/FINAL_ACCEPTANCE.md)

| 组 | 覆盖 |
| --- | --- |
| 运行与原始数据 | 正常退出、非零退出、scope 超时、二进制捕获和目标退出证据分离。 |
| 传输 | SDB 中断、输出超限、旧版服务长度拒绝、新鲜远端完成标记、明确绑定一个端点。 |
| 身份 | 后部署 SHA256 不符、Profile 不符、PID/Session 或 cgroup 身份不符均阻断放行。 |
| 清理 | 缺失、过期、残留进程导致不验证，活任务残留时不删除目标测试目录。 |
| 授权 | 默认计划无目标请求，只读准入无部署，缺授权、缺白名单或正式 headless 执行请求均在传输前被拒。 |
| 远程操作 | 固定 shell 片段语法验证。 |

```bash
python3 -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v
git diff --check
```

测试用结构化合成 transport。没有在真实设备制造断线、错误制品或残留进程。本地全量测试日志 SHA256 为 `baff42c6ffa9727588c429f7172e3a73c03e8c8bbdc37bc6a2e00b3f1c0b9238`。 [新增回归源码](../../../.agents/skills/tizen-image-compatibility/tests/test_sdb_runtime.py)
