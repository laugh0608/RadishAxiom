# GMP v2 第二次受限执行记录

日期：2026-09-25（Asia/Shanghai）。基线：`dev` / `6852a43`，ahead 11；启动时 13 个本任务文件改动未提交，均保留。

用途：记录本次授权的一次真实诊断、失败停止、原始材料留存与离线重放。本文不修改 v1 / v2 历史方法，不接受来源，不授权重试或新的外部动作。

## 实际结果

项目所有者以“授权，继续推进”确认[第二次运行精确范围](gmp-auxiliary-expiry-review-2026-09-25.md#第二次运行的精确待授权范围)后，执行一次：

```bash
python3 docs/records/rust-linux-input-review/run-gmp-verification-v2.py --execute-authorized
```

实际目录为 `.tmp/gmp-verification-20260925-attempt2`，run ID 为 `627fd8f45b1340208c92719bc7d86157`。开始 `2026-09-25T12:36:56.635955+00:00`，结束 `2026-09-25T12:36:57.576962+00:00`，即北京时间 20:36:56–20:36:57，约 0.941 秒。入口退出 1，整批 `passed = false`，失败原因 `fixed certification status mismatch`。

| 步骤 | 实际观察 | 判定与后续 |
| --- | --- | --- |
| `filter` | GnuPG 退出 0，导出 1,501 bytes，主钥到期行与导入计数匹配，五个 packet 的主体 / 自认证包体未变 | v2 筛选判定通过，显式保留到期、自认证尚未检查、历史有效性未建立 |
| `certifications` | GnuPG 退出 0，stdout 637 bytes，status 160 bytes；状态序列超出预注册两种格式 | 完整联合判定失败，停止，不进入原包验签 |
| `verify`、`tampered-body`、`wrong-primary`、`missing-primary` | 未执行 | 不能声称原包签名匹配或负例通过 |

两个容器均正常退出，非 OOM；按完整 ID / ownership 检查后删除：

- `bc1b746b5c9b4172502870247f99928ecd4c315fb19183bf99de03a0ab4be055`
- `7812d7b1c3e2806f0ed088338774e531b2519a9408e05bbcd409ff8f6bffd24e`

仍使用既有固定镜像 `sha256:55063921d0e996f717092e07dce8041cb2376cc171a070bf9a0a38a5dd16c777` / GnuPG 2.4.7。17 条控制 / 执行命令、精确 CLI / socket / 镜像、时间、每步输入、资源参数、退出与清理均在 bundle 中。资源 / 隔离边界沿用已授权方案：无网络、只读根、非 root、drop ALL、no-new-privileges、1 CPU、128 MiB、32 PID、两个 16 MiB tmpfs，只有逐步 status 文件可写宿主；没有 pull、下载、安装、执行上游源码或改变核验时钟。

## 两处差异与结论边界

原始自认证状态恰好为：

```text
[GNUPG:] KEYEXPIRED 1736961163
[GNUPG:] KEY_CONSIDERED 343C2FF0FBEE5EC2EDBEF399F3599FF828C67298 0
[GNUPG:] KEYEXPIRED 1736961163
[GNUPG:] KEYEXPIRED 1736961163
```

v2 只预注册单行 `KEY_CONSIDERED`，或前置一个主钥到期行，因此上述四行被拒绝。没有去重、丢弃未知行、扩大白名单或重跑。

另外对同一 stdout 单独调用**未改动**的 colon 判定器，又复现 `expected explicit expired key and exact expiry`：原强摘要绑定包声明子钥到期为 `1736961679`，实际 `sub:e` 的字段 7 却列 `1736961163`，与主钥到期相同，早 516 秒。这是另一个独立差异，即使只放宽状态序列仍不能通过。主钥 / 子钥字段与两行 `sig:!` 原样留存；两行 `sig:!` 是工具实际输出观察，不是本项目完整联合判定通过。

“工具可能将子钥可用期限制到主钥到期”目前仅为待核实解释；本轮没有取得固定 GnuPG 的相应语义依据，不将其写成已确认事实，也不将输入绑定包或输出字段归一化。下一步应先完成这两处工具语义的本地审阅，再准备可审阅的独立判定修订和测试；必要的新下载、容器 / 真实验签范围仍须先明确并另行授权。本次单次运行授权已消耗，不授权自动续跑或第三次尝试。

GnuPG 的自认证检查命令实际执行过，但 GMP 原包分离签名尚未验证。2023 年签署时点仍是签名内声明，2025 年到期不能直接推导其历史无效；历史有效性仍未建立。有限公钥快照、未认证第三方撤销声明、全渠道撤销 / 最新性缺口、身份页与工具 / 宿主 / 时间可信假设均沿用原方案。GMP 来源仍为 `not-assessed`，不继承 MPFR / musl / MPC 接受结果。

## 留存与重放

[机器复核](gmp-verification-attempt2-2026-09-25.json)由[只读复核入口](inspect-gmp-certification-attempt.py)生成，固定 bundle / 原结果摘要，读回归档输入与 27 份原执行方法，重放 17 条命令的预检、两次创建 / 启动 / 状态检查 / 删除，再复现筛选通过与两处拒绝。它不会调用 Docker / GnuPG，不执行 bundle 内源码，也不是独立密码学验证。

| 材料 | bytes | SHA-256 |
| --- | ---: | --- |
| 原始 `result.json` | 62,201 | `1e3a403d764bd5390d31d1fb8d1370de62c73c4f14c047b2daf7f8a28d74c92a` |
| `.tmp/gmp-verification-execution-20260925-attempt2.json` | 6,101,428 | `495ce3fb361747d09626f1eb0c55f0386a4a0e08f53a6901ecdd08d410e794a7` |
| 留存 manifest | 2,466 | `38ead8a25462c048f3df15d2c4f9f399671014a570fbf7861091eceb3f23d5b0` |

[留存 manifest](gmp-verification-retention-manifest2-2026-09-25.json)覆盖 bundle、v2 入口 / 收集器 / 方案 / 测试、本轮只读复核 / 测试 / 报告，共 8 路径 / 8 对象 / 6,177,457 bytes；bundle 内已带输入、原始日志及实际方法。持久库为 `artifacts/source-inputs/gmp-verification-6852a43-20260925-attempt2`，恢复目录为 `.tmp/gmp-verification-restore-20260925-attempt2`。[恢复报告](gmp-verification-retention2-2026-09-25.json)确认所有字节对应；从恢复 bundle 重算的机器复核报告逐字节一致。仅本机持久留存，未核实异盘备份。

```bash
python3 docs/records/rust-linux-input-review/collect-gmp-verification-v2.py \
  --replay .tmp/gmp-verification-execution-20260925-attempt2.json \
  --sha256 495ce3fb361747d09626f1eb0c55f0386a4a0e08f53a6901ecdd08d410e794a7
python3 docs/records/rust-linux-input-review/inspect-gmp-certification-attempt.py \
  --bundle .tmp/gmp-verification-restore-20260925-attempt2/.tmp/gmp-verification-execution-20260925-attempt2.json
python3 docs/records/rust-linux-input-review/check-gmp-certification-attempt.py
./scripts/check-repo.sh
git diff --check
```

收集器的失败留存判定保持 `failed-run-retained` / `replayed_success = false`；17 条日志的详细一致性检查由上述固定失败复核负责，不能误读为成功的六步重放。

## 验证与工作区

新增 7 项合成检查通过，覆盖两处拒绝与未接受边界、状态增删 / 乱序 / 错误 flags / 未知撤销 / 超限、异常退出、原声明到期值变回时拒绝错误归因、colon 损坏、材料 / 观察时点绑定、禁止放宽历史判定后继续复核。测试使用合成公钥 / UID，不运行外部工具。

仓库检查与 `git diff --check` 通过。未改动原执行方法，因此没有重跑此前已通过的 86 项 GMP 准备 / 导出回归、Rust / 产品构建或 CI。v1 首次失败、v2 预注册方案和本次实际结果分别留存，不改写历史材料。

本次 6 个新增文件和当前状态 / 索引更新连同前序改动尚未提交；`dev` ahead 11，未推送。两个任务容器已删除，输入 / 日志 / 派生钥环 / 方法和本机持久库保留；未新增下载、安装、来源接受或第三次执行。GCC / Binutils 继续阻断完整 source lock 和安装；headers 内容对应核对仍未认证来源。
