# ADR 0014：Darwin App Sandbox container 与 runner 无状态边界

日期：2026-09-03

状态：Accepted

用途：处理 ADR 0013 synthetic microguest 探针暴露的 App Sandbox 自动持久 container，与“逐次 runner 无持久状态 / 无 container data 残留”门槛之间的冲突，并窄修订其 container 状态边界。

读者：checker runtime / launcher、Darwin 平台适配、产品签名与打包、安全审阅和安装 / 卸载维护者。

决策范围不包含：不修改 ADR 0013 的 Accepted 状态，不以继承型 helper / XPC service 形成 fallback，不读取或改写受保护 metadata plist，不修改公共格式、产品根、系统 service、生产签名、entitlement 或远程状态，也不执行 checker。后续 synthetic Linux feasibility 是否运行与是否通过由 ADR 0013 门槛及其独立授权决定，不由本 ADR 预先判定。

## 触发事实

ADR 0013 要求 per-invocation Hypervisor runner 同时满足：

- 独立签名并且只有 App Sandbox 与 Hypervisor 两项 entitlement；
- 每次请求创建新 runner process 与新 VM，不跨请求复用状态；
- 失败后没有 guest、runner、container data、VM image、日志或系统设置残留。

Synthetic bare-metal microguest 已证明 runner / VM / vCPU / descriptor / deadline / teardown 的低层链，但 runner 首次启动后，macOS 自动创建了：

```text
~/Library/Containers/dev.radishaxiom.synthetic.microguest.runner.a13/
  .com.apple.containermanagerd.metadata.plist
```

探针只在精确 `/private/tmp` 根运行，runner 没有主动写 container；临时根与 container `Data` 树已清理。系统保护的 28,896-byte metadata plist 和空父目录仍然存在，当前任务对其精确删除得到 `Operation not permitted`。

这不是 guest / checker 产生的数据，也没有进入产品或公共身份，但它是一次 App Sandbox 启动造成的持久 host state。因此，ADR 0013 的逐字门槛尚未通过。

## 公开平台约束

Apple 的公开文档明确说明：

- [Accessing files from the macOS App Sandbox](https://developer.apple.com/documentation/security/accessing-files-from-the-macos-app-sandbox) 与 [Configuring the macOS App Sandbox](https://developer.apple.com/documentation/xcode/configuring-the-macos-app-sandbox) 都说明 sandboxed app 首次启动时，系统会在 `~/Library/Containers` 创建并关联 container；这不是 runner 可关闭的可选写入。
- [Protecting local app data using containers on macOS](https://developer.apple.com/documentation/xcode/protecting-local-app-data-using-containers) 说明 App Sandbox data container 受系统保护；本机无法从当前任务删除 metadata 与该行为一致。已核查的公开 App Sandbox 配置没有“保留 sandbox policy 但禁止创建 app container”或“逐次执行后由普通 parent 原子销毁 container”的能力。
- [Embedding a helper tool in a sandboxed app](https://developer.apple.com/documentation/xcode/embedding-a-helper-tool-in-a-sandboxed-app) 要求继承型 command-line helper 只带 `com.apple.security.app-sandbox` 与 `com.apple.security.inherit`。这个受支持配置没有为 helper 单独增加第三项 Hypervisor entitlement 的位置；若依靠继承取得 parent 的静态能力，就必须把 Hypervisor 能力授予 parent，扩大产品主进程权限并失去 ADR 0013 的独立 runner profile。
- Apple 的 [Enabling App Sandbox](https://developer.apple.com/library/archive/documentation/Miscellaneous/Reference/EntitlementKeyReference/Chapters/EnablingAppSandbox.html) 还明确指出普通 child 不提供 XPC 的 privilege separation；[Creating XPC Services](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingXPCServices.html) 则说明 XPC service 由 `launchd` 按需管理、拥有自己的 sandbox，[Mac Technology Overview](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/OSX_Technology_Overview/SystemTechnology/SystemTechnology.html) 进一步明确其拥有自己的 container。XPC 会改变 per-invocation process / identity / lifecycle 边界，却不会消除 container。

以上结论只覆盖当前 Apple 公开接口和本机 macOS `26.6.2` 动态观察；它不是对私有 API、未来 macOS 或管理员介入清理能力的断言。私有 API、root cleanup、临时用户或系统 service 均超出当前产品边界，不能作为隐含 fallback。

## 方案比较

| 方案 | 能保留的边界 | 新问题 | 决策结论 |
| --- | --- | --- | --- |
| 继续要求每次调用后物理上不存在任何 container path | ADR 0013 原文字面不变 | 当前公开 App Sandbox 启动必建 container；所选 runner 不可实现 | 保持失败关闭，停止 Linux guest 实施，重新选择宿主 |
| 允许固定产品 identity 的 OS-managed container skeleton 基线 | 保留独立 runner、两项 entitlement、per-invocation process / VM、无 network / disk / host share 等 capability-bearing guest I/O device | 放宽“零持久 host state”；container 是 runner 可写 namespace，必须显式进入 TCB / 跨请求状态审阅 | **采用** |
| 继承型 command-line helper | 不新建 helper 独立 sandbox profile | parent 必须持有 Hypervisor 权限；helper 与产品共享 sandbox / container，权限和状态边界更宽 | 拒绝 |
| XPC service | runner 可有独立 entitlement | 自有 container；`launchd` 管理、可复用进程，偏离逐次 runner 与 parent suspended identity 链 | 拒绝作为无残留修复 |
| 非 sandboxed Hypervisor runner | 不创建 App Sandbox container | 丢失 host filesystem / network 的内核级外层 containment；改变 ADR 0013 信任边界 | 只能在替代 ADR 中重新比较，不作为本 ADR fallback |
| root / uninstaller / 临时用户清理 | 可能删除或隔离部分持久状态 | 管理员批准、系统状态、竞态与新 TCB；不能作为每次请求的普通路径 | 拒绝 |

## 决策

将“无持久状态”收窄为“无请求派生的可复用语义状态”，允许一个由产品签名 identity 固定、macOS 自动创建和保护的 App Sandbox container skeleton 作为**安装级 host state**。它不是 guest artifact、request / result、cache、qualification 或 runtime identity 的组成部分，也不能成为 runner 输入源。

ADR 0013 的实施门槛 7 同步窄修订为：

1. 每次 invocation 后没有 guest、runner process、VM / vCPU、mapping、临时文件、VM image、日志、credential 或请求派生 container data；
2. 只允许固定 bundle identifier 对应的 OS-managed container 与 opaque metadata 基线；禁止逐请求 bundle identifier、container、App Group 或 security-scoped bookmark；
3. runner 不调用 home / container path discovery，不把 container、host path 或 writable device 暴露给 guest，不从 container 读取 boot、checker、bundle、policy、cache 或结果；全部执行输入仍只来自 parent 验证并传入的 descriptor / bounded pipe；
4. container 是 runner 默认可写的 host namespace，必须明确进入 runner TCB 与跨请求状态威胁模型。任何请求派生写入、可观察的 pre/post 增量、跨请求读取或无法区分的系统写入都保持失败关闭；不能以“系统自动创建”为由把任意 container 内容列入允许基线；
5. 安装、升级与卸载必须单独定义 container inventory、用户授权的删除路径与保留策略；per-invocation launcher 不取得 root、Full Disk Access 或额外 entitlement 来清理它。

本决策不声称 App Sandbox container 已被证明完全不可用于跨请求通道。相反，它承认 container 是已选平台 primitive 固有的持久 namespace，并把 runner 不读写它作为 TCB 义务。若未来要求即使 runner TCB 被攻破也不能写任何跨请求 host state，则本决策不足，ADR 0013 所选架构应保持不可实现并由替代 ADR 重新选型。

## 后续停止线

- 后续 synthetic Linux feasibility 已在单一当前主机证明真实非特权 process / descendant、syscall 拒绝、exact 128 MiB 与多轮 cold lifecycle；这不包含 checker / bundle、生产 TCB / signing 或公共身份迁移，`NativeIsolationStatus = RequiredNotProven`、active runtime 0 仍不变；
- 下一步只允许另行提出 guest checker source / artifact acceptance、host + runner + guest identity 迁移和 product packaging 设计；在分别授权前不执行 checker，不修改 launcher policy `0.3`、registration、receipt 或 Execution Profile；
- 不通过读取、改写或删除当前受保护 metadata 来制造“零物理持久状态”结论；产品 packaging 必须建立允许基线和请求派生增量的独立审计；
- 若出现请求派生 container 写入、runner 跨请求读取、无法审计的非 opaque 增量，或产品签名 / 分发无法维持固定 identity，保持 runtime unavailable 并以替代 ADR 重新比较宿主。
