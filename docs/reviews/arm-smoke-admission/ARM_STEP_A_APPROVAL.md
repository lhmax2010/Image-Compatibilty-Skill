# 首次 ARM Step A 待审批状态

**当前未具备申请第一次 ARM 执行授权的条件。** 管理员配置和专用环境宿主预检尚未通过，本轮未生成可执行的 Step A 审批命令。ARM 实际执行 0 次。

宿主预检通过后才能固定命令，范围仅包括冻结 `vd-A-C`、指定 QEMU User、Cortex-A9 与同快照的 VD Loader/libc。届时记录实际投影路径和哈希、限制、网络隔离、workspace 内输出位置、目标输出预测、以及按 cgroup 和进程身份核对的异常回收。待该命令获得单独授权后再执行。 [已冻结指纹与第一项范围](../phase8h/QEMU_SMOKE_RESULTS.md) · [当前阻断](ENVIRONMENT_SETUP.md)
