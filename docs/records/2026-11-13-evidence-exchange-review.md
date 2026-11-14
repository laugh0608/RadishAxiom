# Evidence 独立交换候选实施与离线复核

日期：2026-11-13（Asia/Shanghai）。基线：`dev` 的 `ed4f4d0`。启动时工作区干净，比本地记录的 `origin/dev` ahead 1；未 fetch。

所有者确认 C1–C6，授权本仓契约草案与离线验收材料，完成后审查和相关验证；分仓写入、真实 solver、公共发布及 P6 门禁不变，暂不提交或推送。本文记录实际工作和验证边界，契约正文见[独立交换审阅](../evidence/evidence-v0.2-independent-check-review.md)。

## 本批结果

- 新增独立 request / manifest / result v0.2 候选、backend / batch v0.2 候选、重放中止 v0.2 与组件策略 v0.1。生成目录共 56 个文件，包括五份 schema、规范协议向量、input-only 合成包、四份完整包的固定交换指纹及可审阅清单。
- request 增加 source binding，manifest 引用使用新的文档域 ID，调用方另外固定 request raw 和 batch raw。完整包检查来源清单与 Evidence execution 的身份、顺序、父项和精确主体。
- 中止 cause 采用闭合阶段／原因，单独绑定生产侧 component policy。Debug 诊断不作为语义判据；旧 Debug 中止不能改版本后直接使用。现有 Rust 读回未接入新格式。
- 原四份完整合成 Evidence 字节和文档域身份不变。测试封装显式重建新 backend 下的 batch、manifest 和 request；新的指纹与旧 Evidence 指纹分别校验。
- 四态形状向量使用明确标记的合成 checker 身份，没有实际 checker 运行。完整包导出不写 expected-result，独立产品结果仍待分仓产生。
- 仓库检查新增候选生成一致性与 16 项边界测试；既有 Rust 有限对照测试接入四包交换绑定和每包九项变异。没有引入依赖、lockfile 改动或生产执行路径。

旧 `contract.json`、`backend.json`、基础及后端固定指纹、Independent Check v0.1、ADR、IR 与旧 Evidence 保持原字节；不会因候选生成而覆盖旧登记。本批所有新机器字节位于单独的 `independent-check-v0.2` 审阅目录。

## 审查发现与修正

1. 完整包首轮检查失败，退出 101。原因是旧 Independent Check descriptor 的 format 词法不允许点号，而既有 query 使用 `axiom-smtlib2-qf-uflia-query0.3`。在 v0.2 候选中显式登记新的词法，保留 v0.1 原规则；补合法点号与非法路径、空段、大写及下划线负例。
2. 新旧协议兼容测试首次要求旧 request 返回 unsupported-version，实际旧严格入口先拒绝新增成员，得到 unknown-member。按旧入口真实行为修正测试期望，未改变旧实现；新版 request 的旧版本标签仍明确拒绝。
3. 设计复审发现单独记录 resource / limit 仍不足以区分生产组件策略与 checker 自身预算。新增 component-policy 原件、阶段限额全集及摘要／limit 交叉核对；不虚构当前组件未暴露的消耗计数。新 cause 的生产采集与映射继续待实施。
4. 固定指纹初次生成时，input-only batch 的 subject 曾使用整个 subject 对象；与现有 batch 的 IR 文档 ID 口径核对后修正，并加入明确的主体、P2 和全集检查。只清理了本任务生成且已核对摘要的过期 blob，不改旧产物。
5. 复审发现结构拒绝没有合法 IR / P2 或后端批次。增加 no-backend 分支并限定只含基础 S1–S3 模式；新增完整结构拒绝包，以及完整后端包重算交换身份后仍不能冒充 no-backend 的负例。纯 S1–S3 材料同样使用该分支，避免一个语义有两种来源表示。
6. 结果检查复核了四态优先级、所选 outcome 的完整 refs、输入摘要、接受所需检查类别、来源引用及信任政策；这些检查只约束交换结果，不替代各项语义的独立实现。

## 验证与证据边界

| 检查 | 实际结果 |
| --- | --- |
| 候选生成与字节 | 56 份生成文件只读一致；四份完整交换指纹保留既有 Evidence raw。 |
| Python 边界测试 | 16 项通过，覆盖规范字节／Unicode、旧版、闭合形状、来源 pin、缺件／错件、限额前置、中止／策略、四态、输入身份及信任政策。 |
| 完整合成包 | correct、wrong-add、wrong-drop-zero 各 132 份制品，pre-false 为 43 份。全部新交换绑定通过；每包九项重绑变异拒绝，共 36 项。 |
| 既有有限语义 | 四包仍有 28 个有限重放观察一致，四项生产结果变异被拒绝；原 Evidence 指纹不变。 |
| JSON Schema | 使用本机已有 `jsonschema 4.26.0`：五份 Draft 2020-12 schema 结构有效，16 份协议／中止／策略样例结构通过。未安装该包或增加项目依赖。 |

最终定向重跑退出 0：23 项 `evidence_review::` 全部通过，包含历史、来源、信任、旧 S1–S3 及新增交换检查。基础 Python 的 8 份向量通过、5 份部分文档拒绝；旧 Independent Check v0.1 的 27 份生成文件一致。仓库检查通过（3079 个文件），`git diff --check` 通过；针对旧 backend／基础登记、全部旧指纹、Independent Check v0.1、ADR 与 Cargo.lock 的 Git 差异为空。

收口复核了全部修改与未跟踪文件，未发现范围外文件、意外权限变化或敏感内容。所有验证进程已结束；候选 schema、摘要与资料不构成一般正确性证明。

测试使用 Python `3.14.5` 和已安装的 Rust `1.97.1-aarch64-apple-darwin`，`--locked --offline`。未运行真实 solver、独立 Go 产品 checker、跨平台／宿主资格、完整 M1 或 P6–P9；未把已生成的 schema、合成 four-state 或 Python 核对写成独立接受或 proof。此次没有变更 Rust 生产源码，未额外运行全 workspace 测试或 Clippy。

```sh
python3 -I -B scripts/generate-evidence-exchange-review.py --check
python3 -I -B scripts/test-evidence-exchange-review.py
python3 -I -B docs/evidence/evidence-v0.2-machine-contract/check_vectors.py
python3 -I -B scripts/generate-independent-check-contracts.py --check
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir evidence_review:: --lib --locked --offline -- --nocapture
./scripts/check-repo.sh
git diff --check
```

## 交接与工作区

本批最终完整合成导出保留于已忽略 `.tmp/evidence-exchange-review-2026-11-13-d`，含四个题目目录的只读交换输入与单独 authority 预期值；没有真实数据、凭据或实际独立回执。前期导出 `-b`、`-c` 是中间候选，不用于最终固定指纹；不将临时目录作为持久规范来源。持久复现入口、fixture 源码、输入和摘要均在本仓。

后续先审定本候选的正式字节与生产适配，再按精确提交／摘要在获授权的分仓任务实施。旧 checker 的产品 binary、source、acceptance 和发布状态不因本仓文档更新而重绑。真实来源资格和完整迁移仍单独验收。

首次收口时未暂存、提交、push、PR 或写远程状态；未创建分支或启动长期服务。当时保留本批未提交改动及原有一个未推送提交，P6 保持关闭。后续提交授权与复审如下。

## 提交前复审（2026-11-13）

所有者随后要求再次审查来源绑定、版本兼容、no-backend 和四态，问题直接修复验证后提交到 dev，暂不推送。启动时仍为 dev ahead 1，暂存区为空；承接上述本批文件，没有并行或范围外改动。提交授权不扩展真实 solver、分仓、公共发布或 P6。

新回归先复现了以下问题，再修复检查边界：

- 只检查 manifest 的 Evidence 版本标签，没有核对内部版本、profile 与摘要算法；现已交叉核对，旧版本换外壳不能通过。
- 删除 manifest descriptor 与 blob 后，可隐藏 Evidence 仍声明的制品；同时删掉 Evidence descriptor 时，还可隐藏 execution 或捕获封套仍引用的原件。现按两份清单、subject role、execution／工具及已取得来源封套的实际引用检查闭包。缺描述是矛盾，保留正确描述但缺字节仍为不足。
- no-backend 原先只看模式名。现重算条目身份与执行顺序，核对 kind、工具角色、目标种类、rule、输入输出角色；换标签但保留后端绑定不能绕过。
- 批次内唯一的 invocation 未必与捕获原件一致，批次生产策略也可能与 capture 不同。现将 invocation、request、proof_policy 与 solve 父项对回对应封套；重算批次和请求身份不能掩盖已知矛盾。
- 接受回执可以通过漏写 remaining_trust 删除 Evidence 依赖。本候选没有登记信任消除规则，现要求接受时保留 Evidence trust 全集；未允许的信任继续阻断接受。独立证明支持仍未新增。
- 已绑定非规范原件的合法 rejected 回执会被严格解析入口误拒绝；现分别核对 raw 与可用／不可用文档身份，保留这个合法拒绝路径，禁止为合法原件伪造 unavailable。同时补齐所有四态内 check 引用的解析检查。

首批新增回归运行退出 1（8 个失败、1 个错误）；新增的双清单删除回归也先失败。完整包的唯一但错绑 invocation 探针同样先失败。修正未放宽旧格式，也没有把四态协议检查提升为语义接受。

修改后 Python 边界测试增至 23 项，完整四包每包交换变异增至 12 项。合法 Evidence、batch、request、manifest 与既有 schema／向量字节保持不变；只更新候选契约的规范／源码摘要和空信任消除规则登记。旧 v0.1、原 backend、ADR、IR 与 lockfile 不改。

最终复跑：23 项 Python 边界测试、23 项 Rust Evidence 定向测试、四包共 48 项交换变异拒绝、28 个有限语义观察及四项生产结果变异均通过；五份 schema 与 16 份协议样例结构通过。仓库检查通过（3079 个文件），旧八份基础向量／五份部分拒绝及 v0.1 的 27 份生成文件保持通过，差异卫生通过。未新增全 workspace、真实运行或分仓验证。

本次只按精确路径暂存并提交本仓候选及复审修复，提交身份和摘要以 Git 记录为准。不 push、不创建 PR、不重绑独立 checker 制品；临时合成导出沿用首次收口材料，没有新增长期进程。
