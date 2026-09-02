# Checker runtime Independent Check result consumer 切片审阅单

状态：公共 Independent Check result `0.1` 的单一 Rust 消费边界已物化；真实 checker spawn / isolation 仍未实现
实施日期：2026-09-02

## 交付结论

本切片在主仓 `radishaxiom-checker-runtime` core crate 中实现 qualification 与后续产品 invocation 共用的单一 Rust result consumer。实现只复用现有 safe Rust ASCII canonical JSON、SHA-256、registration 与 qualification 类型，没有新增 dependency、feature、`unsafe`、Go 源码复用或 Python runtime 调用，也没有修改 Independent Check、launcher policy、registration、installation receipt 或 qualification 的公共格式。

consumer 的结论只表示 stdout 是一份结构闭合且与本次运行身份一致的可消费 checker 输出。它不重新执行 checker 的 obligation reconstruction、counterexample / concrete replay、proof / certificate、production conclusion 或其他语义规则，也不把 `accepted`、`accepted-with-trust`、`incomplete`、`rejected` 升级为产品证明。

## 公共 result `0.1` 边界

consumer 对 compact canonical result 独立检查：

- 顶层、checker、request / Evidence binding、check definition / refs、TCB item 和四态 variant 的闭合成员集合；
- result `0.1`、固定 checker implementation / `go1.26.7`、非空且非 `latest` 的版本，以及全部 digest；
- 十类 check kind 与各自公共 code registry、非空且有序唯一的 codes、refs 和 check 集；
- 以 `axiom-independent-check-v0.1:check` 域独立复算每个 check ID；
- missing artifact、remaining trust、result refs 与 TCB 的规范顺序和唯一性；
- 四个必需 runtime TCB category，以及公共格式允许但当前单体 registration 不接受的可选 `certificate-checker`；
- available / unavailable document binding 与四态聚合关系；
- 以 `axiom-independent-check-v0.1:result` 域独立形成 result document digest。

结构通过后，消费入口再绑定调用方已经验证的 registration、canonical request raw / document identity、Evidence raw / document availability，以及当前单体 checker 的四类 TCB artifact / version。当前 registration 只允许精确四项 TCB，任意额外 category、artifact 或 version 漂移均失败关闭。

结果输入上限继续与既有 qualification companion 上限一致，为 1 MiB；共享 strict JSON parser 新增 128 层深度停止线，防止在闭合形状检查前由恶意嵌套耗尽调用栈。当前公共 fixture 明确只覆盖 ASCII canonical JSON，core parser 也继续只接受该已审阅子集；未来公共契约若物化合法非 ASCII / 完整 RFC 8785 向量，必须扩展并重新审阅 parser，不能 fallback 到宽松 JSON 或旧 consumer。

## 外层 failure 类型隔离

`axiom-checker-invocation-failure` `0.1` 由独立 `CheckerInvocationFailure` 入口解析，闭合检查 format、version、stable code、`result = not-produced` 与 canonical request 双摘要，最大 64 KiB。它与 `ConsumedIndependentResult`、`IndependentCheckOutcome` 没有隐式转换；invocation failure bytes 不能被 result consumer 接受。

该 codec 只验证既有 envelope，不从 timeout、signal、exit status、截断 stdout 或 stderr 自行推断 code。真实进程观察、一次 invocation 的 result-or-failure 排他状态机和 spawn 前后 executable identity 仍属于后续 immutable spawn boundary。

## Qualification 接入

`QualificationCompanionInput::try_new` 现在必须取得 registration、request binding 和 Evidence binding，并先通过同一个 `consume_independent_result`。qualification record 层随后继续核对 policy 固定的 scenario、outcome、raw length / SHA-256、result document digest 和 registration digest；不再用只抽取三个顶层字段的局部 parser 冒充 contract validation。

store 测试把三份既有公共完整 result fixture 只在内存中重绑到合成 registration / TCB，未读取或执行真实 checker。完整 result 使合成 qualification record 更新为 2,023 bytes；Rust 与独立 Python canonical encoder 对同一输入一致得到 raw SHA-256 `sha256:12b3e3610a049473b3d56566bbf64cc4ce19f6ac4a4d3945bf947f6ca129221f` 与 document digest `sha256:e90fe30fe00b6108e073887675d99967fc2b68ea9713177b8737d625a5f14ef9`。变化只来自测试输入由简化占位 result 升级为完整公共 result，不改变 qualification 公共格式。

## 验证与停止线

Rust 自身测试独立接受 28 份公共 canonical result，按锁定错误码拒绝 7 份 result 负例，并复算 strict Evidence rejection fixture 的公共 result document digest；公共语料尚未物化的无 trust `accepted` 正例另以闭合合成值覆盖。其余定向负例覆盖 registration、request、Evidence、TCB 身份漂移、result / invocation failure 类型隔离、外层 request 漂移、输入上限与 JSON 深度。

最终 Cargo、Python oracle、生成契约、schema、仓库与差异门禁的实际结果统一记录在[当前状态](status/current.md)，避免在本审阅单复制易漂移的仓库文件计数。

本切片只处理合成内存 bytes 和既有测试临时根；没有读取真实产品根、下载 / 安装 / 执行 checker、解析两层 distribution / candidate 业务 manifest、创建 spawn plan、施加系统资源限制、形成真实 qualification、激活 runtime、修改远程状态、提交或 push。active runtime 保持 0，launcher policy 继续为 `specified-not-implemented`。

后续状态：两层业务 manifest parser 已按该顺位完成，下一本地切片把已验证 slot、单一 result consumer 和进程观察接入 qualification / invocation 共用的 immutable spawn plan。真实 asset fetch / install、checker 执行、qualification 与 `registered-inactive -> active` 继续分别验证、分别授权。
