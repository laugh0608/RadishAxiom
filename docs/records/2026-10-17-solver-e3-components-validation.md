# E3 ABI、内部传输与监督纯组件验收

日期：2026-10-17。用途：记录 ADR 0029 接受后的离线实施、独立复核和兼容性结果。目标读者：项目所有者、执行层实现者与验收者。不包含 Linux 运行资格、真实 cvc5 接受、镜像构建、探针或 solver 结果。

## 授权、提交和职责

项目所有者明确接受 ADR 0029 D1–D3，要求先更新为 Accepted 并提交八份 E3 设计材料，再推进具体 ABI、内部传输格式和可离线验证的纯组件与模拟测试。启动时 `dev` 与本地 `origin/dev` 引用一致，工作树恰为前批八份设计文档。接受决定及设计材料已精确提交为 **`e2d36ce` — `docs(solver): 接受 E3 Linux 监督与能力边界`**，提交后工作树干净，ahead 1。暂存首次受沙盒 `.git/index.lock` 写权限阻止，使用已授权的精确路径重试成功；没有扩大提交范围。

主代理主持接口和验收，三个实现任务明确委派 `gpt-6.1-sol / high`，分别负责 ABI / 策略、内部封套、监督 / cgroup；各任务只写分配的新文件。主代理完成跨组件原容量集成、独立 Python 核对、实现审阅与最终文档同步。没有新增依赖、修改 lockfile 或把模拟对象改名为真实接受 / 资格。

## 交付与证据边界

- [具体 ABI](../query/solver-linux-abi-v0.1.md)：固定版本来源、AArch64 数字 / 结构及纯策略生成和解释；没有 FFI 调用、内核安装或 Linux 制品。
- [S 运行策略](../query/solver-supervisor-policy-v0.1.md)：固定 21 个 FD 角色和独立读写 / 终止 / 通知能力，S 不继承 W / B 允许集合；不深检指针或认证 FD 来源。
- [内部封套](../query/solver-bootstrap-wire-v0.1.md)：`bootstrap-control-v0.1` 的 24-byte 头、闭合正文、绑定、方向序号、流预算、单帧背压和失败毒化；匹配摘要不认证来源。
- [监督与 cgroup 模拟](../query/solver-supervisor-simulation-v0.1.md)：因果 READY / ARM、一次创建 / 首次装载、精确成员与只读解析、OOM 观察区间、终态和清理；输出固定 simulation。

上述实现位于私有 `solver-diagnostic-host`，全 crate `forbid(unsafe_code)`；没有文件、进程、网络、真实时钟、线程、环境或任意执行回调。测试 / 导出程序可读取仓库合成 fixture、写入新的忽略目录；它们不启动 solver。纯策略的解释器结果不等于 Linux verifier 接受、实际 syscall 拒绝、可信装载成立或资源资格。

E0 的精确 CLI 系统库、完整链接库存、许可证接受和构建关联仍未闭合；时钟误差界、内核 / runtime、syscall 适配、独立终止与整树确认也未取得运行资格。没有通过布尔标志、模拟通过或本地策略 bytes 来解除这些门禁的入口。

## 审阅修正

1. 双方向各给 65,536 控制 bytes 会把总额翻倍。实现改为每方向 32,768，总计不超过原设计 65,536；query / stdout / stderr 原上限不变。这是内部封套额外收紧，不扩大 solver 预算。
2. 单帧写缓冲最初在提前超限检查返回错误后可继续发送。修正为除了背压之外的所有错误永久毒化，包括消费越界；拒绝后不能重新开启正常路径。
3. 解码器的语法成功不等于绑定匹配。新增绑定模式，在完整 160-byte 绑定前缀核对 attempt / request / policy / image / nonce 后才复制正文；正文和后续帧不能更换绑定。
4. 首次装载通知补齐 syscall number 与通知 flags 检查，不能只核对 syscall 参数；所有相关整数使用完整 ABI 宽度。`RUSAGE_THREAD=1` 与 `RUSAGE_CHILDREN=-1` 区分，禁止把子进程资源查询误列为自身查询。
5. cgroup 观测只通过有界 parser 建立，外部不能手工构造跳过配置 / 成员 / 区间检查。基线已有资源故障事件、计数回退和 `memory.oom.group` 漂移都不能走正常路径。
6. 生命周期完成与正常响应资格分开；非零退出 / 信号保留实际值，只有完整且干净的退出零才有模拟正常响应资格。S 已死亡时不虚构由死去的 S 发出的 kill；保留依赖 namespace 收束的意图及事实缺失。

## 原容量接续与独立路径

`tests/e3_workflow.rs` 使用既有原容量 AX-B01 wrong-add guarantee：query 为 962,642 bytes、501 个自由符号，原摘要 `sha256:5ba58e0d9754c3448f299ce4d9be2060c2d91d829253ec3e4a170e0d4d07a85a`。query 先分块进入内部封套，按 113-byte 片段增量解码，重新核对实际 query 长度与摘要，再推动唯一创建和首次装载模拟。合成 stdout / stderr 经同一封套复原，在双 EOF、子进程回收、S final、runtime 状态与精确删除的模拟事实完整后，才接既有模拟适配、P4 模型解码和 P4-B 精确目标重放。

导出程序 `export_e3_offline` 只接受新的 `.tmp/<name>` 目录，逐文件使用 create-new，不覆盖既有结果。它保存 W / S 两份实际过滤器 bytes、双向封套、原 query、两流、request / response / candidate / world / replay；各输入均是模拟数据。独立脚本 `scripts/check-solver-e3-offline.py` 不加载 Rust 实现：解释实际 cBPF 指令，逐项检查手工预期的 syscall / FD / 高位 / 内存 / arch 反例；独立解析封套及绑定，并对三行具体世界直接检查主键、Pre 和 wrong-add 的加减差异。它只做该有限见证的检查，不是通用 SMT 求解器或完整独立 checker。

复现入口（工具已验收安装，离线运行）：

```bash
cargo +1.97.1-aarch64-apple-darwin test --locked --offline -p radishaxiom-solver-diagnostic-host
cargo +1.97.1-aarch64-apple-darwin run --locked --offline -p radishaxiom-solver-diagnostic-host --example export_e3_offline -- .tmp/solver-e3-offline-export-new
python3 scripts/check-solver-e3-offline.py .tmp/solver-e3-offline-export-new
python3 scripts/test-solver-e3-offline.py
```

## 实际验证与交接

独立导出的机器结果、13 份导出文件摘要和生成输入摘要见 [offline-results.json](solver-e3-components-2026-10-17/offline-results.json)。原始导出保留于忽略目录 `.tmp/solver-e3-offline-export-c`；仓库保存生成入口与合成输入，可在新的目录重跑，不将摘要误称为完整原材料。ABI 文档分别列出上游固定 tag、两份维护者 fixed-commit 补充来源与许可；没有虚构上游 raw digest 或实际构建接受。

| 已执行检查 | 实际结果与边界 |
| --- | --- |
| W 过滤器独立 Python 核对 | 3,176 个手写预期案例通过；782 条指令、6,256 bytes；SHA-256 `2f5ff64bffb3b8cd438049d8f33d6ce86f9d3c72f4d61add5eba7da056a04e8f` |
| S 过滤器独立 Python 核对 | 1,450 个手写预期案例通过；980 条指令、7,840 bytes；固定合成 FD 映射的 SHA-256 `cf0ff9e3b57b8a0b3fa38414082a128922eb09ad9c14f9a5a227327a9572b57e` |
| 封套与有限见证独立核对 | Mac 17 帧、S 7 帧，累计控制 4,576 bytes；query 与两流原样复原，request / response / candidate / world / replay 摘要绑定与三行具体反例通过 |
| 时间矩阵 | 2,700 组偏移、延迟和误差参数，实际状态机与独立单位速率公式比较：891 组接受、1,809 组拒绝；没有把合成误差界当作宿主资格 |
| 独立检查器负例 | 6 项通过，包含全放行 / 全拒绝策略、坏指令、封套损坏 / 截断 / 序号、重复 EOF 和累计预算 |
| Rust 格式 / clippy | 指定工具链 `fmt --all --check`、workspace / all-targets / all-features clippy `-D warnings` 通过；两处 Copy 类型的多余 clone 已修正，无 lint 抑制 |
| 旧字节与依赖 | 与 `e2d36ce` 启动基线的 2,071 个文件对照；仅本批模块注册及三份 E3 设计 / 计划文档变化，其余 2,067 份逐字一致；旧 IR / query / P4、fixture / contract、Cargo.toml / Cargo.lock 与资源值保持 |

全 workspace / all-targets 的 `--locked --offline` 测试已实际退出 0：29 组、376 项通过、0 失败、1 项既有 ignored（`solver::tests::legacy::export_legacy_materials`，仅在显式导出时运行），日志各组时间合计 357.39 s。本批 E3 共 47 项：ABI / W 6、监督 / cgroup 18、S 策略 7、wire 14、原容量流程与时间矩阵 2。完整日志保留于 `.tmp/solver-e3-workspace-test.log`。`./scripts/check-repo.sh` 通过 2,693 个文件，包含文本卫生与本地文档链接；最终 `git diff --check` 通过。

完整回归的实际入口为：

```bash
cargo +1.97.1-aarch64-apple-darwin fmt --all --check
cargo +1.97.1-aarch64-apple-darwin clippy --workspace --all-targets --all-features --locked --offline -- -D warnings
cargo +1.97.1-aarch64-apple-darwin test --workspace --all-targets --locked --offline
./scripts/check-repo.sh
```

验收结束时，本批实现与验收材料留在工作区，尚未再次提交；当时 `dev` 相对本地 `origin/dev` ahead 1，即已授权的设计提交 `e2d36ce`。项目所有者随后明确要求提交工作区更改，本批实现与验收材料据此归档；最终提交号与工作区状态由提交后交接报告。没有刷新远端、push、安装依赖、构建镜像、运行 Linux 探针或 solver、修改系统配置。没有执行六平台验收或真实 syscall / 资源资格测试；E0 精确 CLI 接受、真实 bootstrap / FFI、内核安装和 E4 / E5 仍未完成。

下一可审阅切片是实际 bootstrap / FFI 的 ownership、设置顺序、部分 I/O / errno 与固定制品配置设计，以及 E0 缺口补证；镜像、探针和真实 solver 保持分别授权。
