# 2026-11-22 AX-B01 独立复核交接与真实 solver 路径裁决

基线为 RadishAxiom `23e72e642ad96729679afbf07973b469823e5144`。本批在所有者委托范围内裁决后续评估路线。项目所有者仍负责输入、宿主信任及工具接受决定。实际执行另按各阶段授权。

## 合成 AX-B01 独立复核

分仓 `51d0a5122820628a24710e94589c4755a9ae284c` 补齐 P4-B 数值范围、节点总性和键基数，并用重封装包核对精确目标、WF / Pre 阻断和预算。分仓 `e4ff16fc6d82592932fd6a34294ff9ee5cfefaac` 接续完成 attestation 历史、消费侧信任、结论聚合和限定中止原因核验。两笔均在分仓本地 `dev`。验收沿用[固定交接指纹](../evidence/evidence-v0.2-machine-contract/independent-check-v0.2/packet-fingerprints.json)、[历史包指纹](../evidence/evidence-v0.2-machine-contract/independent-check-v0.2/handoff-fingerprints.json)和[结构化中止指纹](../evidence/evidence-v0.2-machine-contract/backend-structured-fingerprints.json)。

| 验收项 | 实际结果 |
| --- | --- |
| 逐目标重放 | 原容量三个 AX-B01 包在充足 Checker 预算下各完成九次 P4-A 与九次 P4-B 核对。P4-B 依次核对范围、总性、键基数及既有 guarantee / coverage，重封装错绑和前置阻断通过负例检查。 |
| 历史与信任 | 核对最后一个相容完成支持、历史信任、同目标冲突与错绑。九项合成 attestation 和四项结构支持完整的包为 `accepted-with-trust`，保留 19 条信任。同一份 Evidence 的 `certificate-required` 或禁用所需信任类别请求为 `incomplete`。 |
| 聚合与中止 | 核对合法 IR 的三种结论及决定性引用，拒绝变造结论、错引 attempt 和中止原因矛盾。独立复核九条重复键 `model-invalid`、一条模型世界零字节限制和一条重放世界零字节限制。 |
| 验收规模 | Go `1.26.7` Darwin arm64 核对 14 个固定原包、32 个重封装或请求副本。十份原生交接包为 7 个 `accepted-with-trust`、2 个 `rejected`、1 个 `incomplete`。为 `model-invalid` 提供 150,000 个集合项、2,000,000 步的 Checker 请求副本后，九条原因均通过。Go 全量测试、vet、格式、模块闭包、源码身份与仓库检查通过。 |

本机模拟测试的 `checker.source` 为 `sha256:66e0f593392c766ed81a331239bc554c66902d1d30723d48eba5db173f9a6fec`，测试二进制为 `sha256:f2d2952bfea942b2dedd9df124b7f62ef32e569c20ae492abf6356fa4db48c98`，本机 46 份回执索引为 `sha256:c676eb586d4b4231cd204dead28af272b528068270ddd6b7f6184216a84987fa`。分仓源码、测试制品和已发布 payload 各按精确身份管理。一般 IR、WF 逐字段诊断、无后端整包接受、通用证书、完整 SMT 公式等价性及 `component-error` 等原因仍待验收。主仓 M1 缺同一 Evidence 所需的九项实际后端结果。P6 保持 `closed / p6-not-evaluated`。

## 唯一待审替代路径

选定 **同一 cvc5 `1.3.4` 固定源码的 Linux AArch64 glibc Production 静态 CLI，以 `--no-poly` 对应的 `USE_POLY=OFF` 严格评估**。这是[有限裁决](../query/solver-cvc5-build-candidate-plan.md#首题运行交付的有限裁决2026-11-10)中的单一替代候选待审，当前为 `not-accepted`、`build_ready=false`、`execution_ready=false`。原启用 Poly 的候选和原发布 ZIP 保持各自的 `not-accepted`，停止并行推进。

- 截至本批，针对 LibPoly 固定提交 `3d5e6fbd98639cb0941b029e23ca17c0e3c4a80a` 的上游 issue 仍开放且无评论。整体声明冲突、Polyxx 覆盖及旧 `open_memstream.c` 的来源与授权仍待权威依据。已匹配的材料沿用原库存。 [LibPoly issue #113](https://github.com/SRI-CSL/libpoly/issues/113) · [C1 原审阅](2026-10-23-cvc5-c1-input-review.md)
- 重算固定 cvc5 源归档 `sha256:cbaa927c4d8085e38e7a097191bb9dd3a6780cc17fcde65cb156c9583e597760`，归档注释与提交 `f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341` 一致。在同一归档字节中核对 `configure.sh` 的 `--no-poly` 映射、顶层 `find_package(Poly)` 条件及 `src/CMakeLists.txt` 的 Poly / Polyxx 依赖和链接条件。静态开关提供可核对的裁剪点。有效 cache、图、生成头和最终 ELF 组成仍须分别取证。 [固定来源记录](solver-cvc5-source-review-2026-10-17/source-inputs.json)
- 从固定原包重算三候选 27 份 v0.5 query 的 raw 摘要并对回各请求。输入与输出声明容量均为 100，24 份唯一 query，大小为 265,107–962,850 字节，落在 1 MiB stdin 门槛内。本批核对的原字节只见 `QF_UFLIA`、Bool、Int、未解释 Text 排序、布尔组合与线性算术，查询正文没有乘法、除模或量词。由此选择单一待审候选。实际 argv、模型帧、求解行为、资源占用和精确重放能力仍由 E4/E5/E6 验收。 [v0.5 查询规则](../query/map-filter-query-v0.5.md) · [执行顺序](../query/solver-execution-implementation-plan.md#分批实施与交付门禁)

替代评估沿用相同源码、架构、glibc / GCC、Production、static、non-GPL、Editline、GMP、CaDiCaL、SymFPU 基线，只审 `USE_POLY=OFF` 导致的必需输入、patch 和配置差异。实际产物须登记新身份，按构建图、对象、链接记录、ELF 和许可清单证明有效闭包。原 C0/C1/配方及 LibPoly 原件作为原候选记录保存。本裁决仅写项目文档。

## 阻塞项与恢复条件

| 阶段 | 恢复条件及停止线 |
| --- | --- |
| C0 / C1 / C2 替代差分 | 下一离线批次只核定这一个替代配置。复用固定源码及已核对的 500 个输入文件，明确 Poly 专属输入、静态 patch 与步骤在替代图中的去留。其余构建输入、SDK 精确来源、许可、有效配置和无网络 recipe 仍须独立接受。发现 Poly 残留、额外依赖、实际许可缺项或超出本批范围时停并记录。 |
| L3 / G0 与构建宿主 | L3 仍为 `not-accepted`。复用已核对的 target、Rust、Python、Apple Git 材料，收口 target 发布清单的有限信任、Apple Git 精确源码缺口、Cargo 解析数据来源与许可，以及固定宿主的有限信任。G0 的构建环境、无写别名、独立终止及磁盘 / inode 硬限也须闭合。条件满足后，再分别核定 target 安装、Linux bootstrap 构建、L4 静态验收与 L5 交付 / 诊断授权。 [L3 接续](../query/solver-linux-channel-l3.md) |
| C3 / E0 / E4 | C1 与构建环境资格齐备后，受控构建并留存 cache、配置、真实对象与链接清单、ELF 和许可组成。E0 单独接受精确新 bytes。E4 固定 Linux AArch64 宿主、镜像、监督器、ABI、能力与加载边界，实测硬资源限制、失联终止及空树回收。候选或宿主身份漂移时停止。 [构建批次](../query/solver-cvc5-build-candidate-plan.md#批次占用授权与停止线) · [E4 矩阵](../query/solver-linux-supervision-design.md#e4-资格矩阵与本次结束条件) |
| E5 / E6 / M1 | E0 和 E4 通过且分别获准后，做最多八份既有协议校准，再单独做一次原容量 `wrong-add` guarantee。沿用 128 MiB / swap 0 / pids 2、外层 6 s、内部 5 s / 1,000,000 steps 和原流限额。身份、输出文法、时限、资源或隔离失败时留存并停止，不自动换候选。取得 correct 九项实际后端结果和四项结构支持后，再装配全 13 项，提交同一份 Evidence 给分仓独立复核并恢复 M1。 [首题验收](../development-plan.md#里程碑与完成标准) |
| P7 独立前置 | 提前登记 Node.js `24.19.0` 的精确目标制品、来源及随附许可、实际宿主、外层内存 / 时限 / 能力边界。该项沿自身资格与授权推进。 [首切片依赖](../axiom-pipeline-first-slice-dependency-review.md#收口顺序与两级出口2026-11-10) |

已投入材料按现有 C0/C1、L3 和分仓验收记录核对。本批只作一次公共 issue 状态核对、固定源码及原包的只读检查和文档裁决。累计工时、剩余工时及运行准备成本目前未知。下一批写入准备材料前，由负责实施与复核的项目所有者核定一轮离线差分的时间上限及剩余装置、维护预算。沿用既有预算边界。替代差分达不到进入下一步的条件时，记录精确缺件及恢复条件，暂停运行准备。

本批执行 `./scripts/check-repo.sh`、文档引用与 `git diff --check`。未启动 solver、构建或配置程序、镜像、宿主探针及发布流程，未安装依赖、触发 CI 或改写既有接受记录。
