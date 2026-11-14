# 分仓 Go checker v0.2 首批交换验收

日期为 2026-11-14（Asia/Shanghai）。主仓输入固定在 `8d924f0ec6c076f770ba9f8a36ae3263f27e51b7`。分仓 RadishAxiomChecker 从 `15001af778204b1a4fdc379eceeb0e26d02f7bd7` 推进到本地 `dev` 的 `091c6163bb429ce201f7284797cdafc67e9ce47a`。候选契约和逐案输入来自主仓固定清单。 [交接范围](../evidence/evidence-v0.2-independent-check-review.md#checker-handoff)

| 复核对象 | 实际身份或结果 |
| --- | --- |
| 交换候选契约 | `sha256:b060d887493f3d7999ad0aeb0464e669b0bd57ef445106bafe5d2b0dc1bd9317` |
| 分仓源码清单和本机测试制品 | 源码 `sha256:79c954ec971839742e488d23d6ac703103c7f949c2b769926ce32dbcfba116ce`，Go `1.26.7` Darwin arm64 测试制品 `sha256:e0ae588f5b6b34a589ce542d20130daa76f1a2231fde18f7caf06b4e026cd385` |
| 十个原生合成包 | 九个 `incomplete`，其中四个保留未复核的中止原因。缺历史运行信任的包以 `invalid-state-support` 拒绝。冲突包完成来源绑定，反例和支持的独立复核仍待完成。 |
| 扩展交换矩阵 | 两个无后端包、错误 request / batch / contract pin、版本互拒、重封装后错绑、缺 Evidence、坏摘要及缺件与坏摘要并存的分支均按预期判定。规范回执通过候选 schema 和绑定核对。 |

分仓定向测试、`go vet`、模块闭包及仓库检查通过。完整 `go test ./...` 和源码身份检查在基于分仓提交前源码形成的干净快照中通过。分仓实际工作树已有被 Git 忽略的 `.idea` 文件，源码身份扫描和依赖它的分发测试报告漂移。两仓各自保留本地提交。

下一切片以合成 AX-B01 为验收边界。Go 路径从 IR v0.2 独立重建 P1 / P2 的 13 项核心义务，绑定实际目标、WF / Pre 和有限重放。用 `wrong-drop-zero` 验证 guarantee 失败时 `row-coverage` 不被错归为失败，再用同一目标的合成 `unsat` 与有效反例验证冲突拒绝。S1–S3、证明支持与尚未核实的中止原因仍按实际完成的核验给出结果。真实证据迁移沿原顺位推进，P6 为 `closed / p6-not-evaluated`。
