# 2026-11-22 AX-B01 G0 无盘首启宿主部署

项目所有者授权为已固定的无盘首启制品部署专用账号、组和受保护路径。源码与前批复核已提交为 `3f7914334064a8e36204f11d002226eec9fdbdd5`，完整 Git 树为 `412c5e97a3289df9019b3aeee8836315edc4755f`。独立比对了提交中的构建材料、原构建回执与实际部署字节。 [无盘首启制品与离线复核](2026-11-22-ax-b01-g0-diskless-first-boot.md)

## 部署结果

| 项目 | 已观察的状态 |
| --- | --- |
| 执行主体 | 新建 `_raxcg0` 与同名主组，UID 和 GID 均为 `850`。该账号的登录 shell 为 `/usr/bin/false`，home 为 `/var/empty`，`IsHidden=1`，认证已禁用，实际查询确认不属于 `admin` |
| 宿主路径 | 已创建 `/private/var/db/radishaxiom/ax-b01-g0/`。项目父目录、专用根及 `boot/` 均为 `root:wheel`、`0755`，`records/` 为 `_raxcg0:_raxcg0`、`0700`。祖先与交付树的 `ls -lde` 读回未出现额外 ACL |
| 固定制品 | `Image` 和 `initramfs.cpio.gz` 为 `root:wheel`、`0444`，`g0-first-boot` 为 `root:wheel`、`0555`。三个单链接普通文件的长度和 SHA-256 均与原构建回执匹配；已部署启动器严格验签通过，签名内只含 `com.apple.security.virtualization=true` |
| 普通开发主体 | 在普通宿主上以 UID `501`、GID `20` 运行七项实际检查。三个制品的不截断写打开和四个目录的独占空文件创建均返回 `EACCES`。制品摘要与文件身份保持一致，未留下探针文件 |

## 实际身份与前置检查

从工作目录 `/` 使用 `sudo` 切换到 `_raxcg0` 及同名组。进程的真实和有效 UID/GID 均为 `850`。该进程逐段确认了八个目录的所有者、模式及无符号链接、无额外 ACL，确认对 `records/` 有写入和遍历权限，并逐文件读回单链接、模式、长度、摘要和签名。普通开发身份的防写试验在 Codex 沙箱之外完成。

| 固定制品 | bytes | 实际身份重算的 SHA-256 |
| --- | ---: | --- |
| `Image` | 36,306,944 | `a2cecb9b6fdbd83e87bd43c8040de67300d5b8dde1fc50c34714faa272888f17` |
| `initramfs.cpio.gz` | 1,801,852 | `a6fb5c3b93fe38dab1ab68e478501c723200e7ade9d8ef3af74947272b0a42cb` |
| `g0-first-boot` | 81,728 | `ae3391bb1639f4675fa1102f19a5290b0043780ed50b59c29604b764858a65f3` |

经 `sudo` 切换的进程带入了四个额外组 `12`、`61`、`701`、`100`。已固定启动器的 `--preflight-paths` 返回 1（`execution credentials mismatch`）。系统 Perl 降权试验未通过凭据读回，`chroot` 执行方式以 137 结束且未返回凭据。临时原生探针的 `setgid(850)`、`setgroups(1, [850])` 和 `setuid(850)` 均成功，但随后 `getgroups` 仍返回 `850,12,61,701,100`。该探针在自身守卫处结束，部署的启动器、组策略和路径权限均按原方案保留。

## 回执与恢复条件

本机忽略目录 `.tmp/ax-b01-g0-deploy-20261122/` 保留了原始回执。

| 回执文件 | SHA-256 |
| --- | --- |
| `committed-to-installed.json` | `d14468a3be7dd441aebccdf5e3c0ca7518445771a2b1a749543b34abd4e7151b` |
| `initial-deploy-preflight.txt` | `1df763155195cef74755a311a6be14fd9245f3e52dcce52a61074ac24ea71b02` |
| `dedicated-preflight.txt` | `6b60dd46fd4db61ea95b91b87c18fe7cda18a99721838cad3a47f037a6f42787` |
| `narrowed-preflight.txt` | `6b513cd1154fa5789d55ec2313b0e877e05f9d74209090e4bbc721ca30c7df95` |
| `native-preflight.txt` | `d2bd0c977971fcb29200a0fe22e0f956d434b1cd7954ac85c4e7995825342433` |
| `target-identity-reads-from-root.txt` | `6d0da8c1d76413449da52824c9fe7b8f5a9692687b4bd28c5945f7cbc718780e` |
| `developer-write-probes.json` | `3c3e5cd703e2294ee643cdd58be76d8efaa340e48439a8a2c249d7ccaeef7baa` |

实际首启继续阻塞。恢复须先固定能满足现有凭据守卫的宿主执行方式，实测真实及有效 UID/GID 均为 `850`，附加组为空或仅为主组，并以拟用方式运行同一固定程序的 `--preflight-paths` 取得退出 0。若现宿主无法提供该凭据轮廓，须另行评审宿主或凭据方案。通过前置检查后，再单独审批一次实际无盘首启。

全程未启动虚拟机或容器，`records/first-boot.jsonl` 仍不存在，也未配置、构建或运行 solver。G0 保持 `evidence-insufficient-stop-before-wiring`；真实单向回执与实例退出、私有盘块和 inode 硬限、写别名、OCI 及 daemon 失联时的独立整树终止仍待相应资格。 [宿主决定](2026-11-22-ax-b01-g0-linux-host-decision.md) · [真实资格矩阵](../query/solver-local-cvc5-control-plane-plan.md#a3--a4--a7--a8-真实负向矩阵)
