# Linux headers 4.19.88 Git 元数据实际取证

日期：2026-09-29（Asia/Shanghai）

基线：`72103e1`，`dev`。用途：记录两个已授权请求、沙盒失败后的单次获准重试及本地复核结果。不包含独立验签、来源接受、原始 kernel 制作链或许可验收。

## 授权与执行

项目所有者在审阅[精确请求方案](linux-headers-review-2026-09-29.md#已准备尚未执行的认证取证)后回复“提交更改，授权执行”。先将上一批九个路径提交为 `72103e1`，再以排他创建方式建立 `.tmp/linux-headers-git-metadata-84bd6f8-20260929/`，保存与仓库内[计划](linux-headers-git-metadata-plan-2026-09-29.json)逐字一致的 `fetch-plan.json`，运行：

```bash
python3 docs/records/rust-linux-input-review/fetch-linux-headers-git-metadata.py --execute-authorized
```

首次两项均为 curl `7` / HTTP `000` / 空正文，stderr 为本机代理 `127.0.0.1:10808` 连接失败。保留原日志后申请并获准在沙盒外对相同 URL 各重试一次；没有覆盖首次记录，也没有自动重试。第二次使用原 `fetch-mpc-mpfr-inputs.py` 的 `fetch(name, 2)`，先比对原计划，再由既有方法要求首次确为连接失败、HTTP `000`、空正文；目标及目录仍来自原路由。调用过程为：

```python
assert json.loads((m.DIRECTORY / 'fetch-plan.json').read_bytes()) == m.plan()
m.fetch.DIRECTORY, m.fetch.TARGETS = m.DIRECTORY, m.TARGETS
raise SystemExit(max(m.fetch.fetch(name, 2) for name in m.TARGETS))
```

其中 `m` 为通过 `importlib` 加载的原 `fetch-linux-headers-git-metadata.py`。这是实际重试调用的记录，不是新增通用重试授权；原路由及原计划没有改写。四次调用的精确 curl argv、起止时间、工具摘要和所有流摘要已保留在[完整报告](linux-headers-git-metadata-2026-09-29.json)及本机输入库中。

两次成功请求各仅执行一次，仍不使用凭据、不跳转、不追踪响应 URL；正文上限分别为 64 KiB / 256 KiB，curl 60 秒 / 父进程 65 秒。成功请求合计正文 1,756 bytes；进程已退出。

| 目标 | 第二次结果 | 字节数 | SHA-256 |
| --- | --- | --- | --- |
| `https://api.github.com/repos/sabotage-linux/kernel-headers/git/ref/tags/v4.19.88` | curl 0 / HTTP 200 | 410 | `e03c1e27b167f7756eee46934dbd44fced50b8e9a078a1ea0cf1c1fd08a4950a` |
| `https://api.github.com/repos/sabotage-linux/kernel-headers/git/commits/fefadd9e4e093f776cd14ee3685a80eb4ca000f4` | curl 0 / HTTP 200 | 1,346 | `7618b00fef4319d0b3fbff278352109c98a4fb0f6d64e0e3bc461bd42a5960ff` |

## 实际声明及其边界

响应显示：

- `refs/tags/v4.19.88` 的 `object.type = commit`，直接指向 `fefadd9e4e093f776cd14ee3685a80eb4ca000f4`。这是本次 GitHub ref 记录中的轻量 tag 关系，没有附注 tag 对象。
- commit `sha` 与该目标一致；声明 tree 为 `5c2c118c724ac90d4bd52d26f34ffa0868dd7cf9`，唯一 parent 为 `5cd300037eefe78412a9786097d8f913ea6cfd86`，message 为 `Update version in README`。
- author / committer 均声明时间 `2019-12-13T03:48:06Z`。这是对象元数据声明，不是已证实的历史发生时间或签署时点。
- `verification.verified = false`、`reason = unsigned`，`signature`、`payload`、`verified_at` 均为 null。

因此，本批没有获得 tag / commit 原始签名材料，没有可在本批进行的独立签名验证。`unsigned` 是 GitHub 返回的声明，不扩张为“所有渠道永远没有任何签名”。没有还原原始 Git commit / tree 对象或验证 codeload 归档与声明 tree 的 Git 对象对应；现有归档内容比较仍只支持[前批已记录的关系](linux-headers-inputs-2026-09-25.md)。

保持 `source_acceptance = not-assessed`。不能因两个 HTTPS 请求成功就接受原包，也不能把相同 commit 声明升级为作者认证或可复现制作链。866 项投影、97 项无 SPDX、11 项标记不含 syscall 例外字样、额外 `../linux` 输入、未固定 tag 的打包和不完整补丁链，均按[全文审阅](linux-headers-review-2026-09-29.md)保留。

本批已到原方案停止线：没有继续获取返回的 parent、tree、tag 对象、完整仓库或 kernel 原包，没有请求其他域名。下一步需要审阅保持同一精确原包的分发来源候选及原 kernel 制作 / 许可取证方案；任何来源接受或信任变化仍须明确决定，不自动替换版本、放宽摘要规则或把缺口隐藏为 fallback。

## 离线复核与留存

[inspect-linux-headers-git-metadata.py](inspect-linux-headers-git-metadata.py)检查原计划、四次 argv / 方法 / 流身份、首次连接失败条件、第二次固定正文及声明一致性；所有结果仍为诊断。新增[七项合成检查](check-linux-headers-git-metadata.py)覆盖无签名不升级为接受、ref / commit 漂移、附注 tag 变化、API verified 声明变化、parent / tree 格式、计划漂移和流篡改拒绝。

- 新增 7 项、前批审阅 / 请求边界 11 项、留存 7 项，共 25 项通过。
- [留存 manifest](linux-headers-git-metadata-retention-manifest-2026-09-29.json)：7,028 bytes，SHA-256 `e1183f5f142568242038e7eb435b2b949477ab4e8757b9a4589560462a8c382a`。
- 本机 `artifacts/source-inputs/linux-headers-git-metadata-72103e1-20260929/`：26 路径 / 19 对象，对象合计 50,825 bytes，包含两次失败、两次成功、原计划和全部直接重放方法。
- 恢复到 `.tmp/linux-headers-git-metadata-restore-20260929/` 后逐项字节一致；使用当前仓库方法读取恢复的原始输入，完整 JSON 报告与原报告逐字节一致，见[留存结果](linux-headers-git-metadata-retention-2026-09-29.json)。这是本机恢复核对，不是异盘备份，也不是从恢复目录重建产品。

复核命令不联网：

```bash
python3 docs/records/rust-linux-input-review/check-linux-headers-git-metadata.py
python3 docs/records/rust-linux-input-review/check-linux-headers-review.py
python3 docs/records/rust-linux-input-review/check-musl-retention.py
python3 docs/records/rust-linux-input-review/inspect-linux-headers-git-metadata.py --directory .tmp/linux-headers-git-metadata-restore-20260929/.tmp/linux-headers-git-metadata-84bd6f8-20260929
```

外部影响仅上述公开 HTTPS 请求。没有依赖安装、容器、上游脚本执行、外部验签、产品构建 / 安装、推送或远程写入；未运行 Rust / CI。原材料和恢复目录保留，没有后台进程。本批请求及重试授权已消耗完毕，不延续为后续获取权限。

仓库检查通过（1,312 个文件），`git diff --check` 通过。前批已按要求提交，本批执行结果及同步文档共九个路径尚未提交；`dev` 相对本地 `origin/dev` 记录领先四个提交，未刷新远端状态。
