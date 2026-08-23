# Implementation Readiness Contract v0.1

用途：把四题基准、首版生产管线、独立 checker、工具身份及 ADR 0007 / 0008 的实现前验收条件统一为一份可生成、可拒绝、可追溯的场景矩阵。

目标读者：准备受控实现切片、审阅跨契约停止线或构造后续离线 bundle 的维护者。

不包含：生产编译器、solver / Node / checker 执行记录、完整 IR / Evidence / checker bundle、工具 payload 验收、正式模型调用或六平台通过声明。

## 固定内容

- manifest.jcs：radishaxiom-implementation-readiness 0.1 的 canonical ASCII JSON 清单；
- schemas/implementation-readiness-manifest.schema.json：JSON Schema Draft 2020-12 结构约束；
- contract.json：来源绑定、生成文件摘要、manifest 域摘要、场景计数和生成器源码摘要；
- fixtures/negative/：gate 绕过、义务遗漏、artifact 篡改、伪造 cache hit、缺失 bundle 后错误接受、attestation 越权、错误结论聚合、进程失败伪装成独立结果及未知 member / version / profile 等拒绝样例；
- fixtures/negative/expected.json：每个负例的原始摘要和稳定期望码。

矩阵当前包含：

- 四题语料现有 20 个 Expected Evidence 场景；
- ADR 0008 的 16 个 CHK-* 场景；
- 10 个 pipeline / readiness 场景，覆盖 gate、cache、恢复、新 attempt、emitter / host / P9 操作失败、工具供应链停止线和首次实现单独授权。

每行固定输入 candidate / fixture、P0–P9 结果、gate 决策、必须和禁止出现的 artifact role、receipt、Evidence、独立结果与进程结果、remaining trust / uncovered、六平台注册适用范围和证据等级。重叠验收要求通过 source_refs 与顶层 coverage 指向同一场景，不复制第二套结论。

## 证据和职责边界

level 目前只能为 specified，顶层 observed_scenarios 固定为 "0"。六个平台出现在 platforms 中只表示适用范围，不表示已经执行。benchmark 的 Evidence 断言从版本化语料读取并核对原始摘要；矩阵不生成生产 Axiom Evidence，也不生成或执行独立 checker result。

三层输出保持分离：

- pipeline receipt 只记录生产阶段、attempt、gate、cache 和操作结果；
- Axiom Evidence 只表达规范允许的义务状态、结论、trust 与 uncovered；
- independent result 只表达 checker 对 request / bundle / Evidence digest 的外部复核。

checker 外层构建或进程失败使用 independent.process / process_codes，不得伪造成 accepted、accepted-with-trust、incomplete 或 rejected。independent.codes 只接受 Independent Check Contract v0.1 的闭合 code registry。

## 生成与检查

本 README 手工维护；除此之外，本目录全部文件由零第三方依赖的生成器维护：

    python3 scripts/generate-implementation-readiness.py --check
    python3 scripts/generate-implementation-readiness.py --write

生成器读取并摘要绑定：

- 四题 benchmark corpus；
- keyed finite table semantics、Axiom IR v0.1 与 Axiom Evidence v0.1；
- Pipeline Artifact Contract v0.1；
- Independent Check Contract v0.1；
- Toolchain & Adapter Identity Registry v0.1；
- ADR 0007 与 ADR 0008。

校验器除 schema 结构外还检查原始绑定摘要、场景与来源覆盖、P0–P9 顺序、gate / artifact 停止线、cache 身份、bundle / trust / process 聚合、benchmark 断言一致性和全部负例期望码。当前 canonical 子集只使用 ASCII、无 JSON number / null 的合成 fixture，不冒充完整 Unicode / JCS 实现。

## 仍未解除的停止线

- benchmark bundle 均为 specified-not-materialized，后续仍须生成 AX-B01–AX-B04 的完整 IR / Evidence / checker 离线 bundle；
- 工具 registry 中的 payload、包内容和许可证仍未验收，PIPE-TOOLCHAIN-NOT-ACCEPTED-01 保持 gate 关闭；
- certificate 能力、完整 options / limits、真实跨平台语义一致性和首次 checker 实现仍须分别验收或授权；
- 本契约通过只说明静态实现入口一致，不授权下载依赖、创建编译器 / checker 工程或运行 solver、Node、checker 与正式模型实验。
