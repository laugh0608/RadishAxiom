# 2026-11-07：L3 Python 发布来源与内嵌 libffi 核对

日期为 2026-11-07（Asia/Shanghai）。基线为干净的 `dev` / `26c6a7a`，本地领先 `origin/dev` 两笔。90 分钟批次限于 L3 使用的宿主 Python、构建清单及 `_ctypes` / libffi 的来源和许可。已有 [L3 有限审阅](2026-11-07-linux-channel-l3-input-acceptance-review.md)与 [Rust 来源核对](2026-11-07-linux-channel-l3-rust-source-readback.md)继续提供宿主和 Rust 边界。

## 本机 Python 与发布制品的对应

本机路径为 `/Users/luobo/.local/share/mise/installs/python/3.14.5/bin/python3.14`。该文件为 18,053,472 bytes，SHA-256 `c015ab131972822e27ed108cf353582af6ca2fd7daf6296789576c7e7d1ad61a`，与 Astral Python Build Standalone `20260510` 的 ARM64 Darwin `install_only_stripped` 成员逐字节相等。已对回精确发布制品与构建清单。 [Astral 发布](https://github.com/astral-sh/python-build-standalone/releases/tag/20260510)

| 发布资产 | bytes | SHA-256 |
| --- | ---: | --- |
| `cpython-3.14.5+20260510-aarch64-apple-darwin-install_only_stripped.tar.gz` | 25,930,388 | `1bb0b3d45448dfe7e916dc62144cfd7d7a611dc6ccf05b8bb71662cc5c2a1ad2` |
| `cpython-3.14.5+20260510-aarch64-apple-darwin-pgo+lto-full.tar.zst` | 60,711,262 | `5e3a68e7fee2d3c9275d461951444a9ed882d2e25e8fc77761fd038a7b98de7b` |

两份资产匹配 GitHub Release 的长度与摘要。用宿主 `gh 2.96.0` 和 GitHub API 返回的证明原件离线验证 SLSA provenance，绑定仓库 `astral-sh/python-build-standalone`、签发工作流 `.github/workflows/release.yml`、源提交 `f0ae464f527498d6c4b13f19977447d603cd5edd`。两个摘要出现在同一份已验证声明中。声明中的工作流文件名分别为 `cpython-3.14.5-aarch64-apple-darwin-install_only_stripped-20260510T1214.tar.gz` 和 `cpython-3.14.5-aarch64-apple-darwin-pgo+lto-20260510T1214.tar.zst`。完整包与安装包的解释器和 `libpython3.14.dylib` 分别拥有相同 Mach-O UUID 和 `__TEXT,__text` 字节。 [固定发布工作流](https://github.com/astral-sh/python-build-standalone/blob/f0ae464f527498d6c4b13f19977447d603cd5edd/.github/workflows/release.yml)

核对 71 个选定安装文件。解释器、`libpython3.14.dylib`、`Setup.local`、`build-details.json`、`LICENSE.txt` 和两轮探针涉及的 65 个模块源文件共 70 个逐字节相等。其余一个 `_sysconfigdata__darwin_darwin.py` 用 mise `v2026.5.16` 的固定源码规则重放后逐字节相等，重放 SHA-256 为 `5fc955e447d752fbe302a935e3d0febd1846735342b0c151013d23912b1759fa`。规则替换安装前缀、规范化编译器设置并写入 `PYTHON_BUILD_STANDALONE=1`。本轮实际探针以 `-I -S -B` 运行，导入跟踪仍读取了 49 个本地 `.pyc`。逐个将这些缓存代码对象和已验证发布源码重新编译的结果比较，规范化代码对象内的文件名后全部相等。 [mise 固定处理规则](https://github.com/jdx/mise/blob/f1d8bb19615e87e292cea9ab5f16df386f25da45/src/sysconfig/mod.rs)

## `_ctypes`、libffi 与许可

完整包的 `python/PYTHON.json` 为 129,219 bytes，SHA-256 `9b1f5705e3d689d3700dc0e722696796155694dce4aca074fc359c87bdc1937d`。清单标记 CPython `3.14.5`、`aarch64-apple-darwin`、`pgo+lto`、SDK 15.5 和最低构建目标 11.0。`_ctypes` 项绑定 `PyInit__ctypes`、六个 `Modules/_ctypes` 对象、系统 `dl` 和 `build/lib/libffi.a`。静态库为 54,480 bytes，SHA-256 `c38c4bf9822e6846755e833b3487304b30d0aa82ceb928cf05419bee25a7c81c`。三份 `Setup.local` 相等，均把 `_ctypes` 列为静态模块并传入 `-hidden-lffi`。未剥离的解释器在代码段定义了 `PyInit__ctypes`、`ffi_call`、`ffi_prep_cif`，本机解释器的 Mach-O 动态库声明中没有 libffi。宿主探针确认 `_ctypes` 由 BuiltinImporter 导入。 [模块构建定义](https://github.com/astral-sh/python-build-standalone/blob/f0ae464f527498d6c4b13f19977447d603cd5edd/cpython-unix/extension-modules.yml)

| 材料 | 核对结果 |
| --- | --- |
| CPython `_ctypes` | 固定配方指向 CPython `3.14.5` 源包，23,903,332 bytes，SHA-256 `7e32597b99e5d9a39abed35de4693fa169df3e5850d4c334337ffd6a19a36db6`。六个对应 C 源文件的摘要已留存。Astral 配方含 `patch-ctypes-callproc.patch` 与 `patch-ctypes-static-binary.patch`。源包根 `LICENSE` 与安装包、本机 CPython `LICENSE.txt` 逐字节相同，SHA-256 `b0e25a78cffb43f4d92de8b61ccfa1f1f98ecbc22330b54b5251e7b6ba010231`。完整包清单另指向 Astral 的 `licenses/LICENSE.cpython.txt`，标记 `Python-2.0` 与 `CNRI-Python`。 [CPython 发布](https://www.python.org/downloads/release/python-3145/) · [Astral CPython 配方](https://github.com/astral-sh/python-build-standalone/blob/f0ae464f527498d6c4b13f19977447d603cd5edd/cpython-unix/build-cpython.sh) |
| 内嵌 libffi | 固定配方指向 libffi `3.4.6` 源包，1,391,684 bytes，SHA-256 `b0dea9df23c863a7a50e825440f3ebffabd65df1497108e5d437747843895a4e`。Astral 的脚本含补丁并使用 `--disable-shared`，完整包清单对该静态库声明 MIT 和 `licenses/LICENSE.libffi.txt`。源包许可证与随包文本从第二行起逐字节相同，第一行仅版权终止年份不同，源包为 2024，随包为 2019。保留两份文本，3.4.6 的版权归属以精确源包原文为据。 [Astral 下载锁定](https://github.com/astral-sh/python-build-standalone/blob/f0ae464f527498d6c4b13f19977447d603cd5edd/pythonbuild/downloads.py) · [静态构建配方](https://github.com/astral-sh/python-build-standalone/blob/f0ae464f527498d6c4b13f19977447d603cd5edd/cpython-unix/build-libffi.sh) · [libffi 3.4.6 发布](https://github.com/libffi/libffi/releases/tag/v3.4.6) |

## 复核材料与剩余缺口

下载、来源片段、SHA-256 比较及验证原件留在本机忽略目录 `.tmp/l3-python-source-review-20261107.6VIKRMqU/`。四个精确归档均按大小和摘要核验，通过后才流式读取选定成员。Mach-O 和 `ar` 观察使用任务目录中的非可执行副本。用 `python3.14 -I -S -B <任务目录>/compare-python.py <任务目录>` 可重放成员、安装文件、sysconfig 和缓存比较。可用留存的 `*-api-bundle.jsonl` 和 `trusted-root.jsonl` 按上述仓库、工作流及提交限制复跑 `gh attestation verify --bundle … --custom-trusted-root …`。直接的 release attestation 查询无结果，在线 build attestation 下载发生 TLS 超时。后续以 API 提供的签名证明原件和留存信任根验证成功。保留的错误日志已去除临时签名 URL。

| 本机材料 | SHA-256 |
| --- | --- |
| `compare-python.py` | `e8e04efdcd8addbf26e150f97e95d4464d87e56a09b5056bee4637e0318439ba` |
| `comparison.json` | `0d73a0e76bade1001da9872f67a594314a7d69b6c485e74e2c20917a68669508` |
| `runtime-imports.stderr` | `3066493869fc7cb1567039eac5cd596dfc5cf83a09e7aaf18f689bf5db6532cf` |
| `install-api-bundle.jsonl` | `de1e68d97ab15bc206b6da7aee5503e42a6e5fd8861798d828033ed97f6dfc8a` |
| `full-api-bundle.jsonl` | `edfdcb1d1a55c4224c2ece46a95dd1ff0403253378b910d18262a3498a43e9ac` |
| `trusted-root.jsonl` | `65ca537f6ed8a47fd0e560c421baa1f6c1efb8b25fc200d8c5c02c0e92eb2b9c` |
| `install-offline-verified.json`、`full-offline-verified.json` | `7c158dee9b49d09008d45ae6b3b8e2ee0d1e801d83c39e618e0eb399e8d6901a` |
| `libffi-3.4.6-upstream-LICENSE.txt` | `67894089811f93fca47a76f85e017da6f8582d4ba0905963c6e0f1ad6df7a195` |
| `full-LICENSE.libffi.txt` | `deaf3a42effb551a5b140fa9afefed183a27f1341c6d1bf430d106a5e6931fc0` |

Python 发布身份、选定本机文件、`_ctypes` 与 libffi 来源已查清。证明验证仍依赖 GitHub 签发及 Sigstore 信任根，来源配方与静态库的对应依赖已签名发布和构建清单。没有重建发布二进制，也没有确认本机历史安装收据。未来一次真实构建须固定或重核实际启动文件与读取的字节码，并审阅宿主信任。L3 总体保持 **`not-accepted`**，剩余对象是 target 发布清单的信任范围、Apple Git 选择链、Cargo 解析数据来源与许可，以及固定 macOS / dyld / libproc 的信任范围。target 仍未安装，未生成真实 v0.2 root、构建 Linux 制品或执行 solver。
