# AX-B01 Evidence v0.2 M1 迁移准备记录

2026-11-07（Asia/Shanghai），基线为 `dev` 的 `4b1fcc2` 和工作区中的候选 Rust 读回。M1 已核验旧源、重建目标 IR 和 P2 集合，并复跑目标组件。完整迁移停在 Evidence 装配前。P6 为 `closed / p6-not-evaluated`。 [ADR 0009](../adr/0009-axiom-evidence-v0-drift-and-migration.md) · [M1 验收方案](../evidence/evidence-v0.2-minimal-support-review.md#adr-0009-迁移演练)

## 源包与旧策略

源为主仓 `CHK-PROOF-02` 的 `keyed-finite-table-verification / 0.1`。以下均为 SHA-256，表中省略 `sha256:` 前缀。

| 原件 | 原始摘要 | 文档域摘要 |
| --- | --- | --- |
| [request](../../contracts/keyed-finite-table-checker-bundles-v0.1/s/chk-proof-02/bundle/request.jcs) | `6f020229692fc3c1b500f569a39ed6fe2034063dcc3dfc21f754d74c5caf4a09` | `6c0f64b5b4c1111ec07081365a5f060f29620233616edcfd4c309cda7e61e75e` |
| [manifest](../../contracts/keyed-finite-table-checker-bundles-v0.1/s/chk-proof-02/bundle/manifest.jcs) | `b6918df9c0de9dbea8f0fad50f1dca69367d23cca4c11030dc4d4ed255580b58` | — |
| Evidence v0.1 | `b519aef5b208d8ef93d7559a000c56ab78eb59f99dca95ae6a7f58264c964e4d` | `eb2116912d543e7806947299c265afbb1fc9e38466a4a56855d60105819adf6e` |
| [指定态预期结果](../../contracts/keyed-finite-table-checker-bundles-v0.1/s/chk-proof-02/expected-result.jcs) | `289319da33632e25c073bbe16d7b49d7c3e87d65262200a3c0c75e8607b5df68` | — |

Go checker 工作树为干净的 `15001af778204b1a4fdc379eceeb0e26d02f7bd7`，源码摘要为 `sha256:338c65baae9ada95972f97340b44f5833ddd9507a05ac25791d62013d5e39c03`。其导入副本的 Evidence 原字节相同，但 Execution Profile 制品仍为 `sha256:f291e79b25723fad82d8a1e9e9e706ab74d40c6cac812333389519f239c6249e`，主仓当前为 `sha256:cf331d08d5c97c8edfd283531d22a6d5be4d16d77ee1283cbd82279b5533f054`。相应 request、manifest 和指定态预期结果也不同。本次测试显式读取主仓的包和预期文件。

通过临时 `go test -overlay`，使用独立仓的 `bundle.Verify` → `EvaluateVerifiedBundle` 对实际目录运行。现有源码测试的 `currentTestBoundary` 提供本机 `go1.26.3 darwin/arm64` 身份。结果匹配源策略与指定态预期。闭合 12 个 blob，形成 10 类内存检查，无缺失制品，重算源结论为 `satisfied`。在 `attestation-allowed` 下得到 `accepted-with-trust`，12 项后端支持均为 attestation-only，独立证明为 0，剩余一项 `proof-backend` trust，ID 为 `sha256:da2108aac0cc28b7971cbfaad9463f8e13e7389ed60824f24693344619b3ea5e`。该观察属于旧指定态包的源码级测试。正式 `go1.26.7` 产品入口、checker 制品与规范 companion 本次未验收。

## 目标 IR 与义务重建

从源 Evidence 的 subject 制品读取 IR 原件，调用 `axiom-ir-0.1-to-0.2 / 1`，复核 10 项 IR 身份映射。目标 IR 规范字节等于现有冻结向量，P2 结果与 Rust 和 Python 两条路径重建的 13 项定义、ID 及全集字节一致。 [迁移向量与身份映射](../../crates/axiom-ir/tests/fixtures/v0.2/mappings.tsv) · [目标 P2](../../contracts/ir-derived-obligations-v0.2/sets/ax-b01-correct.jcs)

| IR | 原始 SHA-256 | 文档域 SHA-256 | 语义 SHA-256 |
| --- | --- | --- | --- |
| 源 v0.1 | `8d6ec839cf3cf795539e121c488b3bc4be84a33f24ac8c349d5ceebb29e559e7` | `1fa8846fb3ba15937e3e4b5848e74d84d89050711086d7462eb16175510b4154` | `6b18d65eefa439956db8eebe1f4ce90e08b4def4abf7c718c2605e7528598d0d` |
| 目标 v0.2 | `9a62d3b9397f2db664786d64ad77b848a53c46e62186edc29d2c31f665db9f2a` | `90d876b9fdd533944e09f4274ba4aaa313d179454427e60eca81575707054f0b` | `a40ec7c4eecfde23a340fb61b67727b5393f01b7288d151a34168ec88a87dac7` |

目标 P2 原始 SHA-256 为 `5edf309363ddb36f219a317e2cb714ba0673669c26f1b376368f22c9d327356f`。逐项对照时，在源核心定义的 subject 上替换 IR 文档域 ID，并按 IR 迁移记录替换节点和契约 ID。13 项均唯一命中目标定义，源与目标义务 ID 全部不同。下表使用各集合中唯一的 8 位前缀，定义及完整 ID 见源 Evidence 和目标 P2。

| 目标 | 源义务 | 目标义务 | 实际准备结果 |
| --- | --- | --- | --- |
| `ir-structure` | `9a8a6c52` | `b804c936` | P1 严格读回通过 |
| `effect-empty` | `42b8fd9d` | `64bd44f0` | P3-E 记录重建并逐字节匹配 |
| `field-origin` · `net_orders.order_id` | `f52b2421` | `4f97f098` | P3-F 记录重建并逐字节匹配 |
| `field-origin` · `net_orders.net_cents` | `2038d910` | `e4b0331b` | P3-F 记录重建并逐字节匹配 |
| `totality` · filter | `a9304062` | `b0f12d6e` | 265,107 bytes |
| `totality` · map | `611f797e` | `1dcc3305` | 273,742 bytes |
| `key-cardinality` · filter | `3accfce9` | `8a608c25` | 489,539 bytes |
| `key-cardinality` · map | `9f5de6fb` | `a00fdcf3` | 496,386 bytes |
| `row-coverage` · filter | `5dcb026d` | `75e9b6af` | 722,453 bytes |
| `row-coverage` · map | `ea07f198` | `c088c2a0` | 731,531 bytes |
| `numeric-range` · map 减法 | `1314f936` | `34666d2d` | 274,860 bytes |
| `numeric-range` · guarantee 减法 | `654dac39` | `4b054af7` | 524,434 bytes |
| `contract-guarantee` | `d0411681` | `b4ad73cf` | 960,250 bytes |

九个字节数均为实际重生成的 query v0.5 输入，查询原始摘要与冻结测量逐项相同。P4-A v0.2 用既有合成 generator / tool 身份逐目标生成九份请求，复核 stdin 原字节、目标、P2 摘要和 1,048,576 bytes 上限。定向测试输出各请求的原始摘要。P3-E / F 的内部记录同样使用既有合成 generator 身份。源的第 14 项义务属于旧 `proof-backend` trust，只留在旧记录。目标信任项要从新的实际执行和适用政策重建。 [查询摘要](../query/compact-query-production-validation/ax-measurements.tsv) · [Rust 定向回归](../../crates/axiom-ir/src/solver/tests/compact.rs)

## 阻断与恢复顺序

1. S1–S3 已具备本仓重建材料。公共契约仍须审定，实际执行来源和独立 S1–S3 判定仍须按独立检查矩阵验收。
2. 九项后端义务具备查询及离线请求，均无目标的合格执行、响应或可用结果。现有 solver 的制品与执行环境资格未闭合。即使 ADR 0028 的校准获准，其一次原容量诊断也限于 wrong-add 的 guarantee，产出仍为后端观察。AX-B01 correct 九项的真实执行范围、逐结果支持和可接受信任政策须按验证线门禁单独验收。 [当前恢复顺序](../status/current.md#接下来的事项) · [ADR 0028](../adr/0028-bounded-solver-calibration-entry.md)
3. 目标的实际 trust、Evidence、request、manifest 和独立结果均未形成。M1 保留未完成状态，九项记录为缺执行。等目标材料齐备后，按 ADR 0009 进行完整读回和独立复核，再核对公共版本切换所需的拒绝矩阵。P6 保持关闭。

## 重跑

在主仓根执行以下离线检查。Go 源码核验单独在 checker 仓使用临时 overlay，通过上述两个既有入口读取主仓场景目录，以 `expected-result.jcs` 核对四态、剩余信任与缺失制品。保留了两个负向观察。原摘要路径下替换等长 IR 原字节返回 `digest-mismatch`。用旧 Evidence parser 读取完整合成 v0.2 向量返回 `unsupported-version`。

```sh
python3 -B scripts/generate-checker-bundle-contracts.py --check
python3 -B scripts/generate-p2-profile-review.py --check
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir --test migration --locked --offline
cargo +1.97.1-aarch64-apple-darwin test -p radishaxiom-ir --lib --locked --offline m1_prepares_exact_source_migration_and_nine_backend_requests -- --nocapture
```
