# Phase 8G 验收

**ARM Runtime BLOCKED。真实 ARM 执行 0 次。** 首个 GCC C → VD 的只读输入与执行方案已准备，当前缺少专用低权限账号、独立资源限额及目标执行的明确授权。基线为 `dc4c39ea048497a1d805ca77dc2fc986e8ca9a12`。

| 状态 | 本轮结果 |
| --- | --- |
| **READY** | 首项冻结 ELF、同侧两文件库投影及执行方案已准备。执行准入仍有阻断。 |
| **EXECUTED** | 宿主 x86-64 合成隔离、进程回收和冻结 Controller 回执验证已执行。ARM 冒烟原生 0/4、交叉 0/4。 |
| **VERIFIED** | 冻结产物、模拟器、Loader、libc 的静态身份和指定依赖关系。宿主合成进程组回收以及 Bubblewrap 私有 PID namespace 对照。 |
| **NOT_VERIFIED** | ARM 实际启动、动态 Loader/Provider 路径、真实目标退出和行为、独立限额 cgroup、SQLite 全量。 |
| **BLOCKED** | 第一次真实 ARM 执行及后续用户态用例。正式 SR Runtime 0/8，尚无已授权匹配设备或 Guest。 |

依次参见 [执行准入与拟申请范围](QEMU_EXECUTION_GATES.md)、[首项实际文件身份与未执行记录](QEMU_SMOKE_RESULTS.md)、[进程回收反例和验证](PROCESS_CLEANUP_VALIDATION.md)、[SQLite 状态](SQLITE_STATUS.md) 与 [剩余缺口](REMAINING_GAPS.md)。

## 回归结果

```bash
python3 -m unittest discover -s .agents/skills/tizen-image-compatibility/tests -v
git diff --check
```

完整回归 **262 项，257 PASS、5 SKIP、0 FAIL**，退出 0。测试耗时 114.594 秒，外部墙钟 115.04 秒，最大 RSS 102,856 KiB。新增 6 项，与原 7 项冻结入口测试一起覆盖正常/异常退出遗留子进程、两个输出流超限、启动交接中断、本地回收中断、cleanup 命令中断及成功回执和实际退出分离。旧超时和 SIGINT 测试增加了进程状态独立验证。五项跳过沿用基线，分别为未启用 libabigail、未启用 Clang AST/ARM 实测、缺可配的 GCC/Clang 组合、缺实际 Clang ARM 编译配置、缺 Clang PCS 测试配置。完整日志 SHA256 为 `261c2c8fd39020be5dae120b53046ca18878412243f70388dbcee959eaf2b64c`。 [原回归基准](../phase8f/PHASE8F_ACCEPTANCE.md) · [定向测试](../../../.agents/skills/tizen-image-compatibility/tests/test_frozen_runtime.py)

生产修改集中在 `compat/core.py` 与 `frozen_runtime.py` 的本地有界运行、清理和回执分项。既有 ABI/Linking 判定、SQLite 资源门槛和历史产物保持原样。
