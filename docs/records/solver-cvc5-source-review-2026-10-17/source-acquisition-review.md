# C0 五项源码获取与安全审树记录

日期：2026-10-17。用途：重核本次源码原字节、安全静态展开、逐文件许可定位及已运行检查；不是签名认证、C1 输入接受、构建或工具运行授权。机器入口为 [source-inputs.json](source-inputs.json)，许可语境见[许可审阅](license-review.md)。

## 实际结果

五归档合计 **13,368,905 bytes**。CaDiCaL、SymFPU、LibPoly、GMP 的独立重算 SHA-256 均匹配冻结输入清单的四个期望值；没有修改期望值、重试、备用源或 SDK 包请求。cvc5 归档 SHA-256 为 `cbaa927c4d8085e38e7a097191bb9dd3a6780cc17fcde65cb156c9583e597760`（9,279,538 bytes），没有上游已留存归档摘要可作比较；其 PAX commit comment 与固定 commit 相同，CaDiCaL / SymFPU / LibPoly 的 comment 也与各自固定 commit 相同；这些都是未签名归档自身的声明。cvc5 全部 **7,066 个 Git blob** 与此前留存的未签名 publisher tree 对应。后一项仅是既有材料一致性，不是发布者签名认证。

| 树 | 条目 | regular files | 文件 payload bytes | 实际解压 tar bytes |
| --- | ---: | ---: | ---: | ---: |
| cvc5 | 7,349 | 7,066 | 67,446,922 | 73,031,680 |
| CaDiCaL | 459 | 446 | 2,867,449 | 3,246,080 |
| SymFPU | 51 | 46 | 402,282 | 450,560 |
| LibPoly | 264 | 235 | 2,279,998 | 2,488,320 |
| GMP | 2,343 | 2,156 | 16,998,222 | 18,759,680 |

CaDiCaL 有一条内部 symlink，其余树均只有目录及 regular files；完整 target 与解析结果保存在 tree。第三方源码与原包只在 `.tmp/cvc5-c0-acquisition-2026-10-17`，未进入 Git。该目录及内容保留，不作删除或上传。

## 获取入口与一次守卫修正

[获取 / 审树 helper](../../../scripts/cvc5-c0-source-inputs.py)只读取下载时的精确 `input-selection.json`，将其原字节及当时 fetch helper 复制到保留区并记录摘要；这份冻结选择是旧 `0.2`，不绑定后续可更新的正式 C0 总清单。

首次 `fetch` 完成 cvc5 后，在 CaDiCaL 初始 GitHub 请求返回的 `codeload.github.com/arminbiere/cadical/tar.gz/refs/heads/rel-2.1.3-elevate` 地址处被本地守卫拒绝，未读取 CaDiCaL 正文。这是守卫只接受短 ref、未接受 GitHub 同一 ref 的规范地址所致。旧 helper 及旧失败记录保留；修正严格限于这个 repo/ref 的精确地址，不允许其他 ref、外域或查询参数。

`continue-cadical-redirect` 只接受这一精确零正文失败状态，先独占保存 `fetch-before-redirect-continuation.json` 及 `continuation-helper.py`，再访问已捕获的 Location，不重发 cvc5 或 CaDiCaL 初始请求；其余三项首次访问原冻结 URL。新 helper 与旧 helper 分开保留。原失败 JSON 只捕获了目标 URL 和异常，未单独捕获 HTTP status；接续 chain 中的 302 是由工具 traceback 的 `http_error_302` 恢复的说明字段，不冒充旧 manifest 已捕获的 response status/header。未保存跳转正文或认证其内容。

每项 180 秒总 deadline、零 retry / 备用源，cvc5 64 MiB、其余各 32 MiB、总 192 MiB；所有实际重定向均精确受限于所选 GitHub repo/ref 的归档或同一 GMP 文件的 raw 路径。HTTP chain、实际 bytes、SHA-256、时间、原始 Content-* / ETag 相关头位于获取 manifest。没有签名可信根或签名验证结论。

## 解包安全与重核

在写任何 source tree 前先完整读完并审查物理 tar header、PAX / GNU 长名扩展、payload、padding 与尾部。每树固定上限为 100,000 条、单文件 128 MiB、完整解压 tar 1 GiB、扩展 16 KiB、路径 4 KiB、链接 40 hops；未增限。拒绝绝对 / `..` / 非规范路径、重复路径、casefold 与 Unicode 归一化碰撞、设备 / FIFO / 不支持类型、链接逃逸 / 循环 / dangling / 非目录祖先、截断 / 校验和或尾部错误。

只有完整审查成功后才在新目录逐文件独占创建，不覆盖已有文件或沿已有 link 写入。原 owner / setuid / 可执行位不应用，审阅树目录为 0700、regular files 为 0600，链接最后创建；原权限与目标保留在 inventory。写入时再次完整解析并比较前次 inventory。已展开 cvc5 在五项汇总阶段只核对相同记录，没有重写原树；后续 verify 对现有每条成员与实际内容全量重核。

[独立检查器](../../../scripts/check-cvc5-c0-source-independent.py)不导入获取器，使用 stdlib `tarfile` 的另一解析路径及独立有界解压读取，重新核对归档、tar 成员元数据 / 内容、展开成员集合 / mode / links 与 cvc5 Git blob。独立表示字节与树的一致性检查，不表示独立发布者认证或形式证明。

实际执行通过：

```text
python3 scripts/test-cvc5-c0-source-inputs.py
python3 scripts/cvc5-c0-source-inputs.py inspect-cvc5
python3 scripts/cvc5-c0-source-inputs.py inspect
python3 scripts/cvc5-c0-source-inputs.py refresh-summary
python3 scripts/cvc5-c0-source-inputs.py verify
python3 scripts/check-cvc5-c0-source-independent.py
```

共 **8 个 unittest 方法**通过。显式刷新只为新增全部固定 commit 的 PAX 一致性及检查器自身绑定；原 summary 和 inspection helper 已留存，现 summary 同时绑定当前及保留区冻结 inspection helper。当前 helper 改变后 `verify` 必须失败，须显式刷新而不能冒充旧验证。下载时原 helper 始终为单独冻结版本，当前源码不会替代它。逐字节复制的获取 / 失败 manifest 与实际入口摘要见 [执行历史](source-execution-history.json)。

合成测试覆盖正常 regular / contained links、拒绝覆盖与权限、不安全路径及大小写 / Unicode 冲突、devices / FIFO、链接逃逸 / 循环 / dangling、预算 / 截断 / checksum、GNU / PAX 长名、精确网络目标及独立解析器拒绝摘要篡改。没有执行任何上游 script、configure、CMake、autotools、生成器、探测程序或 solver；未安装、构建、改系统或 push。
