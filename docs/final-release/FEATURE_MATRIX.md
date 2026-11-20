# 功能与验证矩阵

| 功能 | 实现 | 本轮验证与边界 |
|---|---|---|
| ELF header、EABI、PCS、VFP 参数、SONAME、版本化导出、Data/TLS size | IMPLEMENTED | 原 Phase 7A 正反测试、真实 ARM ELF 字节和真实文件抽样。复杂类型、布局仍依赖匹配的调试信息 |
| ARM/Thumb、TLS relocation、stack 与 unwind | PARTIAL | 静态属性、段、节、relocation 类型和计数。互操作、指令可执行性和 unwind 行为在真实 ARM 上 UNVERIFIED |
| DT_NEEDED、RPATH/RUNPATH、Loader 与 Provider | PARTIAL | Phase 7A 解析模型和已有 SONAME 复用经回归。复杂命名空间、运行时装载和实际 secure-execution 需实证 |
| Public Header / API、文件系统及配置 | PARTIAL | Header 完整性门控、静态声明／include、SDK 编译，以及包及权限元数据。缺权威 API 清单和完整语义证明 |
| RPM 与归属 | IMPLEMENTED | 现有包、ELF、符号和角色报告，真实 722/736 包对账 |
| Systemd、CLI、IPC、D-Bus | PARTIAL | Unit/命令静态清单、D-Bus 在已知文件范围内的线格式契约、可声明能力的运行探针。真实 bus 与启动环境 UNVERIFIED |
| 权限、安全与内核 | PARTIAL | 文件模式、可读 ACL/LSM 及 UAPI 证据。有效安全策略、内核行为和硬件 UNVERIFIED |
| Network、Multimedia | PARTIAL | 配置、头文件、库和插件线索，Unix socket 代表性探针。公网、设备、编解码和加速行为 UNVERIFIED |
| C++ 运行库与跨 DSO 验证 | PARTIAL | 观察库名及符号。可信本机正、反例执行 RTTI、生命周期、异常、标准库字符串、TLS、forced unwind；实际跨 SDK/运行库混编 UNVERIFIED |
| GCC / Clang 四象限 | IMPLEMENTED | 期望 ID 与自身参考、真实本机编译成功/链接失败控制。两套真实 ARM SDK 四象限 UNVERIFIED |
| 目标部署与执行 | IMPLEMENTED | 现有外部回执协议与新增 rootless Podman 命令、身份、超时、清理及重复检查已测。实际 Podman 和 Tizen 设备 UNVERIFIED |
| 自动刷机、策略放宽、设备配置修改 | UNSUPPORTED | 交付流程只接受已授权的隔离目标 |
| 影响分析、历史回归、Web 和 CI | IMPLEMENTED | 完整真实侧车、反向索引、历史 Fixture 正反对照、历史数据规模控制与分页 |
