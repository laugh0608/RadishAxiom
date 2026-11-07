# AX-B01 P5 本地执行记录核对

日期：2026-11-07。基线为 `dev` 的 `b3fa0e9` 加本批实现。

本记录供管线实施者核对 [ADR 0033](../adr/0033-p5-host-data-ir-v02-pairing.md) 的实际转换、工具身份和记录。范围是 AX-B01 的本机受限执行。生产 receipt、Evidence、工具登记和独立 checker 按各自契约验收。

## 记录入口与工具身份

[Rust 记录入口](../../crates/axiom-ir/src/host_data/execution.rs)调用真实转换并生成私有 `radishaxiom-private-p5-execution` `0.1` 记录。每条记录绑定实际 IR、任务清单和夹具的字节长度及原始 SHA-256，并保留外部预期 IR / 清单摘要、case、槽位、规则字节摘要和实际预算。成功输出引用精确宿主封套，失败保留稳定结果及原因码，输出列表为空。相同抽象表值可能得到相同封套，case 和夹具身份仍由记录分别绑定。

本批在 macOS arm64 以 Rust `1.97.1` 本地构建 [观察入口](../../crates/axiom-ir/examples/record_p5_fixture.rs)。实际 Mach-O 制品为 4,539,984 bytes，原始摘要为 `sha256:5a773ec01965043393c759831c342567cc0b4ccfa1cce09cc0789ce000b88ab0`。工具名为 `radishaxiom-p5-fixture-check`，精确修订标识使用同一制品摘要，role 为 `fixture-checker`。按私有工具域 `radishaxiom-private-p5-v0.1:tool` 计算的 ID 为 `sha256:3ff4dff2890a3410ce622c4fb372ad08c6d6bb505907e3434f527b12b0a37092`。规则使用 ADR 0033 原始字节，摘要为 `sha256:e3a09d750059e563a17f4317590ba9eda188ce24471b69ba2f19f09ef97d5b0e`。

外部脚本在每次启动前后核对同一二进制的原字节，调用该明确路径，程序再核对当前可执行文件的 SHA-256。观察依赖本机文件在执行期间保持稳定。脚本核对退出状态、完整 stdout 和 stderr，再对照记录及封套。普通构建可能产生新的二进制摘要，届时记录的工具身份和摘要也须随实际产物重算。制品位于本地 Cargo 构建目录。

## 实际结果

| case / 槽位 / 条件 | 结果 | 记录原始 SHA-256 |
| --- | --- | --- |
| `base` / input | `completed` | `71e485bf90325df22691d489e7392b3426af5a6e82ab5a453241d836ac5cf23b` |
| `base` / golden | `completed` | `ef6cab5722ab40f2b04a2da0d22bc3265ac91c252612a3c4bd261a3272b212c9` |
| `boundary` / input / 282 bytes | `completed` | `63cadc57fc35b2c9780104f04a786a393acbd3a304df0dadf675f209028fb3fb` |
| `boundary` / golden | `completed` | `8375f609b09ed18277342eb019a28a3e6dcc045f1ffd62e41802489bcdf18941` |
| `invalid` / input | `invalid` / `fixture-precondition` | `0bc4bccec0092e5cb9dec79ed50cd189553da2dcf51f4cfe521de4b4c10e3c7c` |
| `boundary` / input / 281 bytes | `resource-exhausted` / `host-byte-limit` | `70405c14dd61a0de1acd012693e34e48c880a8479cfba8e2ef6c10043227dd1f` |
| `boundary` / input / 替换为 `base` 数据 | `error` / `fixture-binding` | `29eadae0d74a62e127aa8c018a11a2c8380333e43665804d62d641853e6994a6` |
| `boundary` / input / 错误清单 pin | `error` / `task-artifact-mismatch` | `dfa6ab67cbb863222fee54f629994cc270c7ddbb68b8ee6e92089130873e4382` |

四份实际封套与[独立参考字节](2026-11-07-ax-b01-p5-pairing-review.md#可复算的参考封套)一致。失败四条无输出封套。错误工具 pin 返回预检失败，无转换记录。外部脚本复核了全部八条记录的规范字节、精确工具身份、输入引用、预算和结果。

```bash
cargo +1.97.1-aarch64-apple-darwin build --package radishaxiom-ir --example record_p5_fixture --locked --offline
python3.14 -I -B docs/records/2026-11-07-ax-b01-p5-pairing/verify_execution.py target/debug/examples/record_p5_fixture
```

上述是单次转换事实。后续生产阶段仍须按同一 IR、任务和 case 汇集必要槽位，绑定正式工具制品及生产执行入口，再按已接受的契约审阅 receipt / Evidence 配对。私有本地记录不代表 P5 生产资格或开启 P6。
