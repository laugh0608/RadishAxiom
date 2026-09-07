# Linux 构建包来源链与安装差异诊断

日期：2026-09-06；基线 `8cc7406`。用途：留存三个 Debian 构建包的签名索引 / 字节核验、安装脚本静态审阅、安装模拟与 Rust Linux 校验元数据。读者为构建与工具来源维护者。本记录不是产品工具 acceptance、安装回执或完整 builder source lock；没有安装、构建或执行包内程序。

## 已完成的核验

1. 对官方 bookworm [InRelease](InRelease) 使用固定镜像内 GnuPG `gpgv` 离线验证，退出 0；bookworm archive、bookworm stable release 和 trixie archive 三个主指纹均得到 `VALIDSIG`。记录要求前两个角色同时存在，不用单一额外签名替代它们。
2. 从已验证正文的 SHA-256 段取得 arm64 [Packages.xz](Packages.xz) 与 [Sources.xz](Sources.xz)，按固定 by-hash URL 下载，两者长度与摘要匹配。两份完整索引已留存，避免仅保留选中段落后无法复算签名绑定的摘要。
3. 核对前次候选中的 binary / source 版本、架构、长度、摘要和 pool 路径，再取得 3 个 `.deb`、3 个 `.dsc` 及 6 个 source archive / patch，合计 **6,265,137 bytes**；12 项长度与 SHA-256 全部匹配。[payload-chain.json](payload-chain.json)保留完整选择、来源及核验结果。
4. 只读检查 `.deb` 内的 control archive，包名、版本、Source、架构、依赖及冲突字段与签名 Packages 一致；安装脚本只读取，未执行。[control-inventory.json](control-inventory.json)保留每个控制文件的长度 / 摘要，不在仓库复制脚本正文。
5. 对相同固定镜像、三个精确本地 `.deb` 执行无网络安装模拟：**0 upgraded、3 newly installed、0 to remove**，不安装 recommends。[成功 stdout](install-simulation-attempt-2.stdout)为实际结果，不能当作已安装或配置成功。

核验入口是 [inspect-debian-source-chain.py](../../../scripts/inspect-debian-source-chain.py)，输出独立的诊断格式，明确 `acceptance = not-assessed`。它消费可信的本次 GnuPG 观察，再检查摘要链；它本身不是密码学验证器，也不能把任意提供的 GnuPG 状态 JSON 变成证明。10 项[合成检查](../../../scripts/check-debian-source-chain.py)使用明确标为 mock 的 GnuPG 记录，测试解析 / 拒绝和链上字节绑定，不能代替实际验签。

## 信任与时效边界

固定镜像仍为 `sha256:a339861ae23e9abb272cea45dfafde21760d2ce6577a70f8a926153677902663`；其前次库存包含 GnuPG `2.2.40`、`debian-archive-keyring=2023.3+deb12u2`。本轮实际 gpgv 路径 / binary 摘要、版本、公钥环原始 bytes（base64）及摘要、全部状态与验证正文见 [release-verification.json](release-verification.json)。公钥环来自该镜像，不读取或修改宿主 keyring。

完整主指纹与 [Debian FTP key 页面](https://ftp-master.debian.org/keys.html)核对：bookworm archive 为 `B8B80B5B623EAB6AD8775C45B7C5D7D6350947F8`，bookworm release 为 `4D64FEC119C2029067D6E791F8D2585B8783D481`；额外 trixie archive 指纹亦显式列入观察。该页面提醒不能仅凭页面建立信任；本记录的 bootstrap 仍依赖已盘点但未完整验收的镜像 / 公钥环及 HTTPS 页面。其链接的 key announcement 本轮返回 403，未把它写成已独立核对。没有完成镜像来源或 Web of Trust 验收。

Release 是 **Debian 12.15 / oldstable / bookworm，日期 2026-07-11**，未提供 `Valid-Until`。程序拒绝未来日期，并在存在有效期时检查过期；本次只能报告固定发布快照，没有从签名有效推出最新安全状态。没有读取 bookworm-security / updates 来组成新升级方案，也没有把旧镜像的所有包重新验收。

[apt-secure](https://manpages.debian.org/bookworm/apt/apt-secure.8.en.html)区分 archive 签名链与包级签名。本轮通过 Release → Sources 的摘要核对 `.dsc` 和其对应 source 文件，未独立验证各 `.dsc` 的 maintainer 签名，未对这些 source archive 逐文件做许可 / 漏洞审阅，未重新构建 `.deb`。来源一致不代表包内代码无缺陷或工具已经适用于产品。

## 安装脚本与实际模拟

| 包 | 精确版本 | 静态发现的相关动作 |
| --- | --- | --- |
| flex | `2.6.4-8.2` | debconf 是 **Pre-Depends**；`postinst` 多为无动作分支，`prerm` 在 remove / upgrade 时可能删除旧 `/usr/doc/flex` 符号链接；大量示例动作处于注释内，不按实际执行计入 |
| bison | `2:3.8.2+dfsg-1+b1` | `preinst` 删除旧 `/usr/share/man/man1/bison.1`；`postinst` 配置 `yacc` alternatives 及 manpage 从项，移除 / deconfigure 时撤销 alternative |
| bc | `1.07.1-3` | `postinst` / `postrm` 在存在命令时调用 `update-menus` |

这些动作是将来隔离安装的明确副作用，不是本轮已经发生的改变。源包许可来源仍沿用[精确候选](../linux-6.18.49-archive-inventory/builder-package-candidates.json)；实际脚本的单文件声明与打包总体声明需分别核对，未在此作分发许可结论。

首轮模拟因只读根文件系统下 `/tmp` 不可写而退出 100，保留 [stdout](install-simulation.stdout) / [stderr](install-simulation.stderr)。只增加 16 MiB `noexec,nosuid,nodev` tmpfs 后，第二次模拟退出 0，精确结果为只新增三包；未放宽禁止下载、升级或移除的选项。实际安装仍会执行 maintainer scripts，模拟不能替代配置 / 回滚测试。

## Rust Linux 元数据

取得的官方 [SHA-256 文件](rust-linux.sha256)给出：

```text
9a7a2c336b4787f1b72f6bab7c35d5b7af2fd03cbd39b4fc721466a70d402a7d  rust-1.97.1-aarch64-unknown-linux-gnu.tar.xz
```

入口沿用既有 registry，精确 URL 见 [observation.json](observation.json)。这是发布者摘要捕获，**未下载或重算 Rust payload，未验证其签名或检查 archive**；GNU host 包也不自动覆盖 musl target std / CRT / linker。未改动历史 registry 或 acceptance 记录。

## 输入、命令与复核

本轮只从官方 HTTPS URL 下载，固定 `--proto '=https' --tlsv1.2 --fail --location`。索引按已验签 SHA-256 地址取得；12 项包材料的精确下载命令在 [fetch-payloads.sh](fetch-payloads.sh)，每项上限 4 MiB / 60 秒。脚本不会从未审阅 manifest 自动取得任意 URL。源码和 `.deb` 留在忽略目录 `.tmp/linux-builder-chain-8cc7406/`；仓库只留存索引、公开验证材料、方法与诊断输出。源材料重跑需保留本地缓存或按固定 URL 重新取得并核对摘要。

在仓库根执行的验签命令：

```bash
docker --context orbstack run --rm --name radishaxiom-debian-release-8cc7406 \
  --pull=never --platform=linux/arm64 --network=none --read-only \
  --cap-drop=ALL --security-opt=no-new-privileges --pids-limit=64 \
  --memory=512m --cpus=1 --user=65534:65534 \
  --tmpfs=/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777 \
  --mount type=bind,src=/Users/luobo/Code/RadishAxiom/.tmp/linux-builder-chain-8cc7406,dst=/inputs,readonly \
  --interactive --entrypoint=/usr/bin/timeout \
  sha256:a339861ae23e9abb272cea45dfafde21760d2ce6577a70f8a926153677902663 \
  30s /bin/bash -s < docs/records/linux-builder-source-chain/verify-release.sh \
  > .tmp/linux-builder-chain-8cc7406/release-verification.json \
  2> .tmp/linux-builder-chain-8cc7406/release-verification.stderr
```

第二次 apt 模拟使用相同镜像、mount、资源与隔离选项；容器名为 `radishaxiom-debian-simulation-8cc7406-attempt-2`，省略 `--interactive`，timeout 后的实际命令为：

```bash
/usr/bin/apt-get --simulate --no-download --no-install-recommends --no-upgrade --no-remove install \
  /inputs/flex_2.6.4-8.2_arm64.deb \
  /inputs/bison_3.8.2+dfsg-1+b1_arm64.deb \
  /inputs/bc_1.07.1-3_arm64.deb
```

首轮除容器名省略 `-attempt-2`、未提供 tmpfs 外相同。两轮均没有真实安装；退出后按本任务容器名执行 `docker ps -a`，结果为空，容器与临时目录已删除。

主机侧最终核验与控制文件读取：

```bash
python3 scripts/inspect-debian-source-chain.py .tmp/linux-builder-chain-8cc7406 \
  --observed-at 2026-09-06T13:24:47+00:00 --verify-payloads \
  > .tmp/linux-builder-chain-8cc7406/payload-chain-final.json
python3 docs/records/linux-builder-source-chain/inspect-controls.py \
  .tmp/linux-builder-chain-8cc7406 > .tmp/linux-builder-chain-8cc7406/control-inventory-final.json
python3 scripts/check-debian-source-chain.py
./scripts/check-repo.sh
git diff --check
```

留存时将 `payload-chain-final.json` / `control-inventory-final.json` 原样复制为此目录的 `payload-chain.json` / `control-inventory.json`。本轮主机 Python 为 `3.14.5`；可信 GnuPG 观察、脚本摘要与机器包库存分别保留，不冒充独立 checker。此记录的脚本用于受控诊断，不用于处理任意用户输入或自动批准安装。

下一步补 Rust Linux payload / 静态目标材料、kernel 许可与 stable tag 对应审阅，并提出上述精确三包的隔离安装范围；正式安装、运行、工具 acceptance 和 ADR 0015 接受仍是不同动作。近期顺位以[当前状态](../../status/current.md)为准。
