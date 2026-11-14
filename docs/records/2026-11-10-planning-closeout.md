# 2026-11-10 首题收口规划

日期按 Asia/Shanghai。所有者确认收口方向，仅授权更新文档；不改代码、不执行环境操作、不提交或推送。

## 决定与边界

- [当前顺位](../status/current.md#近期顺位)与[开发计划](../development-plan.md#里程碑与完成标准)固定 AX-B01 验证/Evidence 中间交付，再完成真实 P0–P9。
- 收口后端结果与独立检查；真实 solver 路径按有限批次裁决，取得实际校准后补齐九项后端结果。Node P7 来源/宿主/硬资源缺口提前列入同一剩余清单。
- 独立正向 proof 不额外作为 attestation-allowed 流程前置；独立复核、certificate-required 拒绝、ADR 0009 迁移/group/历史/版本矩阵保持。
- 通用运行包装、额外来源链、新领域/IR/平台、SDK/IDE 与正式 Agent 实验后置；实际执行必须满足的来源、隔离、制品与授权要求未取消。
- 未改 ADR、IR/Evidence 规范、机器契约、锁定 fixture 或摘要；未接受待审 B1–B3、改选 solver 或扩张资源。Checker 分仓未修改。

## 验证与交付

首轮 `PYTHONDONTWRITEBYTECODE=1 ./scripts/check-repo.sh` 使用系统 Python 3.9，因类型联合语法/TypeAlias 不支持而 exit 1；保留该失败。改用本机已有 `/Users/luobo/.local/share/mise/installs/python/latest/bin/python3.14 -B scripts/check-repo.py` 后通过（3001 文件）；未安装或修改解释器。`git diff --check` 通过。没有 Rust/Go/Node/solver 运行、安装、容器/VM、原始输入取证或外部操作；静态材料检查不计为产品/独立证明验收。

启动时 dev 工作树干净，与本地 origin/dev 无 ahead/behind；未 fetch。文档保持未提交，既有实际运行缺口继续开放。
