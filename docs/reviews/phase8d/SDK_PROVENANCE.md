# SDK 来源与完整性

## 快照与发布索引

| 仓库 | Profile 角色 | repomd.xml SHA256 |
| --- | --- | --- |
| vd | Unified Dev 20261119.012448 | `defc64325b4a9070095969b55ab7b1c35c6aa47815cf959d718408af9b6210fc` |
| vd-base | Base Dev 20261117.165532 | `5a3c1596da5a67b97cd673a550d4bf76e4120576d25651029155205bf6530b30` |
| llvm | Unified Toolchain 20261120.082536 | `b2bebcb7c4194801672cde0c6c0128511cea28ab2dd9bab8e56e9a1a3b538063` |
| llvm-base | Base Toolchain 20261119.042539 | `a9fc01dd6aaaac8e3a15ed7eadc8b3af205a957db76af08b7e4eb226cad881e6` |

四个 repomd.xml 通过官方 HTTPS 得到 HTTP 200，与 Phase 8C 留存版本字节一致。按其记录核对 primary、filelists 和 build.conf 的长度和 SHA256。四个仓库的 repomd.xml.asc、repomd.xml.key 均为 HTTP 404。73 个 RPM 的 NEVRA、长度、primary 的包 SHA256 和 rpmkeys -Kv 的可用摘要全部通过。RPM 包只报告 Header/Payload 摘要，未见可验证签名。来源证据是官方 HTTPS、固定索引和匹配的文件摘要，独立发布者签名认证未建立。

- [vd 发布索引](https://download.tizen.org/RBS/TIZEN/Tizen/Tizen-Unified-Dev/tizen-unified-dev_20261119.012448/repos/standard/packages/repodata/repomd.xml) · [vd-base 发布索引](https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Base-Dev/tizen-base-dev_20261117.165532/repos/standard/packages/repodata/repomd.xml)
- [llvm 发布索引](https://download.tizen.org/RBS/TIZEN/Tizen/Tizen-Unified-Toolchain/tizen-unified-toolchain_20261120.082536/repos/standard/packages/repodata/repomd.xml) · [llvm-base 发布索引](https://download.tizen.org/snapshots/TIZEN/Tizen/Tizen-Base-Toolchain/tizen-base-toolchain_20261119.042539/repos/standard/packages/repodata/repomd.xml)

单包复核时从对应 primary 的 location 取得 RPM，核对 size、checksum 和下表的 NAME、EPOCH、VERSION、RELEASE、ARCH，再执行 `rpmkeys -Kv`。有独立可信发行公钥与有效签名时应另行记录其指纹和验证状态。运行镜像、归档 SHA256 与快照关系沿用 Phase 8C。 [镜像身份](../phase8c/COVERAGE_BEFORE_AFTER.md)

## 实际执行的宿主工具

| 构建环境 | 隔离环境中的实际路径 | 版本 | 文件 SHA256 |
| --- | --- | --- | --- |
| VD | /usr/bin/armv7l-tizen-linux-gnueabi-gcc | Tizen GCC 14.2.0 20240801 1.1 | `bfb61b8c23154c69ac5ed71f3d1954dc06f3b8ff7797dd2791d3125a9e7cef9c` |
| VD | /usr/bin/armv7l-tizen-linux-gnueabi-g++ | Tizen GCC 14.2.0 20240801 1.1 | `c08da30b2189c81f76c08f4058e3a3fda929649de28f8a6e1a201d07d2804e7b` |
| VD | /usr/bin/armv7l-tizen-linux-gnueabi-ld | GNU Binutils 2.43 | `e43158e2d6ef1e8577d40ba41b73dfa02c71b01be6d8543d9548b14137cdd50a` |
| LLVM | /usr/bin/clang、/usr/bin/clang++ | Clang 22.1.8 | `0dcc0f03b64ab388393d4382e0ff8bca2e7147408b1ecf3740e854e9514d3ba1` |
| LLVM | /usr/bin/ld.lld | LLD 22.1.8 | `e0b02fac429d2365b7034095f305a92b00eb1b4a915dbfa87d48501774ecceae` |

Clang 的包默认配置指向 x86_64，ARM 探针显式指定 --no-default-config 和 armv7l-tizen-linux-gnueabi，并通过产物核对最终目标。文件 SHA256 按本地安全解析后的实际二进制计算。逐文件抽取和精确 argv 保留在本地审计记录。

## 73 份 RPM 的固定身份

### vd rootstrap（1 份）

| 仓库 | NEVRA | 包 SHA256 |
| --- | --- | --- |
| vd | `app-rootstrap-devel-0:11.0.1-1.armv7l` | `82f811b0be824c6c3ee7beecb5be788a34c9764ccf3c6e772249cedae2db526c` |

### vd host（9 份）

| 仓库 | NEVRA | 包 SHA256 |
| --- | --- | --- |
| vd-base | `binutils-armv7l-0:2.43-1.1.x86_64` | `4894fdef2e00c2a8038d8c1d91e2c20f261827c9bbf00f0ccd22d1507ab4eb9d` |
| vd-base | `binutils-libs-0:2.43-1.6.x86_64` | `ac692372b36ba4e27ec88bda964409cc34c24ccf1fa78f6fd3df4f95fe03f9d5` |
| vd-base | `filesystem-0:3.1-1.1.x86_64` | `58e8d8fa1573a527a34a16a134e2ac677f936f76c951a1e834ae2a976bacd2cd` |
| vd-base | `gcc-armv7l-0:14.2.0-1.1.x86_64` | `d67b911c66cf876fb673156efeec5ee2d874d8b9510bd0176954c496f9a121a2` |
| vd-base | `glibc-0:2.40-1.7.x86_64` | `3ea1444e9efe19bf64334b78ffaf0d6a7d6cbcd30f975e8079c79e38be515142` |
| vd-base | `libgcc-0:14.2.0-1.6.x86_64` | `7d27273e80bcc9341beee9878d038c446e0532f5ee59f653d2ea12ef460c1879` |
| vd-base | `libstdc++-0:14.2.0-1.6.x86_64` | `08368d65beb82db2fc07c6d97b0cd5262048dea285e882d7964e47f299aa59de` |
| vd-base | `pkg-config-0:0.29.2-1.7.x86_64` | `924b80da68fe76b71a4496afcc6e8575fe55746729b2bd11072aca3b34902ffc` |
| vd-base | `zlib-0:1.3.1-1.6.x86_64` | `ccf3bbabf41922277845be17c0dd94d56a87b774d2045aafa970539e68fa7061` |

### vd target（19 份）

| 仓库 | NEVRA | 包 SHA256 |
| --- | --- | --- |
| vd-base | `filesystem-0:3.1-1.1.armv7l` | `b4352874249a799237eefe75d4f5ccee8ffcbac98c8a7811e14566ec254202f3` |
| vd-base | `gcc-0:14.2.0-1.8.armv7l` | `959949c831e7ecaa447e09554effbcc5e7429c782d6c117c11c21646de328ec4` |
| vd-base | `glibc-0:2.40-1.8.armv7l` | `d5d217dfe73355bab019bc64438775be4d1817d62b92ebb8d158a15553827708` |
| vd-base | `glibc-devel-0:2.40-1.8.armv7l` | `a29f8fb33b337b7c8e4f02491f3843a73c8e334663dab2aea7c46b978dcd93a5` |
| vd-base | `libatomic-0:14.2.0-1.8.armv7l` | `77e8d12dbb86089d97e8a18fb4a93164dfa017111a677b626a6f1afa7965d038` |
| vd-base | `libcc1-0:14.2.0-1.8.armv7l` | `a225eed3299b3d19538ebdb0ef686866cff0aef7b1088a778a06e5f600d2b022` |
| vd-base | `libgcc-0:14.2.0-1.8.armv7l` | `7f6899bf8d1e3017c8e797422ca36eddc04957e74fbd1d3402443137f45309a7` |
| vd-base | `libgfortran-0:14.2.0-1.8.armv7l` | `7e9fb03232075a1ddadf62396c346a8db908b838fb6130b3220ddeefe8060650` |
| vd-base | `libgomp-0:14.2.0-1.8.armv7l` | `cb0187703bfa6b68b8dfcbebedccd9106caaa16dfdd2999e7964bb110e8f018b` |
| vd-base | `libitm-0:14.2.0-1.8.armv7l` | `37e43944b3dd2491489d59983d8ebac1bd881f4b96fb995a9a6976d8131fc301` |
| vd-base | `libstdc++-0:14.2.0-1.8.armv7l` | `70e37262cf51c0a06e338f7742c5afc24c0e4d959f2daf27e350db24ace4bd06` |
| vd-base | `libstdc++-devel-0:14.2.0-1.8.armv7l` | `4e87f152bbbbc90c5c4275e95310d41a4ea4e3d28eccf210edb02055c335a77e` |
| vd | `libtzplatform-config-0:5.0-1.armv7l` | `da5b60b186087aa573cb5e10c3439422f634b623f4569cd4eb8c43e08c85747b` |
| vd | `libtzplatform-config-devel-0:5.0-1.armv7l` | `e54e3fa89d5a79bfd37331637aec1549271971aa8ca4f53b164f70d51431b8e1` |
| vd-base | `libxcrypt-0:4.4.36-1.7.armv7l` | `3fa9fa8cbde7df0f9d2b0416b8037ae06f972b89a83a5485075bc366a2ebb01a` |
| vd-base | `libxcrypt-devel-0:4.4.36-1.7.armv7l` | `825afc731579fdf073311c0707d01252f1384cf1fa848e4bcf52d5e16d062d6c` |
| vd-base | `linux-glibc-devel-0:6.6-1.8.armv7l` | `4574ebc2be56c866ebaea50bdc5449a1d9108b3782333f5616174ceb18cb17a7` |
| vd | `tizen-platform-config-0:5.0-1.armv7l` | `9f310fbc9ee16c9ebd4aa93962daf5e2ef46de6921ba8e28a2773be9a8a37f34` |
| vd-base | `zlib-0:1.3.1-1.6.armv7l` | `dca49bd5829f6eb9a3457fcf219739c3b77c9f8fad18efb545c5713fde0d1a10` |

### llvm rootstrap（1 份）

| 仓库 | NEVRA | 包 SHA256 |
| --- | --- | --- |
| llvm | `app-rootstrap-devel-0:11.0.1-1.armv7l` | `85d966a528765001bf69d4328541e13b4d28905f2d18bf98974a0b89fb0384c9` |

### llvm host（17 份）

| 仓库 | NEVRA | 包 SHA256 |
| --- | --- | --- |
| llvm-base | `clang-0:22.1.8-1.6.x86_64` | `0d52afd9f652f95239e3b4c6567b8cebe157f83a99e0b572276eb0d4230d8085` |
| llvm-base | `filesystem-0:3.1-1.1.x86_64` | `65c021d93749f12408ff54409de76f55d3264928c52dfbc6f19c2798fa3f0bc8` |
| llvm-base | `glibc-0:2.40-1.7.x86_64` | `0c8680c1a50f583a0664bab111a76aa6c396dec371f09cb2f9e5695826582d51` |
| llvm-base | `libgcc-0:14.2.0-1.6.x86_64` | `32c76f72328fc8c3b2a9672837a112696ae1355e2a72bad9ff74da30bef9f056` |
| llvm-base | `libllvm-0:22.1.8-1.6.x86_64` | `7d044fb24207821baba8f4cd160561e07a939103fa374a6db154e16a859b525c` |
| llvm-base | `liblzma-0:5.8.1-1.7.x86_64` | `01ce1745d0d15bb190bba9a5c8b11863bd8fa9952dea6d722c64e8cf4bf91009` |
| llvm-base | `libncurses6-0:6.6-1.7.x86_64` | `89f714c44f3b4bd845024a1471cfa284dd02d5ad3257508fccd094348f93dc38` |
| llvm-base | `libsmack-0:1.3.1-1.6.x86_64` | `3a3310e9661759d115a3d69987a4e8bed6be17d178f53966ae4f2f22386b0f3e` |
| llvm-base | `libstdc++-0:14.2.0-1.6.x86_64` | `1edc6d5b3321299e704bb1e5e55b89ac51a68d42ab27a518de738750eab3f2da` |
| llvm-base | `libxcrypt-0:4.4.36-1.7.x86_64` | `52dc4e0c63be2893c2625c192e4f01fe8d8698f7b5a7f0f62ae75ee253245d48` |
| llvm-base | `libxml2-0:2.15.1-1.7.x86_64` | `91b10abbb1ae9b9fae1a1bb986bb5958ea564a04ce3b4ddb418255e182a8a745` |
| llvm-base | `lldb-0:22.1.8-1.6.x86_64` | `d729bc424b6cf68642eb11aaf224940477b9a124bb42b7e5d2a2d33d561814f1` |
| llvm-base | `llvm-0:22.1.8-1.6.x86_64` | `607043cc6c5c41aaca8c19aa1c0f0c766435065dde26a3ea26ebfdf9c7718531` |
| llvm-base | `pkg-config-0:0.29.2-1.8.x86_64` | `0d548f48c290f4b2904fed374c7ca8f40ffbe7d1a28543898e467ee82bca3ec4` |
| llvm-base | `terminfo-base-mini-0:6.6-1.7.x86_64` | `42d7deb10ec344575434f352aad5981c7b655f1476f105e2ed38b1414c5d0825` |
| llvm-base | `toybox-0:0.8.14-5.1.x86_64` | `3f423ccb47e78c34d0bf3711afe37115320fc5392160b14fe243fa4df4de6de3` |
| llvm-base | `zlib-0:1.3.1-1.6.x86_64` | `47d6f305d5999fdb84b38e92cbce3c9be93dc2fb3db31100be8c8ef004cb4fc2` |

### llvm target（26 份）

| 仓库 | NEVRA | 包 SHA256 |
| --- | --- | --- |
| llvm-base | `compiler-rt-0:22.1.8-1.6.armv7l` | `f8228b43c73a2e0b94cff958525f0d0b4a14631bc1b933345388c01ed2a4e625` |
| llvm-base | `filesystem-0:3.1-1.1.armv7l` | `ff4c4f3720f016958da970246d817e522fc8b1c26a2c5d4fc42e52722af57bb3` |
| llvm-base | `gcc-0:14.2.0-1.7.armv7l` | `03602649d21fd21e0d3ae4150d9b3f78357f0c19e786586da3eae157f15f3396` |
| llvm-base | `glibc-0:2.40-1.8.armv7l` | `bf7f128afc248f79fbac3490cd4ed7bd4f295711fa422b295181948b64eeb2a6` |
| llvm-base | `glibc-devel-0:2.40-1.8.armv7l` | `53df79c1a6fa8752ab017d54a113a4e43978c854b9855eea2f88fa71b5d48b55` |
| llvm-base | `libatomic-0:14.2.0-1.7.armv7l` | `f6b8c7de652b162c4663da5d1acbc2466e60e2e18af9427e3e4121d8fa963b58` |
| llvm-base | `libc++-0:22.1.8-1.1.armv7l` | `8b20dff45e80ae988a084199481016d9ab969040f121e4f0d66602b3b42048c9` |
| llvm-base | `libc++-devel-0:22.1.8-1.1.armv7l` | `1b0c5150a3025cc47375e17556b91ea0837cfd88af12485da6094e4910f1c39f` |
| llvm-base | `libc++abi-0:22.1.8-1.1.armv7l` | `6bb9b81f0de60a8fb08e29842484095db676a854faa0a3c687fd3149aeb0e4ca` |
| llvm-base | `libc++abi-devel-0:22.1.8-1.1.armv7l` | `572ed70852f4a0fc94dcd97098031b1334df29b643be9ccf1abb5291c5c389c8` |
| llvm-base | `libcc1-0:14.2.0-1.7.armv7l` | `1554759a4719a22e250eed67d32d082d028d24dd5490afba43df5310a56bb494` |
| llvm-base | `libgcc-0:14.2.0-1.7.armv7l` | `ef5e4873d5486a6e99d247c537cfef0f504852b564f86ba18b3ecf3903819b68` |
| llvm-base | `libgfortran-0:14.2.0-1.7.armv7l` | `84b040786f92314c0c94c680d5f941e0b0219e2ed57b5a41e149cfd5911c5c0a` |
| llvm-base | `libgomp-0:14.2.0-1.7.armv7l` | `39d2971b5ad917c79223b578dedc38a6b8e682f56b342eec28e34343ecde3d4b` |
| llvm-base | `libitm-0:14.2.0-1.7.armv7l` | `8173bbeeaedef79c96c7fb3fbf5a6eb8e30115e599866e2473c613daf1af04c0` |
| llvm-base | `libstdc++-0:14.2.0-1.7.armv7l` | `ce3d1f09ecc395a0cf8b275b1c62d6a80c839638e7b9aa6e8b62f62c423da03d` |
| llvm-base | `libstdc++-devel-0:14.2.0-1.7.armv7l` | `94e80c9f90168e9898811bf4288449ac1d3b89cebe8247fd836ce42e9a4ed5f3` |
| llvm | `libtzplatform-config-0:5.0-1.armv7l` | `37bef4b351d83980437e90a60cd53757e24bf14eca498b574abd82a291fe3be3` |
| llvm | `libtzplatform-config-devel-0:5.0-1.armv7l` | `28f1fb56d20e41654c1fd7f00fd1e425278d034e8eca42abed26ab8cca7f9a03` |
| llvm-base | `libunwind-0:1.6.2-1.1.armv7l` | `ed90979411331f9397f7ec480a3520f4fca8e5dea09022d8edf66ff6f42a2bee` |
| llvm-base | `libunwind-devel-0:1.6.2-1.1.armv7l` | `a8026c3a493a2bf01be675e95a3bdf9127b09696dacedbeec68fc7f1137bbdce` |
| llvm-base | `libxcrypt-0:4.4.36-1.8.armv7l` | `f6db5e68656b1721f0e761ee0889696dbf3e30281e38f1901d399a10d76b2ac7` |
| llvm-base | `libxcrypt-devel-0:4.4.36-1.8.armv7l` | `c144632a4070ed3a226012f78cb1f6d4442bb33abbecb404c0100904391e6539` |
| llvm-base | `linux-glibc-devel-0:6.6-1.8.armv7l` | `d801cabe8d1c8ab1e6791a1a9f2f2632858d1ec40b9bf0941fa4afad2f739251` |
| llvm | `tizen-platform-config-0:5.0-1.armv7l` | `7aa8e56f5a09f8881f696acd4c5870c8b941a159a1df9a961fd473b12361845c` |
| llvm-base | `zlib-0:1.3.1-1.8.armv7l` | `76e71f3fdf223db8aec9573c5b6d455a5c3fe05e8283ddb79718baee3c0ad218` |
