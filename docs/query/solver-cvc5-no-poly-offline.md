# AX-B01 cvc5 1.3.4 的 Poly 关闭候选

日期：2026-11-22。私有候选标识为 `ax-b01-cvc5-1.3.4-linux-aarch64-no-poly`。固定 cvc5 提交 `f3b21c4483d3b88dc63cb7cd3e5eb092eee5e341`、Linux AArch64 little-endian、glibc/GCC、Production、静态、non-GPL、Editline 及原 AX-B01 请求。C1 固定输入已限定接受用于本地诊断。制品仍待 E0，`build_ready=false`、`execution_ready=false`。 [选型及原包核对](../records/2026-11-22-ax-b01-checker-and-solver-path-review.md) · [C1 接受记录](../records/2026-11-22-cvc5-no-poly-c1-acceptance.md)

## 输入与补丁

[候选输入清单](../records/solver-cvc5-no-poly-2026-11-22/candidate-inputs.json)绑定四份源码归档与树、原 500 份 SDK 相关文件的留存清单和包内容记录。四份源码及其留存树可在 LibPoly 原包或解包树不可用时完成重核。SDK 的历史验签范围只随材料保留。GMP/GMPXX、CaDiCaL、SymFPU 与 Editline 保持原选择，实际编译输出的摘要等待生成和复核。

补丁在内存中依次严格应用三段，并记录每段输入、输出树摘要。第一段从固定的 [原显式输入补丁](../../patches/cvc5/1.3.4/explicit-inputs.patch) 投影七个共享文件，排除整个 `cmake/FindPoly.cmake` 段。第二段应用 [候选差分](../../patches/cvc5/1.3.4/no-poly-inputs.patch)，在 `project()` 前检查独立 manifest、显式归档和头文件根并禁止查找 Poly；配置守卫要求 `USE_POLY=OFF`。第三段沿用 [最终链接捕获](../../patches/cvc5/1.3.4/capture-final-link.patch)。合计涉及八个文件。上游原树里的 Poly 相关源码、许可和条件分支按原字节保留。

## 离线配方与清单检查

[独立离线配方](../records/solver-cvc5-no-poly-2026-11-22/offline-build-recipe.json)包含四阶段约束、29 项依赖步骤与 11 项主阶段计划。它排除五项 Poly 步骤、生成头、PIC 安装变换和 Poly 专属探测，并增加两份固定 Editline 头文件的未来复制步骤。新配方保留 CaDiCaL 的两个能力检查。固定 SDK 的 `CheckSymbolExists` 优先使用 C 编译器，原配方会用 C 检查 C++ 头 `cstdio`。新候选显式用 C++11 检查 `getc_unlocked` 与 `closefrom`，后者使用目标源码已包含的 `unistd.h`。实际探测结果留待 C3，原配方继续保留原声明。

从仓库根调用 [私有离线入口](../../scripts/prepare-cvc5-no-poly.py)。`prepare-inputs` 和 `prepare` 只向新的指定路径写 JSON。`check` 接收独立取得的配方 SHA-256，重新计算固定输入、补丁及整份配方，按字段和类型比较。`check-manifest` 接收已留存材料根和独立取得的实际 manifest SHA-256。它只读取 `work/review/build-inputs.json`、同级复核文件与已声明材料，校验五类头文件目录、固定归档角色和路径、已知字节及复核绑定。`bind-inputs` 同时校验配方和材料，只填入经过核对的 manifest 摘要，另存命令数据。检查或绑定通过返回 2 并明确标记阻断状态，拒绝返回 1。

~~~text
python3 -O scripts/prepare-cvc5-no-poly.py check docs/records/solver-cvc5-no-poly-2026-11-22/offline-build-recipe.json --sha256 <独立核定的原始字节摘要>
python3 -O scripts/prepare-cvc5-no-poly.py check-manifest --material-root <已留存材料的绝对根路径> --sha256 <独立核定的实际manifest摘要>
~~~

保留 Editline、tinfo、libbsd 三种必需角色。libmd 的固定 SDK 归档可在复核明确纳入时进入闭包，顺序与必要的重复项随实际复核绑定。`libtermcap.a` 的归档别名解析到 SDK 内的 `libtinfo.a`，清单使用后者的规范路径。实际 pkgconf 输出和成员抽取仍须逐项对账。本批以合成文件检查未来 manifest 正负例，以实际四源码和 500 份留存文件检查准备配方。真实依赖输出、闭包声明及完整的运行期可访问输入集尚待形成。

旧 [v0.1 配方](../records/solver-cvc5-c2-2026-10-23/offline-build-recipe.json)、[v0.2 配方](../records/solver-cvc5-phases-2026-10-27/offline-build-recipe.json)和旧入口继续使用原私有格式、原字节和原门禁，两个候选的配方不能交叉消费。新配置或材料发生变化时须重新裁定候选并审阅差分。

## 停止线

1. 按已登记的 C1 范围复用固定 SDK、来源和许可材料。L3 与 G0 仍需宿主及工具信任、真实输入封闭、冻结与独立终止、磁盘和 inode 硬限。
2. 具备资格并获单独授权后，C3 才能生成依赖、核对 GCC/CRT/ABI 与实际 Editline 链接闭包、绑定 manifest，再留存主配置、编译及链接观察。有效配置、头文件、对象和 map 都须能追溯到固定候选。阶段计划中的 manifest 参数保持待填写，直到真实值有独立复核。
3. 新 ELF 通过 E0 与实际 E4 后再依次恢复 E5 和 E6。沿用原容量和 128 MiB / 6 s，P6 按真实义务结果与独立复核门禁恢复。 [原停止线与执行授权](solver-cvc5-build-candidate-plan.md#批次占用授权与停止线)
