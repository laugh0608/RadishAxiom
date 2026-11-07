# 本地 cvc5 私有离线阶段规则 v0.2

日期：2026-10-27。用途：为[有限实施计划](solver-local-cvc5-phase-plan.md)定义显式私有版本、命令截获与留存材料核对，供实施者和复核者使用。范围为 [ADR 0031](../adr/0031-local-cvc5-build-provenance-boundary.md)下的固定本地候选；不定义公共 Evidence、工具接受或运行协议。实际验证见[本批记录](../records/2026-10-27-cvc5-offline-phases.md)。

## 入口与版本

既有 `scripts/prepare-cvc5-offline-build.py` 的 `prepare` / `check` / `bind-inputs` 与 `scripts/prepare-cvc5-execution-review.py` 均默认 v0.1；必须显式传 `--recipe-version 0.2` 才选择新规则。不得根据输入 JSON 自动迁移或降级。`prepare` 只写计划；其余一致性检查成功后仍返回 2，`execution_ready=false`、`build_ready=false`、`acceptance=not-accepted`。无运行、安装或清理模式。

旧冻结配方字节不变。入口源码变化会使旧配方所绑定的源码摘要漂移，旧入口继续拒绝，不伪造历史摘要或宣称重新接受。新生成的 v0.1 仍使用原命令、配置、资源、布局和失败规则；其当前源码引用摘要自然改变。v0.2 复用原输入预检、布局、32 步依赖配方和 review-gate，仅增加版本化阶段、最终链接 patch 与对应检查。

新代码位于 `scripts/cvc5-build-support/`：`phase_recipe.py` 派生新计划与静态 patch 关系，`phase_rules.py` 检查声明，`capture_link.py` 截获命令，`link_formats.py` / `link_materials.py` 读取有界材料。规则、代码、patch 与 Accepted ADR 的实际摘要进入新配方引用。配方检查从原输入重新生成并作完整类型敏感比较；未知字段、混版及重算摘要后的内容篡改均拒绝。

新版本 JSON 限 16 MiB / 64 层，拒绝重复键和非有限数字。后续 namespace 内的 `bind-inputs` 只解决真实依赖 manifest 的字节绑定与命令数据，不替代此前的完整配方重核；它另检查闭合信封、新规则引用与阶段计划，保留所有阻断项。

## 固定阶段与声明

四个阶段固定为 `dependencies`、`main-compile`、`final-link`、`postprocess`；顺序、输入 / 输出角色与边界由 `phase_rules.plan()` 定义。依赖与主编译期间仍允许原阶段内生成；最终链接必须消费已经固定的输入。阶段之间不重置整批截止时间、存储与日志预算，也不将未登记 tmp / HOME / 可写根带入下一阶段。

`--phase-declarations` 指定私有 `radishaxiom-private-cvc5-phase-declarations` v0.2 文档。根字段严格为 `format`、`version`、`scope`、`recipe_sha256`、`plan_sha256`、`batch_start_ns`、`external_inputs`、`stages`、`runtime_qualification`；scope 必须为 `offline-unverified-declarations`，资格必须为 false。允许检查非空阶段前缀，不允许跳过、中途开始、循环或重复阶段。

外部角色 `sdk`、`sources` 绑定配方对应描述的规范 JSON 摘要，`recipe` 绑定原配方文件摘要；这只是描述绑定，不替代真实组装根验收。每阶段的 `inputs` / `outputs` 是按角色规定顺序排列的 `id` / `sha256` 对，消费者必须引用已出现的相同输出，不允许声明未知生产者或重新定义角色。

每阶段还保留开始 / 结束时间、实际 `build_exit`、`first_error`、截获列表、流关闭、后代 / 写入者 / 可写别名计数、冻结声明、控制面材料摘要与资源使用。所有字段和整数 / 布尔类型严格检查。声明有首错、未关闭、未冻结、残留写入者、资源超额或预算回退就拒绝。即使这些字段自报一致，结果也只是 `offline-declaration-consistency-only`；不认证控制面摘要、不声称实际阻止了宿主写入。

`usage.total_bytes` 是包含留存根、临时区和证据的整批存储高水位，memory / swap 也为整批峰值；log / events / inventory 字节及失败计数均累计报告，不能改成每阶段重置的数值。捕获的实际 cwd 与 shell 的 PWD / OLDPWD 分开保留；后两者可仍指向 `/work` 中先前目录，不以改写环境伪造一致。

## 截获与非零退出

新 `patches/cvc5/1.3.4/capture-final-link.patch` 仅在 `cvc5-bin` 设置 `CXX_LINKER_LAUNCHER`。它接续原 `explicit-inputs.patch`，不修改后者。原始 / 组合前后树、该文件前后字节与 patch 均独立绑定；只以现有 exact patch 算法在内存核对，不运行 CMake。

launcher 使用固定 `/usr/bin/python3.11` 启动 `capture_link.py`，输出 `/work/evidence/cvc5-link-capture.json`，参数分隔符之后保留完整 driver argv。工具不含子进程、网络、删除或 exec 路径；成功写出观察后返回 **78**，表示已截获且没有链接。已存在输出、未知环境键、格式 / 大小错误或写失败返回失败，保留已有文件或部分输出，不覆盖、不自动重试。

观察包含 format / version、`target=cvc5-bin`、`scope=untrusted-tool-observation`、`driver_executed=false`、`exit_code=78`、argv、cwd 与闭合环境。单份 JSON 上限 1 MiB，argv 上限 65,536 项；环境只允许原配方键与 Make / shell 的七个记账键，未允许的环境变量在序列化前拒绝。错误诊断不打印原环境或 argv 值。

主编译阶段只有恰好一次匹配截获、实际 Make / CMake **非零**退出、无其他首错、无假 CLI、流和后代完整收束，才满足离线的“链接待审”声明。不得伪造零退出或把标记当成外围认证。真实生成规则 / 捕获身份、冻结防护及原命令重放均留待实际资格；本实现不执行下一阶段。

## 链接材料的有限核对

`--link-materials` 必须与 `--phase-declarations`、`--material-root` 及显式 v0.2 一起使用。阶段前缀必须恰为依赖、主编译两阶段。材料根是本机已有的独占留存目录，只读；文件引用是相对路径、字节数和 SHA256，拒绝真实符号链接、非普通文件、路径逃逸和大小不符。单文件不超过 1 GiB，总读入不超过 4 GiB，库存最多 100,000 路径；文本材料另限 1 MiB。

私有 `radishaxiom-private-cvc5-prelink-materials` v0.2 文档严格绑定配方及阶段声明摘要，scope 为 `offline-retained-byte-consistency`，`actual_link` 必须为 null。它给出捕获、CMake `link.txt` 原字节、输入文件、虚拟别名、默认搜索根、预期展开参数、有序输入及待复核隐式输入声明。预期来自独立审阅材料；不能将生产解析器的输出作为唯一预期。

- 捕获与生成命令逐 argv 比较。`link.txt` 只接受固定 launcher 前缀的一行 shell 引用子集，不解释变量、通配符、重定向、管道或命令替换。cwd 与环境在捕获中保留；环境的配方固定值必须匹配，不能据此声称已认证真实 cwd / 环境。
- 每个输入给出 `path`、留存文件引用、`role`、`producer`、生产阶段摘要、`frozen_before_link` 及 archive 成员声明。角色限 object / archive / response / script / configuration，生产者限 SDK、依赖或主编译；不得位于独立可写输出根，不能声称来自未来链接阶段。虚拟符号链接复用既有布局解析，不解析成本机宿主 SDK 路径。
- GNU `@file` 按空白、单双引号与反斜杠展开，保留重复和空参数；递归相对捕获 cwd，最多 16 层、展开总文本 8 MiB / 参数 65,536 项。缺失、环、未闭合引号、尾部转义和预算溢出均拒绝，不采用 GNU 对缺失响应文件的字面量 fallback。
- GNU 普通 archive 按实际顺序保存所有对象与特殊表的字节摘要，使用成员名、索引、同名出现序号区分重复。只读 ELF64 little-endian AArch64 ET_REL 的头 / section 边界并拒绝 LTO 节；这不是对象语义验证。thin / BSD archive、未知名称编码、成员截断与声明遗漏均拒绝。
- linker script 只识别 `INPUT`、`GROUP`、组内 `AS_NEEDED` 与注释，输入限绝对路径或 `-l`；相对脚本输入和其他命令停止审阅。搜索只在声明的只读根内进行，保留 `-l` / archive 的必要重复。参数只支持代码明确列出的固定候选子集，保持静态、原 `-o`、map、`--cref` 和双 trace；未知 / 动态 / LTO 参数拒绝，不猜测替换。已声明会使用的隐式脚本也检查其输入，但不将展开结果当成完整隐式闭包。

结果只报告 `offline-prelink-byte-consistency-only`。允许集合与使用观察分开；未出现于观察的文件不推断为未使用。隐式输入声明必须存在且归属 SDK，但**完整性未建立**；成员库存不等于实际成员抽取。没有实际 map / trace、链接 ELF 或 strip 结果，也未证明声明的搜索库存完整。实际生成的命令若超出本子集，应保留失败和具体语法，重新审阅；不得自动加支持或放宽资格。

## 验证与交接边界

验证覆盖源树静态 patch、无 driver 调用的合成子进程、严格版本 / 阶段 / 身份 / 时间 / 预算、响应 / archive / script 负例和旧行为回归；留存 SDK 的 `libgcc.a`、`libc.a`、`libm.a` 仅在内存读取原包成员并检查格式，不落成 SDK 文件树。独立复核不导入生产判定函数，核对实际导出字节及手写期望；测试与独立复核分别报告。

本机 Darwin Python 会自动增加 `__CF_USER_TEXT_ENCODING`；合成进程测试在加载工具后只移除这一宿主键，再调用实际入口。生产 Linux 环境清单不为该测试放宽，测试不提供 Linux 运行资格。响应文件及链接选项语法参考固定版本 [GCC 12.2](https://gcc.gnu.org/onlinedocs/gcc-12.2.0/gcc/Overall-Options.html)与 [GNU ld 2.40](https://sourceware.org/binutils/docs-2.40/ld/Options.html)；本实现有意只接受上述子集。

本批最多形成 A1 / A5 / A6 / A7 / A10 的有限离线覆盖。C1 许可、完整隐式输入与实际产物、输入封闭、冻结对象、受保护记录、资源及终止资格保持未完成；A2 / A3 / A4 / A8 / A9 不升级。没有 SDK 组装、配置、编译、链接、Docker / VM、探针、solver、依赖安装、系统变更或远程写入。
