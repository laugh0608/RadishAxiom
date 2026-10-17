# 五项源码的许可与组成静态审阅

日期：2026-10-17。用途：供 C0 输入与后续 C1 审阅者定位实际取得源码中的许可、版权、生成材料和测试材料。本文不是法律意见、许可接受、静态链接接受或分发接受，不把源码包内材料存在等同于已进入 CLI。

## 逐文件库存及边界

[源码输入记录](source-inputs.json)绑定五份原归档、逐项 tree 与 `*-license-inventory.json`。tree 保存每一条原路径、类型、原 mode、owner、时间、长度、regular-file SHA-256 和 Git blob SHA-1；许可库存保存全 regular-file 字节扫描命中的路径、实际 SHA-256、匹配行数及最多两条各 220 字符的短声明。许可正文及第三方源码仅保留在原归档和任务保留树，不复制进仓库。

扫描覆盖 copyright、SPDX、常见授权正文和例外词，以及许可文件名；这是定位清单，不是能识别任意法律措辞的解析器。材料均默认 `requires-contextual-component-review`，不能把未命中文件推断为无版权或无条件可分发。逐文件库存连同下列人工分层构成本次静态审阅；最终链接对象、生成结果与 SDK 对应源包仍未取得或接受。

## 主许可、嵌入项与可能的 CLI 组成

表内路径相对各自归档顶层目录。所有路径的完整实际摘要见对应 tree / license inventory，不以网上最新许可替代固定源码。

| 来源 / 组成 | 实际许可材料与声明 | 使用范围与待核对项 |
| --- | --- | --- |
| cvc5 主体 | `COPYING`（SHA-256 `341cd23c1133beda63509cad8d82b96a47dc8e321bdd49ce8190e371110ccff7`）、`AUTHORS`；modified BSD 三条件 | 主体许可与内嵌、外部库分别审阅；`COPYING` 说明 non-GPL 配置不排除 LGPL，也不证明任何实际 CLI 组成 |
| 内嵌 MiniSat | `licenses/minisat-LICENSE` 与 `src/prop/minisat/LICENSE` 字节相同（`c75f5063560674728fcfa7b9b291d26a3a8b9436a0d9940eadc81aab7779d62b`），MIT；`src/prop/minisat/**` 源文件保留自身作者声明 | 这是 cvc5 归档中的嵌入源码，不能因为外部 SAT 选 CaDiCaL 就在许可清单中删去。具体编入对象仍以未来依赖文件 / map 为准 |
| CaDiCaL | `LICENSE`（`faf8e28f930684e3fbaf50a03c0c0b6b2373977cd74988efec19144241f0667c`），MIT，列各作者与机构 | `src/` 库与独立程序 / test / scripts 区分；未运行其 configure 或 makefile 生成步骤。声明许可不是静态库已产生 |
| SymFPU | `LICENSE`（`663f684cfc4fbf827926924cb32f5cd84ebcb275d60c55506f9e62524fd14f98`）明确 GPLv3 或 BSD 3-Clause 二选一；`LICENSE-BSD`（`00f50e5054992dc8d34e9995d33ce092c2633c8a000a67df00844b560ba8aeb0`）、`LICENSE-GPL3`、`AUTHORS` 同包保留 | 既定 non-GPL 候选拟用 BSD 选项；未把同包 GPL 选择文本误报为必然 GPL 链接。头文件对实际 CLI 的贡献须后续 header 依赖证明 |
| LibPoly | `LICENCE`（`da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768`），LGPLv3；`include/poly.h` 及源码声明 v3-or-later | C 与 C++ 头 / 实现、Python/test 材料分开；固定静态 Poly / Polyxx 路线仍需实际生成与链接留证。下面的 Debian copyright 歧义阻止声称“完整许可已接受” |
| GMP / GMPXX | `README`、`COPYING`、`COPYINGv2`、`COPYING.LESSERv3`；库文件及示例 `mpn/arm64/aors_n.asm`、`mini-gmp/mini-gmp.c` 声明 LGPLv3-or-later 或 GPLv2-or-later，可并行授权 | 候选拟沿 LGPL 路线；不能整包一概标成一种 LGPL。实际 AArch64 选用汇编、生成头、C++ wrapper 和被抽取 archive 成员尚未确定；mini-gmp 的存在不证明 CLI 使用它 |

## 工具、生成输入、文档与测试

- cvc5 的 `licenses/GCC-exception-3.1.txt`、`licenses/gpl-3.0.txt` 是 GCC runtime 条件说明；不能代替未来精确 Debian GCC / libstdc++ / libgcc 包内 copyright、例外条件或实际对象归属。`licenses/apache-2.0-with-llvm-exceptions.txt` 为另一工具链路线的材料，存在不表示本候选使用 libc++。
- cvc5 的 `cmake/`、`src/options/`、`src/theory/`、`src/expr/`、`src/rewriter/` 等生成脚本、模板、规则数据与主源码分开定位；生成输入的版权库存不能替代未来生成输出 / 对象对应。`test/`、`examples/`、`docs/` 和 bindings 相关材料也在全树与逐文件扫描中保留，不能把未构建目标自动视为已链接或从源包输入清单抹去。
- GMP 的 `configure`、`Makefile.in`、`config.guess`、`gen-fac.c` 保留自身实际声明；未执行。`ltmain.sh` 含 GPL 授权及 GNU Libtool 相关特殊例外，`missing` 含 GPL 及特定分发例外；`install-sh` 有独立宽松授权。这些构建材料不可统一标作 GMP 库许可或自动套用 GCC Runtime Library Exception。
- GMP 的 `doc/gmp.texi` 明确 GNU Free Documentation License 1.3-or-later，带封面文字要求；文档许可不能替代运行库许可。`tests/`、`demos/`、`tune/`、`mini-gmp/` 及生成程序是不同用途材料，是否构建 / 分发仍待对应目标与输出清单核对。
- LibPoly 的 `python/`、`test/`、`debian/`，CaDiCaL 的测试 / 程序 / 配方，以及 SymFPU 的完整头文件树均保留原字节；本轮不执行、不安装、不挑出一个程序就声称输入许可闭合。

## 必须保留的许可歧义

固定 LibPoly `debian/copyright`（SHA-256 `cd3eb8b96019760e240235847501addff027f870ffe57687c4128ec78a155664`）的 `Files: *` 节写 `License: GPL-3+`，对应许可节标题同样是 GPL-3+，但其正文明确使用 **Lesser**，而根 `LICENCE` 与 `include/poly.h` 也声明 LGPLv3。末尾又引用 GPL-3 文本路径。此处是实际归档内声明冲突；不能修改上游原文件、静默把标签当笔误或从库存删除。当前仅能记录库源码与根文本支持 LGPL 路线，包元数据歧义尚未完成许可接受；后续若需更强结论须明确裁定范围或取得针对该版本的权威澄清。

SDK 的 libc / CRT、Editline / tinfo / bsd / md、GCC / Binutils / 生成工具及其对应源码 / patch / copyright 均不在本轮已取得的五归档中。五份源码的静态库存不填补这些缺口；没有链接 map、实际新 ELF、分发组合或许可接受结论。
