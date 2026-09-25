# Linux builder 隔离安装切片审阅

最近文档复核：2026-09-25；原安装切片基线：`dev` / `3aa2dbb`。

状态：精确范围设计；来源前置未闭合，未获安装授权，命令未执行。

用途：把已有三包模拟与 Rust component 库存收敛为一次容器内安装的审阅对象。读者为项目所有者、工具来源与 runtime 维护者。不接受 ADR 0015、修改机器契约、构建产品、执行 checker 或提供完整 source lock。

来源事实沿用 [guest 来源审阅](checker-runtime-guest-source-build-review.md)与其中绑定的记录；本文只维护下一安装切片，不复制历史验签结论。诊断安装也必须通过下列来源前置，不能以“临时容器”豁免。

## 要解除的不确定性与前置

本切片回答：精确的三个 Debian 包与四个 Rust component 能否在固定镜像的新目录中完成离线安装，且实际包差异、安装文件与元数据符合已审阅输入。成功只形成安装诊断，不代表 builder acceptance、init 静态链接成功或产品 qualification。

| 前置 | 当前证据 | 执行前要求 |
| --- | --- | --- |
| 固定输入字节 | 三个 `.deb` 与两个 Rust archive 已取得并匹配各自来源链 | 在同一只读输入上重算长度 / 摘要；Rust 重跑完整归档检查；错误不进入提取 |
| Rust 签名身份 | 分离签名 SHA-512 的历史 GnuPG 核验通过；旧 key 自认证为 SHA-1 | 先决定并验收 key-binding policy；不得默许弱自认证或仅凭 GnuPG 退出 0 放行 |
| 镜像与执行工具 | 固定镜像的包 / 工具库存已有；来源未完整验收 | 明确镜像、公钥环、shell、tar / xz、coreutils、apt / dpkg、Python 与动态库的来源、版本及许可材料 |
| Rust 静态输入 | musl std 中 `libc.a`、`libunwind.a`、9 个 CRT 已盘点；[精确配方与 LLVM 源码 / 许可](records/rust-linux-input-review/source-recipes-2026-09-10.md)已取得 | [musl 原包 / 许可及四份补丁应用](records/rust-linux-input-review/musl-source-2026-09-10.md)已核对，但上游包签名与 key 自认证的 SHA-1 拒绝不变。[有条件 Debian 路线](records/rust-linux-input-review/musl-debian-auth-2026-09-10.md#项目所有者确认与执行顺位)已确认，身份材料、固定诊断工具及本机归档 / 恢复已补证；[九项真实验签](records/rust-linux-input-review/musl-verification-success-2026-09-16.md)通过，[来源审阅](records/rust-linux-input-review/musl-source-acceptance-review-2026-09-16.md)已获确认，该精确原包在固定工具 / 宿主与材料时点条件下的限定来源验收通过。其余六项已有[路线盘点](records/rust-linux-input-review/musl-remaining-sources-2026-09-16.md)，MPC / MPFR 原包与公钥已取得；MPFR 六项真实验签通过，[限定来源声明](records/rust-linux-input-review/mpfr-source-acceptance-review-2026-09-25.md)已获项目所有者确认，该精确原包限定来源接受通过；MPC 上游签名尚未验证，[固定 Debian 路线审阅](records/rust-linux-input-review/mpc-source-acceptance-review-2026-09-25.md)已完成、限定来源声明待确认；其余来源及 upstream binary 到实际构建输入的关联继续待补，不能据此安装 |
| Rust 宿主依赖 | 14 个 ELF 的动态段已有只读观察 | 核对实际 loader / 系统库路径、链接目标、包归属、字节、符号版本与来源；同名包不等于已满足 |
| 授权与环境 | 目前只授权诊断和方案准备 | 以上前置收口后，按本文命令、容器、目录、副作用和清理范围取得当前任务的安装授权；镜像缺失时不 pull |

ADR 0015 与维护投入已于 2026-09-10 独立确认；它们不自动批准安装，也不替代上述来源验收。kernel 原始 tag、最终 config 与对应分发材料继续影响 kernel source / build 验收；本安装切片不提取或构建 kernel。

## 固定目标与预计影响

| 项目 | 精确范围 |
| --- | --- |
| 执行环境 | OrbStack Docker context `orbstack`；Linux arm64；本地 image ID `sha256:a339861ae23e9abb272cea45dfafde21760d2ce6577a70f8a926153677902663`；执行前复核实际 image ID、架构和镜像库存 |
| 容器 | `radishaxiom-linux-install-3aa2dbb-20260910`；名称已占用则停止，不删除同名已有容器；无网络、不挂 Docker socket、不挂用户目录 |
| Debian 增量 | `flex=2.6.4-8.2`、`bison=2:3.8.2+dfsg-1+b1`、`bc=1.07.1-3`，全部 arm64；只使用既有精确 `.deb`，不更新 apt 索引、不升级 / 移除、不装 recommends |
| Rust 增量 | `1.97.1`；GNU archive 选择 `rustc,cargo,rust-std-aarch64-unknown-linux-gnu`；musl archive 选择 `rust-std-aarch64-unknown-linux-musl` |
| 新前缀 | `/opt/radishaxiom/rust-1.97.1`；第一包之前必须不存在（含悬空 symlink）；第二包之前必须恰好具有本次第一包的三个 component 和已核对文件 |
| 写入范围 | 仅容器可写层：apt / dpkg 状态、alternatives / menu、`/work` 提取目录及新 prefix；宿主两个缓存目录只读挂载；宿主仅留任务日志 |
| 时间与资源 | 预计 5–10 分钟；容器内总命令 `timeout --kill-after=10s 720s`；2 CPU、2 GiB memory 且 memory+swap 同为 2 GiB、128 pids。它们是安装诊断预算，与产品 guest 128 MiB 无关 |
| 磁盘 | 两包 tar 流合计 1,847,745,536 bytes，选定安装文件合计 696,197,245 bytes；另有目录、包配置、日志与镜像层开销。执行前容器后端至少留 4 GiB 可用空间；这是容量预检，不是已强制的磁盘上限 |

Debian 安装会运行 maintainer scripts：bison 可能删除旧 manpage 并设置 `yacc` alternatives；bc 在条件满足时更新 menu；flex 使用 debconf 前置。实际 dpkg triggers 也须留存，不能从三包摘要推断没有其他配置动作。

Rust 安装器先处理 legacy / 当前 component manifest；旧 legacy manifest 的绝对路径可能驱动删除。因此只允许全新前缀，第二步还要核对本次生成的 manifest，不能将“缺少同名 component”当成整个旧 prefix 安全。两次显式 `--disable-ldconfig`，避免安装器默认运行 `ldconfig` 或写 `/etc/ld.so.conf.d/`；不修改宿主 PATH、rustup、项目依赖或 lockfile。

## 待授权命令

下列是审阅命令，未执行。启动前先确认来源表全部具备可复核结论；保存实际执行输入、命令文本及摘要，不能从本文抽出某段独立运行。宿主日志目录候选为 `.tmp/linux-install-3aa2dbb-20260910/`，必须以独占创建方式建立；用独立 stdout / stderr 文件和退出码留存，禁止日志管道掩盖失败。

容器启动参数如下；执行者通过保持打开的标准输入逐段发送下列命令，先读取并核对本段实际输出，再发送下一段。显式 root 只用于容器内 dpkg 安装；capability 限于 CHOWN、DAC_OVERRIDE、FOWNER、SETUID、SETGID。若此集合不足，保留失败后重新审阅，不自动追加权限。

```bash
docker --context orbstack run --rm --init \
  --name radishaxiom-linux-install-3aa2dbb-20260910 \
  --pull=never --platform=linux/arm64 --network=none \
  --cap-drop=ALL --cap-add=CHOWN --cap-add=DAC_OVERRIDE \
  --cap-add=FOWNER --cap-add=SETUID --cap-add=SETGID \
  --security-opt=no-new-privileges --user=0:0 \
  --pids-limit=128 --memory=2g --memory-swap=2g --cpus=2 \
  --stop-timeout=10 --interactive \
  --mount type=bind,src=/Users/luobo/Code/RadishAxiom/.tmp/linux-builder-chain-8cc7406,dst=/debian-inputs,readonly \
  --mount type=bind,src=/Users/luobo/Code/RadishAxiom/.tmp/rust-linux-inputs-bb014fd,dst=/rust-inputs,readonly \
  --entrypoint=/usr/bin/timeout \
  sha256:a339861ae23e9abb272cea45dfafde21760d2ce6577a70f8a926153677902663 \
  --kill-after=10s 720s /bin/bash -s
```

以下为逐步执行方案，不是无人值守脚本。执行者在安装前后完成下一节库存核对，不自动登记 accepted。第一段只准备容器目录并模拟，不安装：

```bash
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL=C
export DEBIAN_FRONTEND=noninteractive
umask 022

test ! -e /opt/radishaxiom/rust-1.97.1
test ! -L /opt/radishaxiom/rust-1.97.1
test ! -e /work
test ! -L /work
mkdir /work

/usr/bin/apt-get --simulate --no-download --no-install-recommends --no-upgrade --no-remove install \
  /debian-inputs/flex_2.6.4-8.2_arm64.deb \
  /debian-inputs/bison_3.8.2+dfsg-1+b1_arm64.deb \
  /debian-inputs/bc_1.07.1-3_arm64.deb
```

读取模拟结果并与固定包基线比较，必须仅新增精确三包，不能只按退出码继续。确认后才向同一容器发送第二段：

```bash
/usr/bin/apt-get --yes --no-download --no-install-recommends --no-upgrade --no-remove install \
  /debian-inputs/flex_2.6.4-8.2_arm64.deb \
  /debian-inputs/bison_3.8.2+dfsg-1+b1_arm64.deb \
  /debian-inputs/bc_1.07.1-3_arm64.deb

# 仅适用于已重验完整库存、无 link / 特殊成员的两份精确 Rust archive。
/usr/bin/tar --extract --xz --no-same-owner --no-same-permissions \
  --file=/rust-inputs/rust-1.97.1-aarch64-unknown-linux-gnu.tar.xz --directory=/work
/usr/bin/tar --extract --xz --no-same-owner --no-same-permissions \
  --file=/rust-inputs/rust-std-1.97.1-aarch64-unknown-linux-musl.tar.xz --directory=/work

/bin/sh /work/rust-1.97.1-aarch64-unknown-linux-gnu/install.sh \
  --prefix=/opt/radishaxiom/rust-1.97.1 \
  --components=rustc,cargo,rust-std-aarch64-unknown-linux-gnu --disable-ldconfig
```

核对 dpkg 差异、本次生成的三个 GNU component manifest、所有文件及新前缀边界。未取得实际符合结果时停止，不发送第二个安装器。确认后发送第三段：

```bash
/bin/sh /work/rust-std-1.97.1-aarch64-unknown-linux-musl/install.sh \
  --prefix=/opt/radishaxiom/rust-1.97.1 \
  --components=rust-std-aarch64-unknown-linux-musl --disable-ldconfig
```

**上述片段不能直接拼成无人值守脚本**：逐步核对是本方案的一部分；只有当前段实际符合才能执行下一段，文字说明不构成自动检查。安装授权覆盖同一方案下的这些只读核对，无须段间重复向用户申请。提取只在容器全新 `/work` 内进行，保留全部 archive 层级、不使用 `--strip-components`，不把 kernel 有链接 source archive 纳入同一策略。

## 验收、有限执行与清理

安装前重算两份 Rust archive 与三个 `.deb`，其固定摘要分别取 [Rust 库存](records/rust-linux-input-review/summary.json)和 [Debian 来源链](records/linux-builder-source-chain/payload-chain.json)；同时绑定这些记录自身的摘要与来源判定。不能让输入自行携带另一份“可信摘要”。重跑模拟须与固定 413 包基线逐项比较，拒绝额外安装、升级、移除或未知版本。

安装后交付：

1. dpkg 全量包清单及差异恰好为指定三包；全部状态为 installed、无未配置 / half-installed 项、`dpkg --audit` 无诊断，记录触发器与 alternatives 的实际变化。
2. prefix 只出现指定四个 component；GNU 146 个文件与 musl 66 个文件逐项核对路径、类型、权限、长度与内容摘要。安装器生成的 manifest / log / uninstall 元数据单列来源与内容，不能统统忽略“额外文件”。
3. 两包之间先校验 GNU 文件与 component manifest，拒绝前缀外路径、链接、未知 component 或非本次生成的旧安装状态；第二次安装后重新核对 GNU 文件，不能被覆盖或丢失。
4. 记录 loader / 库路径和符号版本等静态信息；不执行 `ldd`。本切片不执行新装 rustc / cargo / linker，也不编译。后续 `--version`、最小合成链接与产物 ELF 检查另列有限执行切片，不从“安装成功”推断它们成功。
5. 保存来源 gate、命令、实际时间、每一步退出码、stdout / stderr、包和文件差异；无安装回执时状态保持未验收。日志缺失、超时、OOM、配置不完整或差异越界都保留失败，禁止自动重跑、换镜像或加依赖。

正常退出由 `--rm` 删除容器和可写层；不 commit 镜像、不保留 volume，安装诊断的临时 prefix 因而不成为持久 builder。需持久构建环境时另行设计来源与保留方式。超时或通信中断时，以本次捕获的容器 ID 核实名称、镜像和创建身份，再 `docker --context orbstack stop --time=10` 该精确 ID；自动删除未完成时只移除同一已停止容器。不得依名称误删旧容器，不执行 prune 或删除输入缓存。

容器 daemon 无响应或删除失败时保留 ID 与错误并报告，不能宣称已清理。宿主日志保留；两个只读缓存及原始来源材料不删除。预计清理通常数秒，10 秒停止窗口无法收束时记为失败；安装 timeout 不冒充宿主级实时保证。
