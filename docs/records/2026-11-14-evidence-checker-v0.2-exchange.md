# 分仓 Go checker v0.2 首批交换验收

日期为 2026-11-14（Asia/Shanghai）。主仓输入固定在 `8d924f0ec6c076f770ba9f8a36ae3263f27e51b7`。分仓 RadishAxiomChecker 从 `15001af778204b1a4fdc379eceeb0e26d02f7bd7` 推进到本地 `dev` 的 `091c6163bb429ce201f7284797cdafc67e9ce47a`。候选契约和逐案输入来自主仓固定清单。 [交接范围](../evidence/evidence-v0.2-independent-check-review.md#checker-handoff)

| 复核对象 | 实际身份或结果 |
| --- | --- |
| 交换候选契约 | `sha256:b060d887493f3d7999ad0aeb0464e669b0bd57ef445106bafe5d2b0dc1bd9317` |
| 分仓源码清单和本机测试制品 | 源码 `sha256:79c954ec971839742e488d23d6ac703103c7f949c2b769926ce32dbcfba116ce`，Go `1.26.7` Darwin arm64 测试制品 `sha256:e0ae588f5b6b34a589ce542d20130daa76f1a2231fde18f7caf06b4e026cd385` |
| 十个原生合成包 | 九个 `incomplete`，其中四个保留未复核的中止原因。缺历史运行信任的包以 `invalid-state-support` 拒绝。冲突包完成来源绑定，反例和支持的独立复核仍待完成。 |
| 扩展交换矩阵 | 两个无后端包、错误 request / batch / contract pin、版本互拒、重封装后错绑、缺 Evidence、坏摘要及缺件与坏摘要并存的分支均按预期判定。规范回执通过候选 schema 和绑定核对。 |

分仓定向测试、`go vet`、模块闭包及仓库检查通过。完整 `go test ./...` 和源码身份检查在基于分仓提交前源码形成的干净快照中通过。分仓实际工作树已有被 Git 忽略的 `.idea` 文件，源码身份扫描和依赖它的分发测试报告漂移。两仓各自保留本地提交。

## 第二批：合成 AX-B01 语义验收

主仓输入固定为 `9284b5abcc4815da756139f8e0592295f3ecb3b1`，分仓在 `091c6163bb429ce201f7284797cdafc67e9ce47a` 上实现并提交到本地 `dev`，提交为 `ec3eb6fe7bee30a39030c9d6d27da7c72eb821d6`。合成输入沿用 [AX-B01 包指纹](../evidence/evidence-v0.2-machine-contract/independent-check-v0.2/packet-fingerprints.json)、[交接包指纹](../evidence/evidence-v0.2-machine-contract/independent-check-v0.2/handoff-fingerprints.json)和[结构化中止包指纹](../evidence/evidence-v0.2-machine-contract/backend-structured-fingerprints.json)，调用仍从包外提供 pin。

| 复核对象 | 实际身份或结果 |
| --- | --- |
| 分仓源码清单和本机测试制品 | 源码 `sha256:9ed668592e9ce1ba9e7d5ce54de6cfa52dfa8defc289dee3a799d27b5d9aa326`，Go `1.26.7` Darwin arm64 测试制品 `sha256:8ee0cfa703d274b76bda5eccdb88bb23d45124e22b4fcb3e99afa4f073bed7b1` |
| P1 / P2 | Go 对 `correct`、`wrong-add`、`wrong-drop-zero` 独立核验 IR v0.2 并逐项重建 13 项核心义务的 definition / ID。另核对 `pre-false` 的 4 项义务。 |
| 精确目标 | 在 `wrong-drop-zero` 的绑定世界上，WF 与 Pre 成立，guarantee 为假，filter 和 map 的双向覆盖成立。将失败声明改挂到 coverage 并重算包身份后，checker 在对应义务上返回 `counterexample-invalid`。 |
| 十个原生交接包 | 八个 `incomplete`。缺历史运行信任以 `invalid-state-support` 拒绝，已绑定的同目标合成 `unsat` 与独立重放确认的违反见证并存时以 `proof-support-mismatch` 拒绝，保留源信任。 |

分仓定向测试和仓库检查通过。与分仓变更逐字节匹配的干净源码快照通过 `go test ./...`、`go vet ./...`、模块闭包和源码身份检查。提交前复跑十个交接包、四个 AX-B01 / Pre 包、两个无后端包，以及错 pin、缺件、坏摘要、重封装错绑和 coverage 错归因的负例。回执通过候选 schema 及身份绑定核对。

本切片核实绑定世界上的有限结论。交接请求的 `collection-items` 限额不足以完整解析大型符号表，P4-A 尚未从原始模型独立重建 world。下一步先量化该预算断点，再验收独立的符号和布局核对、模型解码及规范 world 字节比较。相符、模型与 world 错配、符号错绑和预算耗尽须各有可复现结果。S1–S3 支持、其他重放目标、attestation 聚合和未核实的结构化中止原因继续按 `incomplete` 处理。真实 solver 和公共发布沿用原门禁，P6 保持 `closed / p6-not-evaluated`。

## 第三批：合成 P4-A 独立解码复审

主仓输入固定在 `a866257`，分仓由 `ec3eb6f` 推进到 `92960b77838b602135101164b63c7f2ac849da7c`。本机 Go `1.26.7` Darwin arm64 测试制品为 `sha256:35ed606dc7b38aa16e93637183dfdcaff7bab3c0ed275f77b0fed67065a6586b`，源码清单为 `sha256:b235d7c8bc76c575bc0d56590c552b15dc88ed5f939ca4d14e63d9476e940091`。

复审补计了重建 JSON 在规范编码前再次解析的 JSON 成员、深度和步骤，并在逐字节比对前检查累计账本。因此本表取代初次实现时的预算断点。最大的单份输入符号表有 12,768 项。原请求的 `collection-items` 为 10,000，三个 AX-B01 包在首个模型比对完成前即返回资源 `incomplete`。

| 合成包 | 9 次模型核对所需的最低累计 `collection-items` | 量测该项时的 `semantic-steps` |
| --- | ---: | ---: |
| `correct` | 129,086 | 2,000,000 |
| `wrong-add` | 127,887 | 2,000,000 |
| `wrong-drop-zero` | 130,227 | 2,000,000 |

用固定包复制件和调用方重新计算的 request pin 测到上限等值及少 1 项。等值时，27 份 SAT 响应重建出的 world 和 Text 类均与包内规范字节匹配。少 1 项时，三个包各保留 8 项通过，第 9 项按 `source-unavailable` 返回 `incomplete`。保持表中项数、把步骤还原到原请求的 1,000,000 时，同样各保留 8 项通过，第 9 项耗尽步骤。复审未修改原交接包或生产限额。

重新封装后分别修改原始模型中的活动数值、替换候选 world、交换两个同类型自由符号的来源、篡改布局字段路径，四案均由独立模型检查以 `concrete-check-mismatch` 拒绝。旧 pin 拒绝新请求。同目标冲突包同时核对预算不足与预算充足，已确认的冲突均保留 `rejected`。十个交接包仍为两个 `rejected`、八个 `incomplete`。

分仓定向测试、仓库检查、干净源码快照的 Go 全量测试、`go vet`、模块闭包和源码身份检查均通过。独立解码范围为合成 AX-B01 标量输入及零容量 Pre 对照，整条 SMT 公式与 IR 目标的等价性仍待核实。下一切片独立检查 S1–S3 的四项结果支持，再覆盖其余精确目标与历史状态。真实 solver、公共发布和 P6 继续沿用原门禁。
