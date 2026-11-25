# 剩余缺口

- VD headed 尚未进入验收。切换前取对应 Profile 的发布版本、关键库哈希、匹配 SDK 与合法执行授权。原始四个冻结程序仍需在各自原生环境完成参考，随后用相同 SHA256 交叉运行，比较 Loader、Provider、版本绑定、退出码、确定性输出与清理。
- Headless 正式矩阵仍为 0/8。已有静态对比和 LLVM headed 的实机观察分别保存，正式跨镜像兼容性保持 UNKNOWN。
- 独立 SDB 会话复查了本轮受控探针的进程。正式目标监督仍需独立可信机制证明 cgroup 与真实目标资源回收，因此正式 cleanup 字段保留 NOT_VERIFIED。
- 当前 LLVM headed 的可见标准库路径和 Loader 缓存中缺少 `libc++.so.1` 与 `libc++abi.so.1`。既有 Clang + libc++ 只具备独立离线编译链接证据，设备执行跳过。其 `libunwind.so.8` 可见不改变此结果。
- Secure execution、特权程序、其他 namespace、产品全量应用、性能和未执行的 Lazy Binding 仍缺少证据。专项结果不改变历史 Linking UNKNOWN。
- SQLite 实验独立记录于 [SQLite 验收](SQLITE_ACCEPTANCE.md)。
