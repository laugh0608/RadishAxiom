# Keyed Finite Table Corpus v0.1

本目录是 RadishAxiom 首个目标领域的已提交生成语料。正式范围、格式、可信边界和维护规则见[有键有限表基准语料库 v0.1](../../docs/benchmarks/keyed-finite-table-corpus-v0.md)。

机器入口：

- `corpus.json`：语料版本、语义 / IR / Evidence 绑定、生成器摘要和任务清单；
- `ax-b01`–`ax-b04/task.json`：每题任务 identity、候选、fixture、Expected Evidence 场景和文件摘要。

生成：

```bash
python3 scripts/generate-benchmark-corpus.py --write
```

只读校验：

```bash
python3 scripts/generate-benchmark-corpus.py --check
```

除本 README 外，本目录文件均由生成脚本维护，不接受手工修改。`.ir.jcs` 没有末尾换行，这是 Axiom IR 规范机器字节的要求；相邻 `.ir.json` 是带末尾换行的人类审阅投影。
