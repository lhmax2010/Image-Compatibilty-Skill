# SDB Adapter 与探针 Bundle

Phase 8E 冻结清单继续由原加载器验证。新增的 `tizen-compat-probe-bundle/v1` 支持每项探针独立的普通 ARM 程序、伴随 DSO、预期退出和可选符号绑定观察。运行入口要求由工作流配置或独立参数传入审核后的清单 SHA256。设备执行授权另行匹配清单、目标身份指纹、产物 ID 和完整 SHA256。生成清单本身不会授予授权。

`compat/probe_bundle.py` 检查完整文件表、文件名、目录与路径边界、symlink、大小、文件摘要、ELF 类型、EABI 及实际解释器。主 executable 和每个 DSO 都单独校验，完整 Bundle 在 SDB 部署后再次校验，伴随 DSO 在 grant 前复核。Adapter 提供固定协议操作，SDB 只使用配置中的已连接端点。默认计划模式离线，`--admit` 只读，`--execute` 还要求 enrollment 允许执行。

`compat/runtime_build.py` 保存原始源码摘要、SDK 锁定文件摘要、编译器摘要、实际 argv、退出码和 readelf 证据。构建以 bwrap 提供 SDK 只读视图，产物发布为只读本地副本。被审核的 SDK 和构建配方属于信任输入，静态镜像文件不会被用作编译器。

本轮使用单独的 headed enrollment，沿用已审核的硬件和基础运行库摘要。新增的 `libpthread.so.0`、`libdl.so.2` 摘要来自已保存的 LLVM 参考镜像，并通过设备准入再次核对。该事实只证明相应文件相同，保留两个 Profile 的独立身份。

关联实现见 [Bundle validator](../../../.agents/skills/tizen-image-compatibility/scripts/compat/probe_bundle.py)、[SDB Adapter](../../../.agents/skills/tizen-image-compatibility/scripts/compat/sdb_runtime.py) 和 [CLI](../../../.agents/skills/tizen-image-compatibility/scripts/runtime_workflow.py)。
