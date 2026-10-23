# C2 SDK 布局与构建事件离线检查记录

日期：2026-10-23。用途：记录本批离线接线设计、可测试组件和真实库存检查，供后续实施者核对。接续 `e269188` 的 C2 配方；本文不接受许可、宿主或执行能力，不表示完成 SDK 组装、C3 构建或 E0。

## 交付与实际结果

- [接线设计](../query/solver-cvc5-execution-preparation.md)明确 SDK 写入顺序、权限候选、挂载 / 读取观察、构建进程树与外层 watchdog 分工、失败留证及清理停止线。
- [布局入口](../../scripts/prepare-cvc5-execution-review.py)直接复用原 C2 预检并从已绑定库存生成完整预期树；没有解包或执行入口。
- [事件规则](../../scripts/cvc5-build-support/event_rules.py)处理原配方依赖步骤的命令绑定、显式审阅声明、单调时间、日志摘要、资源声明与不可恢复失败；只检查有限声明一致性。
- [36 项测试](../../scripts/test-cvc5-execution-review.py)覆盖合成攻击输入、原 32 步合成事件序列及真实库存逐项对应；既有 33 项 C2 配方测试回归通过。

本批真实预检重核原 500 个输入文件、五源码及八文件 patch，通过后生成 **172 包、17,125 个归档条目合并为 14,719 路径** 的候选：1,367 目录、12,525 文件、822 符号链接、5 硬链接，普通文件合计 537,445,262 bytes。没有添加隐式父目录、遗漏已列成员或以宿主文件补目标；不是磁盘实际占用或 SDK 已可用的声明。

明确保留两类待审阅项：

1. `tar 1.34+dfsg-1.2` 中 `etc/rmt → /usr/sbin/rmt` 悬空。其余 826 个链接在候选虚拟树中解析到已列文件 / 目录。没有创建目标、安装包、移除链接或自动接受该缺口。
2. `bin/su`、`sbin/unix_chkpwd`、`usr/bin/newgrp`、`usr/bin/wall`、`var/local` 共 5 处 setuid / setgid 位在候选中列为移除；原权限单独保留。实际文件权限未改动，所有者映射及这些差异须在组装前审阅。

完整布局约 5.9 MB，保存在任务专用 `artifacts/cvc5-c2-execution-review-2026-10-23/sdk-layout-review.json`，摘要 `9bdb1a5d1deb76c56669abefe38ed386e03fda1fae92c29473493d7c459e96e8`。内容是预期文件元数据，没有第三方可执行载荷。生成入口、原配方、库存与输出身份见[验证记录](solver-cvc5-c2-execution-2026-10-23/validation.json)；重建使用设计文档的命令并指定新的输出文件。旧配方及其来源绑定未修改。

## 验证范围

实际运行 `python3 -O scripts/test-cvc5-execution-review.py`：36 项通过；真实库存测试从绑定 gzip 原字节重算摘要，对全部成员逐项核对类型、长度、摘要 / 目标、原权限和拥有者，并检查唯一悬空链接及权限差异集合。合成测试覆盖路径逃逸、非目录祖先、跨包冲突、循环 / 深链、歧义 `..`、硬链接类型 / 模式 / 符号链接穿越、特殊文件、条目 / 字节预算。

事件测试包含原 32 步完整合成序列、乱序 / 篡改命令、审阅门禁跳过、期限不续期、时钟回退、memory / swap / disk 保留额度、OOM / pids 拒绝、计数回退、日志逐流及累计超额、缺失 CMake trace、最后资源样本缺失、流关闭后写入、非零退出、取消 / 观察丢失 / 未归属输入、布尔值冒充整数及拒绝后继续。合成完成结果仍为 `execution_ready=false`，不认证审阅摘要或实际捕获。

既有 `python3 -O scripts/test-prepare-cvc5-offline-build.py` 的 33 项回归通过。真实新入口返回 **2** 并输出审阅候选，明确 `assembly_ready=false`、`execution_ready=false`、`build_ready=false`；这不是预检错误，也不是构建成功。`./scripts/check-repo.sh` 通过（2,868 文件），`git diff --check` 通过；日志身份见验证记录。

本轮没有改动 Rust 源码，未重跑 Rust workspace 测试；未执行上游工具、CMake / configure、编译器、pkgconf、容器、真实文件读取监控或负向资格探针。未安装 / 组装 SDK，未创建 `artifacts/cvc5-build-candidate-2026-10-23`，未发送上游消息、提交或 push。

## 仍未取得的能力

C1 的 LibPoly 许可接受仍阻断。SDK 扩展元数据、权限 / 所有者映射、悬空链接处置、实际组装与只读回读均未验收。构建专用 PID / inode 限额、观察间隔、真实文件读取后端、独立 watchdog、进程树终止及资源限额强制尚未形成；Python 规则不能填补这些 OS 能力。

既有 solver cgroup / S / B 规则具有两进程和受限再执行边界，本批不放宽它们，也未把模拟状态升级为真实监督器。下一批仅沿接线设计的具体缺口审阅，实际 SDK 组装、资格验证与构建仍须在 C1 闭合后按精确目标另行授权。
