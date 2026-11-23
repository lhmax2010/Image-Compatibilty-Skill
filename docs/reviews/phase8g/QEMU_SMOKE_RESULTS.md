# QEMU_USER_SMOKE 执行与身份记录

**执行次数 0。原生 0/4，交叉 0/4，均为 BLOCKED。** 当前没有目标退出码、stdout、stderr、实际解释器打开记录、动态绑定或目标进程退出观察。正式 SR Runtime 仍为 0/8。

| 阶段 | 用例 | 实际结果 |
| --- | --- | --- |
| A | GCC C → VD 投影 | BLOCKED。静态文件身份与宿主替代预检已核实。 |
| B | Clang C → LLVM 投影 | BLOCKED。等待 A 的有效原生证据。 |
| C | GCC C++ → VD 与 Clang C++ → LLVM | BLOCKED。等待两个原生 C。 |
| D | GCC C/C++ → LLVM 与 Clang C/C++ → VD | BLOCKED。等待各自原生产物的有效证据。 |

## 首项真实输入的静态身份

VD 为 `tizen-unified-dev_20261119.012448`，发布归档 SHA256 `ec4b0e371151711b881c2def2a11fd8c941b36ed030e61691650573a12546237`。下表由实际文件的 SHA256 与 `readelf -W -h -l -d -A -n --dyn-syms -V` 重新核对。投影中的文件为普通、只读文件，无 setuid/setgid 和 file capability。 [冻结清单](../phase8e/ARTIFACT_MANIFEST.json)

| 角色和目标路径 | SHA256 | Build ID |
| --- | --- | --- |
| GCC C `/runner/probe` | `8b9a99ab11fff447022618f796ee397cccd21fbaf4d30a29d9561647c3f687fc` | `52ab99d766461b94e206566043fc2a7cf694bbf3` |
| Loader `/lib/ld-linux.so.3` | `0b1fe895ab844a3dfb04a2ab034a6fca9aeadb570abd49b36bf4be16a676f4df` | `ea82b530d45842e6aadf046ea0635608946c1a51` |
| Provider `/lib/libc.so.6` | `f5a377a3121928d31111fa3a556a5ffe16014dc75254620bf2257d5ab7c1e4d4` | `a91fd88503ac5874d098e0271f68757baa489eb4` |

冻结 ELF 请求该 Loader，唯一直接 `DT_NEEDED` 为 `libc.so.6`。libc 唯一直接依赖该 Loader，Loader 无直接依赖。冻结探针的 4 个版本化导入和 `GLIBC_2.4`、`GLIBC_2.34` 两个节点，以及 libc 对 Loader 的 22 个版本化导入，均在指定静态文件中匹配。三者均无 RPATH/RUNPATH。实际 Loader 与 Provider 的选择保持 **NOT_VERIFIED**。首项预期结果从源码推导，仍需实测。 [准入与授权范围](QEMU_EXECUTION_GATES.md)
