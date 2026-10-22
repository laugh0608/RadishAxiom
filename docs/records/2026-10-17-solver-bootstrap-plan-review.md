# bootstrap / FFI 方案与 E0 后续补证验收

日期：2026-10-17。用途：记录 E3 离线组件之后的原生实施方案审阅、来源补证、范围和待确认决定。读者：项目所有者、实施者与验收者。本批不构成原生程序、工具接受或运行资格。

## 启动、授权与分工

项目所有者要求继续真实 bootstrap / FFI 实施方案和 E0 缺口补证，主代理主持设计与验收，具体工作委派 gpt-6.1-sol / high；原容量、旧字节、资源值和外部执行边界保持。启动检查为 `dev`，HEAD `c489ec2`，工作区干净，相对本地 `origin/dev` ahead 2；没有刷新远端。

主代理负责 ADR、最终实施方案、跨端绑定 / 固定策略身份和验收。两个 gpt-6.1-sol / high 任务分别完成原生可行性独立审阅，以及 E0 公共来源 / 固定源码归档补证与离线复核工具；没有委派修改旧 Rust 实现、执行 Linux 载荷或远程写入。

## 交付与关键修正

- [ADR 0030（Proposed）](../adr/0030-solver-bootstrap-ffi-and-build-provenance.md)列出 D1 原生宿主与共享 core、D2 真实绑定 / 观察、D3 可追溯构建候选三项独立决定，尚未接受。
- [实施方案](../query/solver-bootstrap-ffi-implementation-plan.md)固定模块责任、启动描述候选格式、Mac/S 状态分离、S0–M7 顺序、FD / 信号 / 错误处理、构建输入和验收批次。
- [独立审阅](../query/solver-bootstrap-ffi-review.md)保留源码 / 接口依据和真实落地缺口；它不修改 Accepted ADR 或实际过滤器。
- [E0 补证](2026-10-17-cvc5-provenance-followup.md)保存取得材料、失败与可重跑核对；原 CLI 的完整链接库存 / 来源关联缺口不被配方证据替代。

审阅后纳入方案的具体修正：

1. 收 listener、重映射与关闭设置 FD 必须早于 S filter；否则最终策略会禁止自身后续设置。
2. 固定 S 21 个 FD 数字与实际 bytes 身份，避免把生成器摘要冒充动态实例摘要。READY 时还未取得的 pidfd / listener 仅为计划角色，取得后核验才能收紧与 CONTINUE。
3. S / W pipe 的阻塞属性分开；B 重映射使用无目标冲突的保留源槽，父端关闭多余 child 端保证 EOF / EPIPE 有意义。
4. std 的 main 前代码、handler / altstack / SIGPIPE 状态纳入 TCB；B 无 handler、无分配尾段，mask 跨 exec 的兼容风险显式保留。
5. 真实 Mac 不向 S 提供虚构的本地 `make_arm` 状态；分开两套时钟责任，模拟对象不升级来源。
6. 增加闭合启动描述，解决 READY 前 request 绑定从何而来；描述 / manifest / image 摘要层级避免循环自引用，回显不认证镜像或许可。
7. 单 reader 的首次 POLLIN 只触发一次 RECV；O_NONBLOCK 不是通知 ioctl 的非阻塞保证。v6.12 源码推论须由实际内核资格复核，不据此声明硬实时。
8. cgroup / waitid 的自然退出竞态按 Proposed 过渡记录处理，保留全部原始事实，最多一次额外读取，不掩盖额外 PID / 资源事件或延长期限。

## 证据与许可边界

Linux v6.12 seccomp 实现、Rust 1.97.1 Unix 初始化源码及官方 man-pages / kernel / Docker 文档的精确引用均在上述两份方案中。网页只读核对用于事实和控制流推论，没有复制 GPL 内核实现、第三方源码主体或许可全文到仓库，也没有声称保存了网页原字节 / raw digest。E0 下载来源的实际字节身份与适用许可单独列在补证清单，不能与网页阅读混称。

Rust / musl 候选意味着新的原生依赖接受责任，即使 Cargo 不新增 registry 依赖也不能省略。D3 只建议准备新候选的可追溯构建方案，未更换当前 CLI、未编译 cvc5；任何新 bytes 都要独立接受和校准。本次不作对外分发或整包许可证通过结论。

## 实际验证与交接

主代理对最终实施方案与 ADR 再作交叉审阅，独立审阅者复核无阻断问题；结论仅限本轮设计一致性，不将计划中的 F1–F4 或 E4 / E5 计为通过。

实际执行：

- `python3 scripts/test-cvc5-provenance-followup.py`：8 项测试通过，包含错误状态、摘要、分页、归档配方 / 取得状态篡改与非普通文件拒绝。
- `python3 scripts/check-cvc5-provenance-followup.py .tmp/cvc5-provenance-followup-2026-10-17 .tmp/solver-bootstrap-plan-2026-10-17/provenance-root-recheck.json`：4 份真实响应核对通过；主代理生成结果与持久观察 JSON 逐字一致。
- 基线核对覆盖 2,104 个文件，其中 2,102 个保持原字节；仅 ADR 索引和执行实施清单这两处预期路由文字变化。Rust、Cargo 声明 / lockfile、契约、原资源、旧 profile 与已有 E0 / E3 原始观察不变。初次严格比较将这两处已知路由改动列出；逐项审阅后单独归类，没有修改基线或掩盖实现漂移。
- `./scripts/check-repo.sh`：通过，检查 2,702 个文件；日志保存在 `.tmp/solver-bootstrap-plan-2026-10-17/check-repo.log`。最终 `git diff --check`、差异及未跟踪文件复核通过，无权限变化或越界文件。

四份新增 GET 响应只有 artifacts 空列表、两份 attestation HTTP 404 和固定缓存配方；404 不是不存在证明。四个配方归档的下载审批在等待后由工具报告 `aborted by user`，未观察到下载执行或取得归档，未重试；不能记作网络失败或摘要通过。原 CLI 的 B1 / B2 / B3 仍未闭合，不生成 accepted payload。

本批没有 Rust 实现或依赖改动，未重跑 Rust workspace；没有构建 binary / 镜像、运行探针 / solver、修改系统配置或 push。新增本批临时基线 / 检查材料约 344 KiB，来源 / 获取记录约 32 KiB，均在对应忽略目录保留；没有新增后台执行器。旧来源材料与 ZIP 保持。

共 13 个本批文件未提交，暂存区为空；`dev` 相对未刷新的本地 `origin/dev` ahead 2。下一步只等待 ADR 0030 D1–D3 的逐项选择；接受设计不自动授权工具下载 / 安装、构建、镜像、资格探针或 solver 运行。

## 随后接受与接续授权

项目所有者于 2026-10-17 明确接受 ADR 0030 D1、D2、D3，要求先提交本批方案与补证，再推进 F1 纯共享边界和启动描述实现，并准备 D3 构建候选方案。对应 ADR 和当前状态已更新；上述初始审阅时的 Proposed 与未提交状态是当时事实。主代理主持设计与验收，具体实现继续委派 gpt-6.1-sol / high。本次接续不扩大到 F2 可调用 FFI、镜像、探针、solver、系统配置或 push。
