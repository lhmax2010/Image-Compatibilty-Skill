# 静态 ABI 验证

ARM 正反 fixture 构造实际 ELF32/ET_REL 字节，由 GNU `readelf` 读出 EABI5、`R_ARM_TLS_LE32`、Thumb-2 属性和 `.ARM.exidx`。VFP PCS 与 base PCS 的明确冲突产生 INCOMPATIBLE，完全相同的对象不产生冲突。Quick 模式没有 relocation 观测。硬件能力继续 UNVERIFIED。 [Arm ELF ABI](https://github.com/ARM-software/abi-aa/blob/main/aaelf32/aaelf32.rst)

使用既有 Tizen GCC/LLVM 已提取 Rootfs，各选择 8 个 ARM ELF 只读检查。覆盖 bash、RPM、systemd、busctl、libstdc++、libgcc_s、libc、libpthread。样本输出为 `8 COMPATIBLE / 7 UNKNOWN / 3 INCOMPATIBLE / 1 IDENTICAL`。三个不兼容项的证据分别为 rpm、systemctl、busctl 的 `_IO_stdin_used` 动态导出缺失。样本不包含这些导出的公共 API 权威或直接消费者证明。所有样本文件的前后 SHA256 一致。原始工具证据和逐条 Finding 在 `.local-backups/final-development/real-arm-sample/static-arm-sample.json`。

D-Bus 测试验证公开 wire type 变化、已确认删除、同协议保留、损坏 XML 和禁用实体声明。解析完成标记属于文档范围。旧 Manifest 缺标记、同名歧义或候选文档未读完时，相关缺失保持 UNKNOWN。

原 Header、dynsym、SONAME、secure-execution 的 Phase 7A 测试继续执行。真实全镜像旧报告为历史静态证据，新增分析逻辑对样本和可重现 fixture 验证。 [已知限制](KNOWN_LIMITATIONS.md)
