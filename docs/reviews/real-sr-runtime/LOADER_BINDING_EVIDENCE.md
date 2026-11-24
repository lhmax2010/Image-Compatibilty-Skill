# Loader 与 Provider 证据

**实际运行时绑定 NOT_VERIFIED。** 下表由设备上的 `readlink -f`、`stat` 和 `sha256sum` 实测，代表已存在文件。五个文件均匹配冻结 LLVM headless 参考，五个均与冻结 VD 参考不同。

| 接口名 | 实际存在文件 | 设备实测 SHA256 |
| --- | --- | --- |
| ld-linux.so.3 | `/usr/lib/ld-linux.so.3` | `b011ebe723dc6e8115f4eb44c964817f7d61878e44d6de3a9367e7359b5bf7da` |
| libc.so.6 | `/usr/lib/libc.so.6` | `9f2ae4ee0d10374c7681a33b09b5a84dbfca82c3d1bc012edf81483f11202b96` |
| libstdc++.so.6 | `/usr/lib/libstdc++.so.6.0.33` | `871c24ae874b77d767cffff6933886566985326e20fd787bdd9892816284ae53` |
| libgcc_s.so.1 | `/usr/lib/libgcc_s.so.1` | `904b67964d3e751b9d9213fdb0b7643bf18d5e15294a0fb50782c580610cdb25` |
| libm.so.6 | `/usr/lib/libm.so.6` | `3ed8dbce48a46dd38779d7aba07acf90404ae9a6a8ba5e6104577f357136adf1` |

本地冻结 ELF 的 `PT_INTERP` 均为 `/lib/ld-linux.so.3`。GCC C 的直接 `DT_NEEDED` 为 libc，Clang C 还需要 libgcc_s，两份 C++ 均需要 libstdc++、libm、libgcc_s 和 libc。目标实际加载顺序、Provider 选择、符号版本及行为均无动态观测。 [冻结 ELF 结果](RUNTIME_EXECUTION_RESULTS.md)
