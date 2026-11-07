# AX-B01 P5 新旧宿主封套配对审阅

日期：2026-11-07。基线：`dev` 的 `f03db3f`。

本记录保存 [ADR 0033（Proposed）](../adr/0033-p5-host-data-ir-v02-pairing.md) 的样本、拒绝对照与验证入口。对照工具只生成 ASCII 样本并做绑定检查。生产 serializer、`check-fixture` 执行记录和 Node consumer 尚待实现及验收。

## 现行读取器的实测

- [旧封套结构验证器](../../scripts/pipeline_artifact_contracts/validation.py)接受原最小样本。用同一封套 v0.1 形状写入已迁移 IR 的文档 ID 后也通过结构验证。这里检查的是摘要词法，没有取得实际 IR 以确认域和版本。
- 将拟议封套的 `format_version` 设为 `0.2` 后，旧封套读取器报 `unsupported-version`。将[原 receipt](../../contracts/pipeline-artifacts-v0.1/fixtures/minimal/receipt.jcs)的 `ir_version` 改为 `0.2` 并重新规范化，旧 receipt 验证器同样拒绝。
- [旧 receipt 样本生成器](../../scripts/pipeline_artifact_contracts/builders.py)的 P5 输入已是 `host-input` / `golden-output`，输出为空。它没有覆盖原始夹具转宿主封套的配对。下一版需从实际夹具与工具输出建立这条关系。

## 可复算的参考封套

使用[原任务清单](../../benchmarks/keyed-finite-table-v0.1/ax-b01/task.json)选定 `base` 和 `boundary` 的实际源制品，重算其原始 SHA-256。表数据与 [P5 独立对照](2026-11-07-ax-b01-p5-entry-review.md)一致。下表各对保持表和角色不变，只切换封套版本值与 IR 文档 ID。

| IR | canonical 字节 SHA-256 | 文档域 ID |
| --- | --- | --- |
| v0.1 | `8d6ec839cf3cf795539e121c488b3bc4be84a33f24ac8c349d5ceebb29e559e7` | `1fa8846fb3ba15937e3e4b5848e74d84d89050711086d7462eb16175510b4154` |
| v0.2 | `9a62d3b9397f2db664786d64ad77b848a53c46e62186edc29d2c31f665db9f2a` | `90d876b9fdd533944e09f4274ba4aaa313d179454427e60eca81575707054f0b` |

| 样本 | 字节数 | 封套 v0.1 原始 SHA-256 | 拟议封套 v0.2 原始 SHA-256 |
| --- | ---: | --- | --- |
| `base.input` | 444 | `c8bffc56c9aaff6e2ccead55cd9d3b0599409f71d6585db2884b4290572e90fb` | `f2e62589dfdabf4b8da1c7767f48c0a3719cf2ff8418726d3454e95efe2ab307` |
| `base.golden` | 274 | `bbe7d677b41f429b02d6da1b7f7b9091efd7e2a7a7383396bcb5ee3350ba96e2` | `e2395dbafded36de5a4b0974484a1b31c64c6f57e0ac85dce38e143ed2eb88a3` |
| `boundary.input` | 282 | `a5436c6528c62c05d61a28452e643cea053a5c3f2701b19901e8540a3dc8e87d` | `c044278f53053a8b6cbfe787d1099990052c3d045dae2af73e1d0f738152f270` |
| `boundary.golden` | 243 | `6e17392e8949bf385dd794578adbd171a4631e26820390cb316f223c066fb237` | `d0f8a189b1941f35fcc37ae61cbfba26f0991cf5a591622cfd51aa9ea84369d4` |

`boundary.input` 的拟议字节如下，哈希时去掉展示用的末尾换行。

```json
{"format":"axiom-host-data","format_version":"0.2","ir_document_digest":"sha256:90d876b9fdd533944e09f4274ba4aaa313d179454427e60eca81575707054f0b","role":"input","tables":[{"name":"orders","rows":[{"discount_cents":"0","order_id":"O4","state":"settled","subtotal_cents":"100000"}]}]}
```

## 拒绝路径与覆盖

| 情形 | 本批实际观察 | 拟议生产记录 |
| --- | --- | --- |
| 原 `invalid` | Rust P5 组件依据已绑定的 `assume` 拒绝 `orders:OX`，折扣 `101` 大于小计 `100` | `invalid`，无宿主输出。Evidence 使用可重放见证及实际检查 |
| 同一 `invalid` 但比较预算为 0 | Rust P5 返回 `Resource(PreconditionChecks)`，尚未判定该行 | `resource-exhausted`，无宿主输出 |
| 旧封套进入新配对，或提供旧 IR | 对照拒绝封套版本、IR 制品摘要或 IR 版本 | `error`，无宿主输出 |
| 把旧文档 ID 或 IR 原始摘要写入新封套 | 对照拒绝 IR 文档域绑定 | `error`，无宿主输出 |
| 互换输入与黄金角色，或修改夹具字节 | 对照拒绝角色或原始夹具摘要 | `error`，无宿主输出 |
| 用完整且可独立散列的 `base` 新封套替代 `boundary` 新封套 | 格式、角色和 IR 文档 ID 均相同，仍因根据选定夹具重建的完整字节不同而拒绝 | 制品复核失败，拒绝消费 |

在仓库根运行[对照脚本](2026-11-07-ax-b01-p5-pairing/compare.py)和已有组件测试。

```bash
python3.14 -I -B docs/records/2026-11-07-ax-b01-p5-pairing/compare.py
cargo +1.97.1-aarch64-apple-darwin test --package radishaxiom-ir --lib --locked --offline fixtures::tests
```

四份对照及九项拟议配对拒绝通过，另有两项旧读取器版本拒绝。七项 Rust 组件测试通过。原契约由仓库检查回归。新封套的 Unicode 编码、序列化预算、完整执行记录及跨实现复核仍是实现后的验收项。
