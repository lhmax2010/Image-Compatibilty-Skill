# Skill 功能矩阵

| 功能 | 状态 | 证据范围 |
| --- | --- | --- |
| ELF、ABI、RPM、Finding、Impact | IMPLEMENTED_AND_VERIFIED | 历史真实 SR headless 静态报告、Phase 7A/8A–8C 回归 |
| API、Header 与完整动态链接覆盖 | PARTIAL | 静态证据有缺口；保留逐项 UNKNOWN |
| 镜像准备与可用提取工具 | PARTIAL | Rootfs TAR、包与已知封装有回归；VDFS 依赖外部可信提取器 |
| 两侧 ARMv7 SDK 编译链接 | IMPLEMENTED_AND_VERIFIED | 21 项新真实构建，及 Phase 8D 的正反链接结果 |
| 冻结与签核、DSO Bundle | IMPLEMENTED_AND_VERIFIED | 阻止未知摘要、目标、路径、文件和未授权请求；真机核对部署摘要 |
| LLVM headed SDB 基础观察 | IMPLEMENTED_AND_VERIFIED | 4 个冻结产物各 3 次 |
| C++ 跨 DSO、RTTI、异常、对象协定、TLS、Unwind | IMPLEMENTED_AND_VERIFIED | 4 个编译器搭配及行为、线程、取消探针 |
| GNU 版本和指定符号绑定 | IMPLEMENTED_AND_VERIFIED | 真实正例、缺版本、缺符号和缺 Provider |
| 自定义 DSO 动态加载 | PARTIAL | 常驻 Provider 句柄成功；设备禁止私有 DSO 的 dlopen |
| 独立 SDB 清理观察 | IMPLEMENTED_AND_VERIFIED | 实机进程/cgroup、scope、目录与另外的最终只读复核 |
| 正式目标清理与 headless 执行矩阵 | IMPLEMENTED_BUT_UNVERIFIED | 无独立可信目标监督，正式矩阵 0/8 |
| VD headed 原生与双向对照 | IMPLEMENTED_BUT_UNVERIFIED | 本轮单 LLVM headed 设备 |
| libc++ | PARTIAL | 离线编译链接已证实；设备两项关键 Provider 缺失 |
| 统一 JSON、Markdown、HTML 与 Scope 隔离 | IMPLEMENTED_AND_VERIFIED | 自动化合成测试与真实报告 |
| 全量 SR SQLite | IMPLEMENTED_BUT_UNVERIFIED | 真实建库已启动，独立对账待完成 |
| 任意远端命令、自动提权 | UNSUPPORTED | SDB Adapter 只提供固定操作 |
| 刷机、QEMU 等 | NOT_APPLICABLE | 本轮已有真实 LLVM headed 设备 |
