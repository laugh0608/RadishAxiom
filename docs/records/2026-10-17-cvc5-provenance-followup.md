# cvc5 E0 公开来源有界复核

日期：2026-10-17。范围：原精确 CLI 的 B1 / B2 来源缺口复核。接续[依赖与许可补证](2026-10-17-cvc5-cli-dependencies.md)，没有安装、构建、解包执行、运行 solver / 探针或变更系统配置。

## 结论与精确对象

**原 CLI 保持 `not-accepted`，B1 / B2 / B3 均未闭合。** 本批取得四份公开响应原字节，确认公开 artifact 查询本次返回空列表，并将固定提交的依赖缓存配方绑定到前批 tree。两项精确摘要 attestation 查询均返回 HTTP 404，未取得可关联实际构建输入的声明。不能把空列表或 404 写成“上游从未提供来源材料”。

对象没有变更：`cvc5-1.3.4` / source commit `f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341`，ZIP SHA-256 `2a4c108367f20b0c8990abd6b9535a5d62e08908d471d4671c00734e408f85bc`，其中 `bin/cvc5` SHA-256 `26fa94d71ecb3d4f1458eb06b9b9d4762fb3753cfb5cb9dca6f917fbf4dbe6c7`。本批通过前批观察摘要绑定该对象，没有再次执行或重新认证二进制。

## 实际取得的材料

[来源索引](cvc5-provenance-followup-2026-10-17/source-inputs.json)保存完整 URL、HTTP 状态、响应 Date、字节数、项目重算 SHA-256、角色与许可材料指向；[复核观察](cvc5-provenance-followup-2026-10-17/provenance-observation.json)绑定检查器与前批身份。原始响应仅保存在忽略目录 `.tmp/cvc5-provenance-followup-2026-10-17/`，仓库仅保存自有索引与观察，不复制上游源码。

| 公开请求 | 本次实际响应 | 可以确认的边界 |
| --- | --- | --- |
| [run 25505454189 artifacts](https://api.github.com/repos/cvc5/cvc5/actions/runs/25505454189/artifacts?per_page=100) | HTTP 200；32 bytes；`total_count=0`、`artifacts=[]`，无下一页 Link | 2026-10-17 12:26:59 UTC 响应未提供 artifact；不能排除历史清理、保留期限或其他来源渠道 |
| [ZIP 摘要 attestations](https://api.github.com/repos/cvc5/cvc5/attestations/sha256:2a4c108367f20b0c8990abd6b9535a5d62e08908d471d4671c00734e408f85bc) | HTTP 404；126 bytes；正文 `status=404`、`message=Not Found` | 本次匿名公开请求未取得声明；权限、接口可见性或端点行为等原因没有被排除 |
| [CLI 摘要 attestations](https://api.github.com/repos/cvc5/cvc5/attestations/sha256:26fa94d71ecb3d4f1458eb06b9b9d4762fb3753cfb5cb9dca6f917fbf4dbe6c7) | HTTP 404；126 bytes；与 ZIP 查询错误正文同字节 | 同上；错误正文不是 attestation，不作签名验证或存在性否定 |
| [固定提交 setup-cache/action.yml](https://raw.githubusercontent.com/cvc5/cvc5/f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341/.github/actions/setup-cache/action.yml) | HTTP 200；3,208 bytes；SHA-256 `4c3ab441581251da369270ce5a81569b5f527dcd83eaa1350ebc9ef64215817b`；Git blob 与前批 tree 一致 | 实际配方使用 `actions/cache@v5`，包括 `build-shared/deps` / `build-static/deps`；没有该次作业的 cache-hit、恢复内容或库身份结果 |

缓存源码的依赖 key 来自 `inputs.cache-key`、`runner.os` 及 `cmake/**` / `.github/**` 的内容摘要；ccache 另有按 commit 的 key 与恢复前缀。这说明检查具体恢复内容有意义，但不能仅由配方断言该次命中、污染或用了任何特定库版本。固定源码许可沿前批同 commit 的 `COPYING` / BSD-3-Clause 记录；没有将其正文重新纳入仓库。

本批没有取得该次 runner image version 或系统包清单，因此没有用当前 `ubuntu-22.04-arm` 镜像、当前 Ubuntu 包版本或发布日期推定原构建系统库身份。前批详细 job log 的 HTTP 403 路径保持停止，**没有再次访问、寻求凭据或联系上游**。

## 四个配方归档的真实状态

原配方的 CaDiCaL、SymFPU、LibPoly、GMP 四个候选 URL 与声明摘要保留在来源索引，并逐项核对前批配方观察。它们的 `status` 均为 `not-obtained`，项目重算归档摘要和实际 CLI 关联均为 `null`。

下载命令曾进入 `require_escalated` 审批等待，工具在 614.5 秒后返回 `aborted by user`，没有成功输出或网络失败输出。后续本地 inventory 仅发现四份已完成响应与 `retrieval.json`，没有归档或 `archive-retrieval.json`。因此本批将其记录为“审批等待中止，未观察到下载执行”，不能归因为上游网络错误，也不能称为已经下载、摘要匹配或许可扫描通过。没有重试、换源、解析 tar 或运行归档内容。

即使未来四个原包下载且声明摘要匹配，也只证明取得了固定配方原包；仍须有该次构建的选择 / cache 结果、可能 patch 与 CLI 摘要的关联，才能补足 B2。B1 的精确 libedit / tinfo / glibc / compiler runtime 及实际间接链接组成仍需独立材料。

## 后续停止线

本轮有限公开复核到此结束。已有材料不足以给原 CLI 生成 accepted payload，也不足以确认静态再分发义务完整满足。若后续选择另行准备同版本、可追溯输入的构建候选，应按新的工具身份与方案确认范围；不能把本批检查通过当作构建、替换 payload 或执行授权。

## 离线复核与验证

[检查脚本](../../scripts/check-cvc5-provenance-followup.py)只读四份本地原字节，核对来源集合、精确 URL / HTTP 状态、字节数 / 摘要、artifact 数量与列表一致、404 的错误正文、固定缓存源码 Git blob、前批观察与 CLI 身份，以及四个未取得归档的原配方 pin。不联网、不执行载荷，也不产生公共 acceptance 格式。HTTP 状态是本机获取时保存的观察，不是签名认证；重跑离线检查不重新证明远程状态。

```bash
python3 scripts/test-cvc5-provenance-followup.py
python3 scripts/check-cvc5-provenance-followup.py \
  .tmp/cvc5-provenance-followup-2026-10-17 \
  .tmp/cvc5-provenance-followup-2026-10-17/provenance-observation-recheck.json
```

输出路径须尚不存在；还需保留前批 `.tmp/solver-cli-licenses-2026-10-17/cvc5-tree.json`。该 tree 原字节通过前批索引摘要复核，再核对新增缓存源码的 Git blob。重新获取时不能为了迁就新的远程响应而改原摘要。

实际验证：8 项测试通过，负例覆盖错误 artifact 数量、隐藏后续页、404 正文混淆、越界路径、摘要 / HTTP 状态不一致、超限输入、符号链接、FIFO 非普通文件，以及归档 URL / pin / 取得状态 / 重算摘要 / CLI 关联篡改；四份真实原字节的离线复核通过。结果只支持本记录的静态观察，未补齐 B1 / B2 / B3。本批文件未提交、未推送；仓库级最终检查由主任务统一记录。
