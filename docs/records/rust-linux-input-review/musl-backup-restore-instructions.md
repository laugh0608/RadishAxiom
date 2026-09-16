# musl 来源材料备份恢复说明

用途：供项目所有者保管、转移及恢复 2026-09-16 已接受的固定 musl 来源材料。此包是私用复核材料，不是产品发行包或全部工具链备份。

## 内容与范围

- `RadishAxiom/`：提交 `aa13d7ce88a39177fa389adc9ddfe2068276fbb3` 的完整受版本控制文件快照，不含 `.git` 或提交历史；另附生成本压缩包的方法。
- 其中 `artifacts/source-inputs/musl-verifier-2fb2e70-20260912/`：132 个恢复路径所需的 87 个对象及原清单，包含完整 Sources、musl 原包、公钥与验证工具包。
- 其中 `.tmp/`：精确选定的首次 / 第二次验签和 smoke 原始编号日志、status、公开输入，以及固定 rootfs tar。没有打包用户 Docker 配置、整个缓存、其他未跟踪文件或 daemon 镜像库。
- `MANIFEST.json`：除自身之外每个文件的路径、长度、SHA-256 和模式；清单不提供独立签名身份保证。

备份不含其他 Rust / kernel 大型缓存，也不承诺在任意主机直接执行 GnuPG；动态重跑仍需要已审阅环境和明确授权。当前 Git 快照在后续六项依赖审阅之前，不能用本包声称包含之后的工作。

## 转移与完整性核对

请把 `.tar.gz` 和同名 `.tar.gz.sha256` 一起保存在私人云端或另一块介质。复制后从目标位置重新读取并核对 SHA-256；只有检查过目标副本，才能确认转移完整。Downloads 在本机，单独放在那里仍不是异盘备份。原项目内材料暂不清理。

在文件所在目录执行（以实际文件名为准）：

```bash
shasum -a 256 -c RadishAxiom-musl-source-aa13d7c-20260916.tar.gz.sha256
```

校验通过后，在不存在同名文件的新目录中解压；不覆盖现有项目，不执行包内的上游程序或安装器。以下 `-p` 保留文件模式，验签输入必须保持 `0444`；有些解压工具会自动添加 owner-write 位，导致严格复核拒绝。`.tmp` 中的记录也必须保留。

```bash
mkdir RadishAxiom-musl-restore
tar -xzpf RadishAxiom-musl-source-aa13d7c-20260916.tar.gz -C RadishAxiom-musl-restore
```

## 离线复核

需要现有 Python 标准库，无需 Docker 或联网。在解压后的 `RadishAxiom/` 目录中运行下列命令，并将 stdout 与 `docs/records/rust-linux-input-review/` 中对应 JSON 逐字节比较：

```bash
python3 docs/records/rust-linux-input-review/collect-musl-verification-execution.py --attempt 1
python3 docs/records/rust-linux-input-review/collect-musl-verification-execution.py --attempt 2
python3 docs/records/rust-linux-input-review/collect-musl-smoke-execution.py
```

它们分别对应 `musl-verification-execution-2026-09-16.json`、`musl-verification-success-2026-09-16.json`、`musl-verifier-smoke-execution-2026-09-12.json`。旧记录中的绝对宿主路径保留原执行身份；离线复核从恢复树读取实际文件，不要求向那些旧路径写入。

原 132 项输入的展开恢复继续使用归档中的 `retain-musl-verifier-inputs.py restore`，精确命令与四条静态复核见 `docs/records/rust-linux-input-review/musl-retention-2026-09-12.md`。恢复目标必须不存在；静态 LLVM 复核仍依赖原已审阅宿主工具，不能把复制成功当成环境也已恢复。

## Git 与共享

本仓单文件门禁为 10 MiB；大型压缩备份不进入普通 Git 历史，不分片绕过门禁。Git 保留方法、摘要、清单和审阅记录即可。本包含第三方源码、工具二进制及已有许可材料，默认私人保管；公开再分发需要单独核对源码提供与归属责任。没有自动上传、创建 Release 或引入 Git LFS。
