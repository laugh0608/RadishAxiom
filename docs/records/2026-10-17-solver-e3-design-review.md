# E3 监督与能力边界设计审阅

日期：2026-10-17。用途：保存本批授权、设计选择、已发现风险和静态验证；读者为项目所有者与接续实现者。不记录任何实际 Linux 执行结果，不接受工具或宿主资格。

## 授权与提交

项目所有者要求先提交 E1–E2 实现及验收材料，再推进 E3 设计收口，明确控制端失联后的独立终止机制与 cgroup / syscall 能力边界；E0 继续作为真实执行硬门禁，保留原容量、旧字节和资源限值，不构建镜像、不运行探针或 solver、不修改系统配置、不 push。

启动复核为 `dev`、ahead 7，恰好前批 27 个文件，暂存区为空。21 份已记录的验证输入摘要一致，`git diff --check` 通过；按精确路径暂存并提交为 **`a0150c6` — `feat(solver): 完成 E1–E2 纯组件与模拟验收`**。提交后工作树干净、ahead 8。前批的 329 项 workspace、独立导出和旧字节结果见[原验收](2026-10-17-solver-simulation-validation.md)；本次提交不伪称重跑了这些测试。

E3 是本次新增设计任务，由主代理完成。未派生实施任务、创建执行器或改动 E1–E2 代码；首次提交授权不扩大为提交本批设计。

## 形成的提案

[ADR 0029（Proposed）](../adr/0029-solver-linux-supervision-and-capabilities.md)、[监督设计](../query/solver-linux-supervision-design.md)与 [syscall 策略](../query/solver-linux-syscall-policy.md)形成一个具体方案：

- D1：同一容器内 PID 1 持续监督，唯一可信装载子进程随后成为 solver；两个单线程任务共用原 128 MiB / 6 s，`pids.max=2`，不增常驻服务或 host broker。
- D2：READY / ARM 按已消耗的全局时间给出不可续期的 Linux 绝对 deadline；明确准备阶段无 ARM 时不启动 solver，以及 VM / 内核停顿不能由软件定时器覆盖。只读 cgroup 观测、OOM 归因、子进程回收、PID 1 退出和精确容器清理分层。
- D3：S / B / W 三阶段封闭 syscall 集合、明确 FD 生命周期与 ABI 审查。拟用一次性通知协调可信 B 的初次固定 exec，W 之后无 CONTINUE 路径；不使用 USER_NOTIF 检查不可信 pathname 后放行。

这些决定新增监督代码、一次性装载状态和内核 / runtime 退出确认信任前提，因此保持 Proposed，未擅自改成 Accepted。原 ADR 0028、query / P4 规则、E1–E2 模拟记录与资源常量字节保持。

## 关键审阅发现

1. **固定 fd + AT_EMPTY_PATH 不是一次执行保证。** Linux 允许非空绝对 pathname 并忽略 dirfd；原准备设计中的“一次装载”是未实现的目标，不能把该目标写成已有过滤器保证。新 B6 明确拒绝这种简单放行方案。
2. **USER_NOTIF 不能通用地消除 TOCTOU。** 官方文档明确警告；提案只协调已经受信任、单线程、无共享可写改参主体的 B，不读取不可信路径后作决定。源码无法建立这些阶段不变量，或允许 W 重装过滤器时，方案继续阻断。这里没有用几条动态测试替代安全性论证。
3. **S 自身占用整个 cgroup。** S 活着时 populated=1 不能被当作未回收错误，也不能伪造成事后空树；拟用子进程 reap + PID namespace init 退出 + 已取得资格的 runtime 终态确认，单独披露该信任方式。若要求事后直接 populated=0，当前无宿主写入方案不可满足，不自动新增权限。
4. **OOM 计数不是精确时序。** 本 cgroup 的 oom_kill 可能来自不同 OOM killer，观测区间也不能当成发生时刻。S 丢失、计数缺失、归因不明或与 deadline 顺序重叠时，保留未知并拒绝正常响应。
5. **跨时钟与暂停不能靠纸面公式认证。** 因果握手避免把消息延迟重新加到余量；时钟误差界 δ 和虚拟时钟运行假设仍未取得资格。没有为当前宿主填写数值或声称普通 OS 的物理实时上界。

资料于本次只读查阅，具体链接随设计中的相关主张保留：Linux man-pages 的 execveat / PID namespace / timerfd / pidfd / memfd / USER_NOTIF，Linux kernel 的 cgroup v2 / seccomp，以及 Docker 的 seccomp / resources / runtime metrics。它们支持接口解释，不证明当前 OrbStack 配置、精确 CLI 行为或构建供应链合格。

## 有限时间算例

以下标准库 Python 算例实际运行通过：2,700 组组合中 891 组允许模型中的启动，1,809 组拒绝；允许项的换算截止均不晚于模型全局 6,000 ms 减去声明 δ。输入覆盖准备晚于全局窗口、往返延迟、不同绝对时钟偏移和过期 ARM。

它只检查单位速率、无暂停、非负传输延迟下的设计算术；**不是内核探针、δ 校准、硬实时证明或宿主资格**。下列完整源码可独立复跑，不依赖 Rust 或 Docker：

```python
import itertools
import json

accepted = rejected = 0
for entry, setup, offset, ready_delay, arm_delay, delta in itertools.product(
    [0, 100, 3000, 7000], [0, 1, 1000], [0, 1000000, 1000000000000],
    [0, 1, 100, 3000, 7000], [0, 1, 100, 3000, 7000], [0, 1, 100]
):
    ready = entry + setup
    received = ready + ready_delay
    remaining = 6000 - received - delta
    deadline_linux = min(ready + offset + remaining, entry + offset + 6000)
    arrival_linux = received + arm_delay + offset
    start_allowed = remaining > 0 and arrival_linux < deadline_linux
    if start_allowed:
        assert deadline_linux - offset <= 6000 - delta
        assert received + arm_delay < 6000
        accepted += 1
    else:
        rejected += 1
assert 5500 + 1000 > 6000  # 从 ARM 到达起重给余量会扩大窗口的反例
print(json.dumps({"model": "unit-rate-causal-READY-ARM-only", "scope": "design-arithmetic-not-host-qualification",
                  "cases": accepted + rejected, "start_allowed": accepted, "start_rejected": rejected,
                  "assumptions": ["unit-rate clocks", "no pause", "nonnegative transport delays", "declared delta only"]}, indent=2))
```

运行入口与结果暂存于已忽略的 `.tmp/solver-e3-design-review/`。反例为 READY 在全局 4,000 ms 发出、5,000 ms 接收，余量 1,000 ms；若 ARM 在 5,500 ms 到达后重新计满余量，错误截止成为 6,500 ms。按提案绑定的 Linux 绝对截止，该 ARM 已过期，必须拒绝。

## 检查与交接

仓库级检查通过（2,672 文件），269 个本批文档本地链接有效，`git diff --check` 通过。相对 `a0150c6` 的 2,098 份既有源码、契约和规范逐字节一致，仅排除允许更新的 ADR 索引与执行层实施清单；Cargo.toml / Cargo.lock、原 ADR 0028、全部 query / P4 规则与实现均保持。本批没有修改 Rust 或锁文件，故未重跑 workspace / Clippy；前批测试结果只能作为 `a0150c6` 的既有证据。没有下载新的执行载荷、安装依赖、构建镜像、启动服务 / VM / 容器、运行 Linux 探针或 solver、修改系统设置、CI 或任何远程写入。

下一步是项目所有者接受 / 修改 ADR 0029 D1–D3，再进入具体 ABI / 内部传输格式与实现审阅；E0 的精确 CLI 系统库、完整链接库存、许可证接受及构建关联仍缺失。E3 设计方案不替代 E0，不开启 E4 / E5 / E6。新真实观察格式必须表达可信来源、时钟区间和未知归因，不能把 E1 的 simulation 改名冒充资格。

收口时八份 E3 文档改动未暂存、未提交。期间本地 `origin/dev` 引用已更新到 `a0150c6`，reflog 显示 `update by push`；这不是本代理执行的动作。本代理没有 fetch / push，最终 `dev` 与该本地引用 ahead / behind 为 0 / 0，不把提交后的历史 ahead 8 当作当前状态。无新增长期运行进程，有限算例与检查日志留在已忽略目录。

## 后续接受决定

2026-10-17，项目所有者明确接受 ADR 0029 D1–D3，要求先更新为 Accepted 并提交这批八份 E3 设计材料，再推进具体 ABI、内部传输格式和可离线验证的纯组件实现与模拟测试；主代理主持设计与验收，实现委派 gpt-6.1-sol / high。以上 Proposed、未提交和未授权实施的叙述保留原设计批次的历史事实，本段记录其后发生的接受。E0 和实际运行资格继续作为硬门禁；原容量、旧字节和资源限值保持，不构建镜像、不运行探针或 solver、不修改系统配置、不 push。
