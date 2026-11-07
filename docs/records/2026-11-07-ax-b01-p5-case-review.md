# AX-B01 P5 用例关联与候选工具核对

日期：2026-11-07。基线为 `dev` 的 `17c2cc4` 加本批源码。

本记录保存 [ADR 0033](../adr/0033-p5-host-data-ir-v02-pairing.md) 的同案关联实现、实际候选工具和独立复核结果，供 [ADR 0034](../adr/0034-p5-case-receipt-v02.md) 评审使用。范围限于 AX-B01 和本机候选。公开回执、Evidence、生产工具接受和宿主执行各自验收。

## 同案执行与失败记录

[用例入口](../../crates/axiom-ir/src/host_data/execution/case.rs)把同一工具、IR、任务清单、case 和预算交给已有的单次转换。输入先检查，成功后才尝试黄金输出。私有用例记录按执行顺序引用实际记录的长度及 SHA-256，工具、规则、输入、角色及输出继续由单次执行记录绑定。调用方只能在两次执行成功后取用封套对。单次输入封套可以保留供审计，缺失或失败的黄金槽位不能用它补齐。

实际输入不符合时保留 `invalid`，预算不足保留 `resource-exhausted`，缺少黄金数据与制品错配分别使用 `missing-golden` 和 `fixture-binding`。黄金预检失败时保留之前的输入执行，黄金槽位没有伪造的 attempt。用例完成仍须经过原 P6 门控才可生成目标。

## 候选工具的实际构建

[候选记录](2026-11-07-ax-b01-p5-pairing/case-tool-candidate.jcs)绑定 86 项冻结材料及长度 / SHA-256，集合摘要为 `sha256:18700a877d957ebf3b928bf09fa0dbc7733d0dda6994a1df7d0b0bbbd7953947`。其中 69 项是 Cargo 为观察入口报告的依赖，其余材料供 workspace 解析及标记构建边界。以固定的 Darwin arm64 Rust `1.97.1`、实际 Cargo 和 rustc 文件，从临时源副本重新执行 `build --package radishaxiom-ir --example record_p5_fixture --locked --offline`。构建禁用增量，使用现有离线 Cargo 缓存，临时源副本及其构建目录已清理。

[构建观察脚本](2026-11-07-ax-b01-p5-pairing/capture_case_candidate.py)检查源副本、原材料和工具在构建前后相等，并确认新构建的依赖清单与发现清单相同。该观察采用 Cargo 报告的依赖边界和本机已选的链接环境。系统库、链接器和操作系统按此本机观察范围信任，工具的每次读文件没有单独截获。

实际工具为 4,470,608 bytes 的本机制品，SHA-256 为 `sha256:f8bd89af3a9c844c35098b81493b296cc149d33bdf0b9e6a59d25aed2b1c2ec3`，私有工具 ID 为 `sha256:126ecbbe2804bd5d39269bc5ca57c7b33bd83a1fb8ac861398fd23d4c221e45c`，role 为 `fixture-checker`。规则为 ADR 0033 原字节，SHA-256 为 `sha256:e3a09d750059e563a17f4317590ba9eda188ce24471b69ba2f19f09ef97d5b0e`。实际二进制按摘要保留在本地 `target/p5-case-candidates/`。重建的调试路径或宿主差异可能产生新二进制，按新字节建立身份。

## 独立复核

[外部脚本](2026-11-07-ax-b01-p5-pairing/verify_case.py)核对候选源材料和实际二进制，每次启动前后核对同一制品。对固定的 AX-B01 IR 和任务清单，脚本按原始夹具重建预期判定、封套、单次执行和用例记录，比较进程状态与全部原始输出字节。复核适用此处固定样本及其错配。正式独立 checker 的通用 IR 重建和工具接受仍分别验收。

| 实际运行 | 结果 | 用例记录原始 SHA-256 |
| --- | --- | --- |
| `base` | `completed` | `3b06ca3c305d24c3070370cb43dad4b8408c42cfabb7c96baebb1176354487dd` |
| `boundary` | `completed` | `9c53d3df899b18ecc325810c2fb27f96606011d13d407c8ef8050d85f95800be` |
| `invalid`，另给黄金夹具 | `invalid` / `fixture-precondition`，只记录输入 | `0a3f827689d83a6e07a7128d81f2c87424d3529c621327d32bddd9e1488dfb6f` |
| `boundary`，281 bytes | `resource-exhausted` / `host-byte-limit` | `7bca0def788a299e56e03551827186cd9e514a4dee13f395ba4b15e5487e0e08` |
| `boundary`，缺少黄金 | `error` / `missing-golden`，保留成功输入 | `018f9f834b251d8d7d091016c0599e3877b43a9cb783cfe6d6dbdbd1c36746bc` |
| `boundary`，提供 `base` 黄金 | `error` / `fixture-binding`，保留输入和失败黄金执行 | `a9e7e2cdafbe1c22ab0246427955440cd2c10fafec02a923362d0f0c9c172283` |
| `boundary`，282 bytes | `completed` | `d46c9e3a35fe224756d056e8ea0f46bac503f6ab69e650cef76ba05cd0144778` |

另用一对各自合法的实际输出，把 `base` 的黄金执行记录与封套替换进 `boundary`。重新计算内部引用和整包摘要后，独立重建仍拒绝。既有单槽位验证重新通过八条实际记录及错误工具 pin 的预检，14 项相关 Rust 测试通过。新增 Rust 测试覆盖黄金预检超限时已完成输入仍可复核。

在仓库根复验留存制品：

```bash
candidate=docs/records/2026-11-07-ax-b01-p5-pairing/case-tool-candidate.jcs
binary="$(python3.14 -I -B -c 'import json,sys; print(json.load(open(sys.argv[1]))["artifact_path"])' "$candidate")"
python3.14 -I -B docs/records/2026-11-07-ax-b01-p5-pairing/verify_case.py "$binary" "$candidate"
python3.14 -I -B docs/records/2026-11-07-ax-b01-p5-pairing/verify_execution.py "$binary"
```

若需重新构建候选，先用上一批的[显式构建命令](2026-11-07-ax-b01-p5-execution-review.md#实际结果)生成发现 depfile，再将 `target/debug/examples/record_p5_fixture.d` 传给构建观察脚本。把 stdout 保存到新的候选记录并用该记录的二进制路径复验。当前公开回执版本决定见 ADR 0034。
