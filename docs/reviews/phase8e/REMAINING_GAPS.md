# 外部资源与准入缺口

- **可运行 SR 的授权环境。** 需要已核实运行 VD 和 LLVM 对应快照的隔离设备或 Guest、实际包及启动标识、普通测试账号、访问范围、写入边界和清理授权。对 QEMU System 路线，还需同意安装模拟器、取得匹配 Kernel/DTB/Boot 配置和分配存储。QEMU User 冒烟应单独授权和标注范围。 [环境方案](RUNTIME_ENVIRONMENT_OPTIONS.md)
- **目标 Adapter 验证。** 需要在两侧验证部署后哈希、启动身份、真实结果及超时/断线进程回收。普通测试还需给出有效加载器、库、Linux 用户与挂载证据。AT_SECURE、Namespace、setuid、File Capability 等仍需要独立授权和上下文。 [Adapter 规格](RUNTIME_ADAPTER_READINESS.md)
- **真实四象限。** 四个已冻结对象的 8 项目标组合均为 NOT_EXECUTED。确认原生运行参照后再比较跨侧表现。 [执行顺序](FOUR_QUADRANT_EXECUTION_PLAN.md)
- **libc++ 产品迁移。** 可离线编译链接。SR 当前没有安装两种 libc++ 运行库，需要独立的部署、运行和跨 DSO 异常验证。 [独立轨道](LIBCXX_FEASIBILITY.md)
- **SQLite。** 真实构建、数据对账及实际资源见 [SQLite 验收](SQLITE_FULL_ACCEPTANCE.md)。
