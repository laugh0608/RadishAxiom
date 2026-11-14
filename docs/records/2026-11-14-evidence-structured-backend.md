# 本仓 Rust 新 batch 与结构化中止适配

日期：2026-11-14（Asia/Shanghai）。基线：`dev` / `bc25628`，开始时工作区干净、ahead 2。

用途：记录 R1–R6 的本仓候选实施、复审、验证及边界。现行接口约定见[交换审阅](../evidence/evidence-v0.2-independent-check-review.md)，本文不授予真实运行、公共格式接受或分仓写入资格。

## 授权与交付

所有者先确认 R1–R6，并在接续任务中授权再次复审、修复、验证及本地 `dev` 提交。分仓写入、真实 solver、公共发布与 P6 门禁沿用原范围，P6 为 `closed / p6-not-evaluated`。

- 新增 `readback_v02_with_backend_v02`，在调用边界选择已固定 backend `0.2` 字节；旧入口继续消费 `0.1`。共用来源、P1/P2、S1–S3、目标重放、历史及信任检查。
- 新增 `ReplayInterruptionV02` 与 `InterruptionBinding`，输出中止和组件策略两份规范制品。生成错误来自调用方传入的类型化 Rust 错误；本仓读回须再次运行组件并匹配事实，序列化自身不保证来源或因果。
- model 策略绑定 request 的六项生产预算；replay 策略绑定 execution 的十三项资源预算。其他 request / replay 限额沿用原检查。consumer 上限不足与生产中止分开，零不解释为无限。
- model 中止保留四项输入；replay 中止保留 candidate/world 共六项输入。诊断附件只核对描述、字节与摘要，不读取 Debug 含义。没有诊断附件不影响有效结构化事实。
- 新 Python 原生包入口显式使用 `native_backend=True`；默认旧包重封装路径仍拒绝 Debug 中止。新增结构化原件引用、生产策略及输入闭包核对，不扩大为语义 checker。

## 验收覆盖与保留项

| 层级 | 实际材料与检查 | 不能推出的结论 |
| --- | --- | --- |
| 类型化映射 | model 六资源、replay 十三资源的名称／单位／预算；model 输入类别、replay world 格式及四类 Unsupported；未登记阶段／资源、Internal、嵌套错误保留原错误。 | 不代表所有枚举都可在当前有效 AX-B01 链上触发。 |
| Rust 实际合成调用 | model world-bytes 为零、replay world-bytes 为零、AX-B01 重复 order_id 触发 invalid-model；读回后核对三包及 11 次中止。replay world 精确字节预算完成、少一字节中止。 | 没有真实 solver 输出或合格的真实捕获来源。 |
| 来源与对抗 | 新旧版本互拒，旧 Debug 改版本不接受；重算整个引用图后的错误 cause、限额、阶段、策略、请求及父项拒绝；诊断缺件／错件／文本变化；独立 batch pin 与 consumer cap。 | 重算测试 pin 仅为合成装置，不是来源授权。 |
| 兼容与历史 | 旧四包经过新旧入口，Evidence raw / 文档域身份及剩余信任一致；新 batch 对回既有交换固定摘要。历史、冲突、数值顺序及来源变异在两契约下运行；基础无后端材料仍不要求 batch。 | 不替代独立 Go 的语义实现、四态结果及完整迁移验收。 |
| 跨语言离线检查 | Rust 生成三包，Python 核对结构、来源、生产策略、缺件与交换变异；旧四包继续运行 Python 五类有限语义核对。 | 新中止的 Python 检查不重演 Rust 计数器，不认证运行错误，也不产生独立接受回执。 |

`component-error` 仍属于候选协议可表达范围，本入口没有可接受的独立受信运行事实，故不生成或接受该支持。replay 的模糊 BindingMismatch / Json 等不被猜成某个输入错误；详细支持集合以审阅稿为准。全量 request / manifest / result Rust runtime consumer、真实来源、公共格式、分仓 Go 与 M1/M2/M3 完整验收仍未完成。

## 字节与生成入口

旧 backend / 基础契约、原四包 Evidence、旧读回指纹与交换指纹保持原字节。新中止会自然改变其 Evidence、execution、provenance、batch 及交换身份，不能冒用旧摘要。

[backend-structured-fingerprints.json](../evidence/evidence-v0.2-machine-contract/backend-structured-fingerprints.json) 固定三份新合成包的 Evidence raw、batch raw、request / manifest raw 与文档域摘要及实际大小。输入分别来自 Rust `structured_facts_keep_production_limits_and_stage_specific_inputs` 与 `invalid_model_is_observed_and_bound_to_the_actual_response`，复用具名 MINIMAL / CORRECT fixture 和现有合成响应生成入口。首次生成后人工审阅结构与来源，再从成功测试输出的三行 JSON 固定摘要；正常检查仅只读比较，不自动改基线。

交换候选 `contract.json` 的规范说明和工具源文件摘要随本批更新；backend 登记、五份 schema、原协议向量及原四包交换指纹不变。元数据更新不等于公共字节接受。

## 失败记录与修正

- 首次编译发现一个内部 Batch 单测遗漏新增的显式契约参数，已补为 Legacy；Clippy 发现 fixture 中多余 `let` 返回，已直接消除。
- 额外字段负例最初因测试构造的对象键未排序，先抵达非规范字节拒绝；修正测试为规范字节后抵达闭合成员拒绝，没有放宽读取器。
- 无效模型测试最初修改了 discount_cents 而非规范叶序中的 order_id，解码实际完成，测试失败；对照既有 AX-B01 模型测试后改为重复 order_id，要求解码真实返回输入错误。
- 新包的删除捕获原件负例最初仍调用默认旧重封装入口，先因版本不符失败；将显式 native_backend 选择传至该检查后，再核对实际原件闭包拒绝。保留默认旧入口的版本拒绝。

日志保留于已忽略 `.tmp/evidence-structured-*-2026-11-14.log`；它们仅含合成材料。复现关键源码和固定摘要均在仓库，不依赖临时日志才能运行。

## 验证与交接

首轮实现验证：

| 验证 | 实际结果 |
| --- | --- |
| 全工作区离线测试 | 41 个测试目标、569 项通过、0 失败、1 项既有手动 legacy 导出测试忽略，进程退出 0。日志 `.tmp/evidence-structured-workspace-2026-11-14.log`。 |
| Evidence 验证 | 全工作区包含的 34 项全部通过；新增 8 项集成与 3 项映射测试。最终独立定向八项也通过；旧四包 48 项及新三包 36 项交换变异拒绝、旧 28 项有限重放结果对照均通过。 |
| Python 边界及候选生成 | 23 项边界测试通过；56 份候选生成文件只读核对通过。新三包固定指纹已在最终全工作区运行中再次核对。 |
| 基础及格式契约 | 8 个基础向量、5 个部分文档拒绝通过；用已有 jsonschema 校验五份 schema 与 16 份协议样例通过，未安装依赖。 |
| 静态与仓库检查 | 工作区 Clippy（all-targets / all-features，warnings 为错误）、fmt、仓库检查、文档文件链接及 `git diff --check` 通过。 |
| 字节边界 | 已核对旧 backend、基础和旧四包指纹、新 backend、五份 schema、旧交换四包指纹均无 diff；候选总清单只更新三条来源摘要。Cargo.lock、contracts、AGENTS.md / CLAUDE.md 无变更。 |

没有运行分仓 Go、真实 solver、公共发布或产品装置验收；不宣称独立证明或 P6 放行。主要复现入口：

```sh
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir evidence_review:: --lib --locked --offline -- --nocapture
python3 -I -B scripts/test-evidence-exchange-review.py
python3 -I -B scripts/generate-evidence-exchange-review.py --check
cargo +1.97.1-aarch64-apple-darwin fmt --all --check
cargo +1.97.1-aarch64-apple-darwin clippy --workspace --all-targets --all-features --locked --offline -- -D warnings
cargo +1.97.1-aarch64-apple-darwin test --workspace --all-targets --locked --offline
./scripts/check-repo.sh
git diff --check
```

## 提交前复审

- 新 Rust 入口用类型化中止产物的原因码同时核对 execution 和 replay provenance 终态，旧入口仍使用原 Debug 映射。重放中止复用已完成规范性检查的观察对象。
- 离线交换检查核对来源与 execution 的终态、已知观察 descriptor 的版本以及实际输入角色。即使观察字节缺失，已知的旧版 descriptor 仍拒绝。model 错误指向 response，replay 错误指向 world。若生产 request 已提供但缺预算字段，报告策略错绑。
- 对 Rust 实际生成的合成包增加 15 项离线变异，覆盖伪报完成、把中止原件重新标为完成观察、缺旧版原件、错误输入、改写策略和缺生产预算。首次定向运行复现伪报终态漏拒绝，日志为 `.tmp/evidence-structured-rereview-before.log`。
- 新版历史测试核对全部 5 条信任 ID；删除中止 replay 的精确 host-runtime 与配套 trust-boundary 后，即使较早完成支持仍成立，也以缺运行信任拒绝。

复审工作区离线测试在 41 个目标中通过 569 项，0 失败，1 项既有手动导出测试忽略。最后一次离线检查补强后复跑全部 34 项 Evidence 定向测试，11 次合成中止、额外 15 项变异、原兼容指纹及五类目标有限复核均通过。Python 23 项、56 份生成文件、5 份 schema 与 16 个协议样例、基础 8 个向量及 5 个部分文档拒绝通过。Clippy、fmt、仓库基线、文档相对链接目标和 `git diff --check` 通过。旧候选登记、历史指纹、交换 schema 和协议样例无字节差异。复审日志在已忽略的 `.tmp/evidence-structured-rereview-*.log`。
