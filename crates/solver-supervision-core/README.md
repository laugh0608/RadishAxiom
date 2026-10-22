# 监督纯规则

私有 `radishaxiom-solver-supervision-core` 从 E3 host 提取 ABI 值编码、W/S 离线 cBPF、wire codec 与 cgroup 文件值解析，不依赖 Axiom IR。Rust 2024 / pinned 1.97.1、禁止 unsafe，仅依赖仓库自有 digest；没有系统调用、FFI、build.rs 或第三方依赖。

`WireLimits` 与 `CgroupLimits` 由调用方显式传入，无默认资源值。host 的兼容入口从既有 `PROCESS_LIMITS` 和原 E3 监督常量传入；未来 native 只能接受审阅后构建时固定的离线输入。`BOOTSTRAP_SUPERVISOR_ROLES` 固定 21 个 FD 角色，其中 pidfd/listener 在设置完成前仅为预留目标。

`bootstrap_start` 提供闭合启动描述，`handshake` 分离 Mac/S 本地时钟和单次 ARM；它们只是有界纯规则。cgroup 解析只产生文件值，合成身份、观察区间、OOM 归因与 `SimulationSupervisor` 继续由 host 管理。任何解析、摘要或握手成功都不认证来源、随机性、实际 FD、CLI 接受、镜像或运行资格，也不能构造真实成功捕获。

旧 host 的 e3 模块、构造方式、字节和拒绝行为保留。原容量兼容测试和既有独立离线检查负责核对旧字节；测试通过不构成形式证明或真实 Linux 资格。
