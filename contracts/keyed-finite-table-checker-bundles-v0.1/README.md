# Keyed Finite Table Checker Bundle Contract v0.1

用途：把 Implementation Readiness Contract 的稳定场景 ID 解析为完整、离线、内容寻址的 checker 输入和唯一预期结果，让后续独立 checker 可以在不读取生产缓存、不联网、不执行生产 Node module 的条件下重放格式、身份、义务、状态、反例、具体检查、proof policy 与结论聚合。

本目录仍是 `specified` 级合成验收制品。这里的 Axiom Evidence、pipeline receipt、checker result 和进程失败记录描述应当出现的规范字节，不表示 Rust `raxc`、cvc5、Node 或 Go checker 已经运行，也不构成六平台观察证据。

## 固定内容

- `bundle-set.jcs`：28 个 readiness scenario ID 到 bundle、Evidence、request、预期结果与摘要的 canonical 索引；包含 20 个 benchmark、5 个跨契约场景和 3 个负例。
- `schemas/keyed-finite-table-checker-bundle-set.schema.json`：索引的 JSON Schema Draft 2020-12 结构约束。
- `s/<scenario-id>/bundle/`：ADR 0008 的只读目录 envelope，只有 `request.jcs`、`manifest.jcs` 与 `blobs/sha256/<hex>`；短前缀用于满足仓库跨平台路径长度门禁。
- `s/<scenario-id>/expected-result.jcs`：Evidence 之外的指定态独立结果；`CHK-PROCESS-01` 改用 `expected-process-failure.jcs`，明确不产生四态 result。
- `contract.json`：来源绑定、生成器源码、全部生成文件摘要、bundle set 内容摘要和域摘要。

每个 manifest 只列普通 blob，按 content digest 唯一排序并固定 `byte_length`、`format`、`format_version` 与 role。Evidence 的 artifact 清单覆盖其直接引用及所绑定 receipt 的传递制品闭包，receipt 由结构检查 execution 显式引用；normative spec 包括 [Execution Profile Contract v0.1](../execution-profiles-v0.1/README.md)，保持独立 role 且不能改写 checker 规则。bundle 不包含路径 resolver、URL、凭据、网络 fallback、生产 cache key、symlink 或可变工具身份。预期结果不位于输入 bundle 内，checker 也不得修改 bundle。

## 场景范围

20 个 benchmark 场景完整覆盖四题的正确候选、两个错误候选、非法输入与 backend timeout。Evidence 从 IR 按 `keyed-finite-table-benchmark` profile 生成完整义务：文档 / 程序、全部非 input 节点、算术与聚合表达式、转换覆盖与输出字段来源、guarantee / noninterference、具体输入、宿主输出、黄金比较及实际 trust 均有稳定 anchor 和义务 ID。

跨契约场景固定：

- `CHK-CONCRETE-01`：host output 与 golden 不一致，Evidence 为 `implementation_inconsistent`，独立结果仍可接受该忠实失败报告；
- `CHK-PROOF-01`：`certificate-required` 遇到 backend attestation，结果为 `incomplete`；
- `CHK-PROOF-02`：`attestation-allowed` 只保留为 `accepted-with-trust`；
- `CHK-RESOURCE-01`：checker 在请求内显式 semantic step budget 耗尽时形成 `incomplete`；
- `CHK-PROCESS-01`：checker 在形成规范结果前失败，只生成绑定 request 的外层 invocation failure。

三个负例分别物化 `CHK-BUNDLE-01` 的必需 blob 缺失、`CHK-DIGEST-01` 的 IR 路径字节篡改，以及 `CHK-OBLIGATION-01` 的 Evidence 义务省略。负例保留原 manifest / request 或重新绑定被篡改的 Evidence，以便精确区分 `artifact-missing`、`digest-mismatch` 与 `obligation-mismatch`。

## 指定态 Evidence 投影

反例 world 使用 Evidence v0.1 的显式 tagged value 与完整 record；trace 只使用 document、obligation 和 observation 稳定 step。`reduced` 只绑定 `axiom-witness-order-v0.1`，不声明 `proved-minimal`。正确场景的 `proved` 使用绑定 query / response / execution / proof-backend trust 的 `backend-attestation`；错误候选和非法输入中其余可完成静态义务使用指定态 `kernel-replay`，失败义务绑定完整 world 与 replay execution。backend timeout 使用真实非空 attempt 结构，不写成 `failed`。执行 `replay-counterexample` 的 fixture tool 必须显式声明既有 `counterexample-replayer` role；生成器按全部 execution kind 检查对应 tool role，不接受角色 alias。

checker result 中每个 check definition 的 `codes` 沿用 Independent Check Contract v0.1 的闭合集合；bundle set 顶层 `expected.codes` 只保留 readiness 场景要求的决定性 code，因此成功接收场景可为空。`remaining_trust` 存放 Evidence trust ID，bundle set 另从 Evidence definition 重算类别，二者不可互换。

## 生成与检查

本 README 手工维护；除此之外，本目录全部文件由零第三方依赖生成器维护：

    python3 scripts/generate-checker-bundle-contracts.py --check
    python3 scripts/generate-checker-bundle-contracts.py --write

生成器复用 Independent Check Contract v0.1 的 request / manifest / result 校验入口和 Pipeline Artifact Contract v0.1 的 receipt 校验入口；它不会调用 solver、Node 或 checker。仓库级检查同时执行 bundle 生成重放、摘要链、readiness 断言、负例、路径与文本卫生校验。

## 指定态边界与运行进展

- 本目录 bundle 是指定态 fixture，`observed` 保持为 0，不能作为真实工具运行或证明记录。后续 checker 对它的实际运行应另存绑定输入身份的结果，不原地把期望制品改写为观察证据。
- checker 已有的有限执行、反例 / concrete replay、结论重算、独立 result / CLI 和 payload 进展统一见[当前状态](../../docs/status/current.md)。生成器不会因这些实现完成而变成生产工具；支持范围仍受 profile 和 [ADR 0009](../../docs/adr/0009-axiom-evidence-v0-drift-and-migration.md) 约束。
- 工具来源、包内容和依赖 / 许可证按[逐 payload 验收](../toolchain-payload-acceptance-v0.1/README.md)及[checker 登记](../checker-runtime-payloads-v0.1/README.md)判断；单项已验收不代表全工具链、全部平台或 runtime 已激活。
- cvc5 options、Node invocation limits 与 checker resource limits 由 Execution Profile Contract v0.1 指定。契约通过不证明真实执行满足限制，也不扩大 certificate 支持集合或把 backend attestation 升为独立 proof。
- 本契约不授予下载 / 安装、生产实现、工具执行、push、发布或部署授权；实际任务按当前状态与对应 ADR 的前置和授权规则执行。
