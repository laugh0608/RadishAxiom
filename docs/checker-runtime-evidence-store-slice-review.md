# Checker runtime qualification / attempt store 切片审阅单

状态：`checker-runtime-store-v0.1` 六项能力已在 Darwin 合成临时根闭合；真实产品安装与 qualification 仍未授权
实施日期：2026-09-01

## 交付结论

本切片补齐 [ADR 0012](adr/0012-product-checker-runtime-host-and-persistence-interface.md) 中 `checker-runtime-store-v0.1` 的最后两项能力：

- `create_qualification_exclusive(registration, qualification_bytes)`；
- `append_attempt(registration, bounded_observation)`。

实现只复用既有 `radishaxiom-checker-runtime-darwin-store` capability 和 exact `libc 0.2.189`，没有新增 dependency、feature、C shim、平台 facade 或网络能力。所有文件系统测试只使用测试进程创建并自动清理的 `0700` 合成临时根；没有读取真实产品根、下载 / 安装 / 执行 checker、发现 provider credential、激活 qualification、修改登记状态、写远程状态或 push。

这两项是持久化原语，不是 qualification 判定器。`PersistedQualification` 只返回相对存储身份与 document digest，不产生 `Qualified`、`Active` 或可供产品选择的类型；目录存在、exclusive rename 成功或 exact reread 均不能单独说明三条 checker 结果已经由完整 result consumer 接受。

## 输入与格式边界

`QualificationArtifacts` 对既有公共 `radishaxiom-checker-runtime-qualification-record` `0.1` 做 strict canonical / closed-shape 重读，并精确绑定：

- `registered-inactive` registration ID / record digest、target 和 artifact；
- launcher policy `0.3` digest 与 execution profile；
- 重新按同一 policy / registration 验证的 installation receipt digest；
- policy 固定的三条 scenario、canonical companion 原始长度 / SHA-256、现有 Independent Check result document digest、outcome 和 checker identity。

本切片实施时，Rust 与 Python oracle 对三份简化合成 companion 形成完全相同的 2,020-byte qualification record：raw SHA-256 为 `sha256:e09b055f2784a3df2e9fc81c4f204f083484ba04231cba03069ea55a0b916f1a`，document digest 为 `sha256:c82f6576c49d55f4fcc30b6e2419e5497bfd2e10aaa720dedd062baf71cd3b97`。后续 [result consumer 切片](checker-runtime-result-consumer-slice-review.md)已将输入升级为完整公共 result 并把 qualification 接到单一 consumer；qualification、installation receipt、launcher policy 与 Independent Check result 的公共格式均未改变。

`BoundedAttemptObservation` 是 store 接口的闭合内存输入，只允许：

- stage：`installation`、`qualification` 或 `invocation`；
- 与 stage 相容的 failure / identity / resource classification；
- 最长 64 bytes 的小写 ASCII 稳定 code；
- UTC 秒级 observation time。

它没有 message、argv、绝对路径、环境值、credential、stdout / stderr 或用户数据字段。store-local attempt document 使用私有 `radishaxiom-checker-runtime-attempt` `0.1` canonical envelope，绑定 registration、单调 ordinal 和 bounded observation；这不是新增公共交换格式。

## Descriptor-relative 状态机

Darwin 上 qualification、attempt、各自 staging 和 registration lock 的 root 以下访问全部通过已持有的 directory descriptor、单 component no-follow lookup、exact inventory、mode / link 检查和 full-sync 完成。新能力在非 Darwin 构建明确返回 `unsupported-store-capability`，不提供 path-based 较弱 fallback。

qualification 按 registration 与 qualification document identity 写入 slot 外的：

```text
qualifications/<target>/<format>/<registration-digest>/<qualification-digest>/
  qualification-record-v0.1.jcs
  companions/
    ax-b01-correct.jcs
    chk-digest-01.jcs
    chk-resource-01.jcs
```

同 registration 的真实 OS lock 串行化写入。staging 只接受 exact record + 三文件 inventory，逐文件 full-sync 后以三 flags `renameatx_np` no-replace 发布，再同步 final / staging parent 并从 final descriptor exact reread。相同 destination 已存在也返回 `qualification-exists`；字节、inventory、mode 或 link 漂移返回 mismatch / boundary error，绝不覆盖。slot receipt 在 qualification 与 attempt 写入前后保持逐字节不变。

attempt 按 registration 写入：

```text
attempts/<target>/<format>/<registration-digest>/
  <20-digit-ordinal>-sha256-<document-digest>/attempt-v0.1.jcs
```

每次 append 先在 registration lock 下 exact 重读全部 final inventory，要求 ordinal 从 0 连续、目录 / 文件闭合、document digest 与路径及 registration 精确绑定；随后形成下一 ordinal 的 deterministic staging，以同一 no-replace / full-sync / final reread 顺序发布。相同 observation 再次提交也形成新的 ordinal，既有 attempt 不修改、不覆盖，后续成功也没有删除入口。容量在 1,000,000 项处失败关闭。

## 并发、恢复与失败关闭

test-only 独立进程矩阵证明：

- 两个 qualification writer 得到恰好一个 `created` 和一个 `exists`；
- 两个 attempt writer 得到唯一连续 ordinal 0 / 1；
- qualification 在 lock、artifact 写入、staging verify 后崩溃，exact retry 才完成 create；rename 或 parent sync 后崩溃，retry 只观察 `exists`，不再次写入；
- attempt 在 lock、file 写入、staging verify 后崩溃，exact observation retry 恢复同一 ordinal 0；rename 或 parent sync 后崩溃，已发布 ordinal 0 保留，同一 observation 的下一次显式 append 形成 ordinal 1；
- qualification extra entry、attempt hard link、inventory gap、digest / registration / mode / link 漂移均阻断后续写入。

进程 crash 矩阵不等于物理断电证明；`F_FULLFSYNC` 仍只是当前 kernel / filesystem / hardware 边界内的 best-effort durability observation。当前主机也没有第二个可安全使用的 volume，因此 `EXDEV` 仍只有显式错误映射而没有真实跨 volume 运行证据。同 UID 恶意进程仍在 ADR 既定 DAC 威胁边界外，不能由 descriptor API 冒充不可篡改。

## 验证与停止线

使用精确 `+1.97.1-aarch64-apple-darwin` 已通过：

- `cargo fmt --all --check`；
- locked / offline workspace test：core 40 项、Darwin 平台 crate 3 项；
- locked / offline workspace Clippy，`-D warnings`；
- Python launcher oracle 21 项及 qualification canonical golden 交叉复核。

仓库级生成、schema、文本与 Git 差异门禁的最终计数统一记录在[当前状态](status/current.md)，避免在本审阅单复制易漂移批次数字。

`checker-runtime-store-v0.1` 的六项持久化 capability 至此已闭合，但完整 launcher policy 仍为 `specified-not-implemented`。后续本地切片应单独审阅两层业务 manifest 或单一 Rust Independent Check result consumer；真实 immutable asset fetch / install、产品绝对根、checker 获取 / 执行、spawn / isolation、qualification 协调与 `registered-inactive -> active` 继续分别验证、分别授权。
