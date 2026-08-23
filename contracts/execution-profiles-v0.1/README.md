# Execution Profile Contract v0.1

本目录把 ADR 0005、0006、0008 与 Toolchain & Adapter Identity Registry 已冻结的执行身份收口为单一机器契约，固定：

- cvc5 `1.3.4` / `QF_UFLIA` adapter 的完整允许参数序列、stdin / stdout / stderr framing、内部 `rlimit` / `tlimit`、外层 stream / wall-clock / memory 限制和操作失败分类；
- Node.js `24.19.0` invocation 的 Permission Model、精确只读 target module grant、清空环境、BigInt / UTF-8 codec、输出与进程上限，以及禁止网络、文件写入、子进程、worker、WASI、addon、inspector、npm 和动态代码的能力边界；
- Go 独立 checker request 七项 limit 的精确默认正例、确定性计数位置、固定逻辑内存计费表、外层 OS hard limit 伴随边界，以及内部资源不足可形成结果、外层 kill / crash / 截断只能形成进程失败记录的停止线；
- Alethe / CPC 仅为未验收候选，受支持 certificate profile 集合为空；`certificate-required` 与 `attestation-allowed` 的结论继续以 Independent Check Contract 和 `CHK-PROOF-01` / `02` 为唯一权威，本契约只保存反向引用，不复制 outcome、trust 或 code。

`manifest.jcs` 是唯一规范机器表示；`fixtures/positive/` 是从 manifest 生成的精确投影，不是第二个配置来源。`fixtures/negative/` 覆盖未知字段 / 版本、顺序与重复、limit 缺失 / 零值、cvc5 未登记 option / 环境 / 随机种子 / 路径、Node option / 环境 / 能力 / codec / output limit、checker 计数 / 进程边界、certificate 越权和来源摘要漂移。除本 README 外，目录内容全部由生成器维护。

生成：

```bash
python3 scripts/generate-execution-profile-contracts.py --write
```

只读校验：

```bash
python3 scripts/generate-execution-profile-contracts.py --check
```

本契约保持 `level: specified`。它不会下载、安装或运行 cvc5、Node、Go checker，也不表示任一工具 payload、平台隔离、limit 数值或 certificate checker 已经通过真实验收；外层硬限制在不同 OS 上的具体机制与六平台观察值仍须在实现任务中绑定伴随记录。
