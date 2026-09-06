# Linux 6.18.49 来源核验与候选 builder 盘点

日期：2026-09-06。基线：`dev` / `dc4de70`。本记录是诊断观察，不是 Axiom Evidence、工具 acceptance 或完整 source lock。

## 实际结果

- 官方 `linux-6.18.49.tar.xz` 为 154,627,808 bytes；本地 SHA-256 为 `ae826f33111fea6f1d279dde7299d7463c8dfd204aeb75a8fb5432bc60a28191`，与发布者摘要一致。
- 未压缩 tar 流经 GnuPG `2.2.40` 验证，第二次返回 0，产生一个 `VALIDSIG`，完整主指纹为 `647F28654894E3BD457199BE38DBBDC86092693E`。没有展开或执行源码。
- 第一次返回 2：keys.openpgp.org 返回的两个公钥没有 UID，GnuPG 跳过导入，最终 `No public key`。这不是签名有效性判定。输入、原验证脚本及 stdout / stderr 均保留；原脚本在管道失败后提前退出，tmpfs 内机器状态未导出，此缺失不能补写成实际结果。
- 第二次从固定 kernel 开发者公钥仓库镜像提交取得同一 Greg KH 公钥的完整 UID 版本。签名已指向 Greg KH，因此第二次只接受该完整指纹，未扩大 signer 集合。改进脚本保留失败管道的退出码与机器状态。未改变源码、签名或信任指纹，也未设置信任级别绕过失败。
- 隔离 keyring 显示 `TRUST_UNDEFINED`，其他公钥认证签名未核验。身份关联依赖已审阅的 kernel.org 完整指纹页面与 HTTPS；没有验证公钥仓库 commit 签名或完整 Web of Trust，也不证明不存在本记录之后的撤销。

原始材料、来源 URL、长度、摘要和退出码见 [observation.json](observation.json)，成功 / 失败输出见 [attempt-2.stdout.txt](attempt-2.stdout.txt)、[attempt-2.stderr.txt](attempt-2.stderr.txt)、[attempt-1.stdout.txt](attempt-1.stdout.txt)、[attempt-1.stderr.txt](attempt-1.stderr.txt)。公钥是公开验证材料，分离签名是公开发布认证材料；来源和固定版本见 observation，不包含私钥，不作为项目自有代码重新许可。

## 候选 builder

使用宿主已有 OrbStack Docker server `29.4.0` 和固定本地 `rust` 镜像，未 pull。镜像 ID / RepoDigest 见 observation；这是内容身份观察，不能替代上游镜像和各包的来源 / 许可证验收。

保留的 [builder-inventory.json](builder-inventory.json)由 [盘点入口](../../../scripts/inspect-linux-builder.py)产生，记录 Debian 12 arm64 的 413 个 dpkg 条目、source package / source version、工具探测退出状态及二进制摘要。Rust shim 与 rustup 所选 binary 分别记账。脚本拒绝非 Linux / 非 Debian、损坏或重复包行和超时，不会安装工具或声明验收。

| 项目 | 实际观察 | 判断 |
| --- | --- | --- |
| GCC / binutils | GCC `12.2.0-14+deb12u1`；binutils `2.40` | 需继续验收精确包来源及库 |
| make / xz / GnuPG | `4.3` / `5.4.1` / `2.2.40` | 本次实际使用 xz / GnuPG；工具仍属于未完整验收的诊断 TCB |
| Rust / Cargo | `1.96.1` | 与候选 `1.97.1` 不符，不作为 init builder |
| flex / bison / bc / Go | PATH 未找到 | kernel 前三项缺失；checker 的 Go 输入也未就绪 |
| kernel | `7.0.11-orbstack-00360-gc9bc4d96ac70` | 容器共享 OrbStack kernel，不是待构建产品 guest |

未接触兄弟项目容器或启动其 VM。盘点容器的 512 MiB 限额只约束此次诊断命令，不能代替 ADR 0015 的产品 guest 128 MiB 含义。

## 留存命令与隔离范围

以下是在仓库根执行过的命令，重跑需要重新确认精确本地镜像与运行授权。`--pull=never` 禁止隐式下载；入口来自主仓，未执行待验收源码。collector 的原始字节摘要记录在 observation；输入变化后应新建记录，不能覆盖历史观察。

```bash
docker --context orbstack run --rm \
  --name radishaxiom-builder-inventory-dc4de70-retained \
  --pull=never --platform=linux/arm64 --network=none --read-only \
  --cap-drop=ALL --security-opt=no-new-privileges \
  --pids-limit=64 --memory=512m --cpus=1 --user=65534:65534 \
  --interactive --entrypoint=/usr/bin/timeout \
  sha256:a339861ae23e9abb272cea45dfafde21760d2ce6577a70f8a926153677902663 \
  30s /usr/bin/python3 - < scripts/inspect-linux-builder.py \
  > .tmp/checker-linux-builder-inventory-dc4de70/inventory.json

docker --context orbstack run --rm \
  --name radishaxiom-linux-source-signature-dc4de70-attempt-2 \
  --pull=never --platform=linux/arm64 --network=none --read-only \
  --cap-drop=ALL --security-opt=no-new-privileges \
  --pids-limit=64 --memory=512m --cpus=1 --user=65534:65534 \
  --tmpfs=/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777 \
  --mount type=bind,src=/Users/luobo/Code/RadishAxiom/.tmp/linux-6.18.49-source-review-dc4de70,dst=/inputs,readonly \
  --interactive --entrypoint=/usr/bin/timeout \
  sha256:a339861ae23e9abb272cea45dfafde21760d2ce6577a70f8a926153677902663 \
  120s /bin/bash -s < docs/records/linux-6.18.49-source-review/verify.sh \
  > .tmp/linux-6.18.49-source-review-dc4de70/signature-attempt-2.stdout \
  2> .tmp/linux-6.18.49-source-review-dc4de70/signature-attempt-2.stderr
```

第一次验签使用相同参数，容器名为 `radishaxiom-linux-source-signature-dc4de70`，输入为本记录的 `verify-attempt-1.sh`，输出名为 `signature.stdout` / `signature.stderr`。首次公钥在输入目录名为 `gregkh.asc` / `sashal.asc`，在本记录加 `attempt-1-` 前缀保存。第二次输入使用 `gregkh-full.asc`。`verify.sh` 对解压流验证签名，对压缩文件核对固定 SHA-256。

下载使用 `curl --fail --location --proto '=https' --tlsv1.2`；source / signature 的请求上限为 180 秒、200 MiB，完整公钥为 30 秒、2 MiB；精确 URL 见 observation。完整公钥 transport 按 base64 严格解码。重跑需要把相应输入放入上述只读目录，并先校验 observation 中的材料摘要。

诊断结束后 `docker ps -a` 按本任务容器名过滤结果为空；容器及 tmpfs keyring 已自动删除，宿主 keyring 未修改。约 148 MiB 压缩源码及下载材料留在被忽略的 `.tmp/linux-6.18.49-source-review-dc4de70/`，未纳入 Git；小型复核材料已留存此目录。没有安装依赖、构建 kernel / init / checker、启动产品 VM、签名产品或写入远程状态。

## 下一验收边界

源码 archive 文件 / 路径 / 链接 / 许可证库存、未压缩 tar 长度与摘要、stable commit 对应关系、镜像及工具来源仍待闭合。旧 [tar 检查入口](../../../scripts/inspect-toolchain-tar.py)的源码摘要已进入历史 acceptance 生成链，不能直接增加 Linux profile 后重算旧记录。下一步先审阅检查入口的版本化方案及精确构建依赖清单，再取得缺失包 / 工具；未完成这些前不构建 guest。

本记录不接受 ADR 0015、init 语言、维护预算或公共契约迁移。现行能力仍以[当前状态](../../status/current.md)为准。

## 本地验证入口

```bash
python3 scripts/check-linux-builder-inventory.py
bash -n docs/records/linux-6.18.49-source-review/verify.sh
bash -n docs/records/linux-6.18.49-source-review/verify-attempt-1.sh
./scripts/check-repo.sh
git diff --check
```

盘点拒绝边界的六项测试与实际容器观察分别报告；语法检查不替代真实验签，仓库检查不提升来源验收等级。
