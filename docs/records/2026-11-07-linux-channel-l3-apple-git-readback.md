# 2026-11-07：L3 Apple Git 执行链核对

本批以干净的 `dev` / `9d2bd8b078b53c3dd4dad5ee92013eebe90a6905` 开始，按 90 分钟上限核对宿主 Git。范围是 L3 源码快照使用的 Git 入口、实际程序、Apple 安装与签名证据、随包许可及身份漂移的阻断条件。 [前次输入审阅](2026-11-07-linux-channel-l3-input-acceptance-review.md)

## 执行链与实际身份

包装器以绝对路径调用 `/usr/bin/git`。复用 [snapshot 的环境和配置参数](../../scripts/build-linux-channel.py)执行只读探针，子进程从空的继承环境开始，关闭系统和用户 Git 配置、可选锁、交互提示及 lazy fetch。固定 PATH 为 `/usr/bin:/bin`，环境中无 `DEVELOPER_DIR`。在 macOS 27.0.1（26A434）上，`xcode-select -p` 指向 `/Applications/Xcode.app/Contents/Developer`，`xcrun --no-cache --find git` 指向同一目录下的 `usr/bin/git`。 [Apple 的选择规则](https://developer.apple.com/documentation/xcode/configuring-command-line-tools-settings)

用 `/usr/bin/git cat-file --batch` 启动一个短时进程并等待输入。通过 `proc_pidpath` 在同一 PID 依次看到 `/usr/bin/git` 和 `/Applications/Xcode.app/Contents/Developer/usr/bin/git`，随后向该进程发送一个固定 blob 查询并验证响应。入口和实际程序都报告 `git version 2.54.0 (Apple Git-157)`，实际构建为 arm64，`version --build-options` 未给出构建源码提交。

在同样的包装器参数下，`rev-parse HEAD` 匹配基线提交，`status --porcelain=v1 --untracked-files=normal` 为空，`ls-tree -rlz` 读回 2,947 个文件、合计 97,889,572 bytes。样本 `scripts/build-linux-channel.py` 的 `cat-file blob` 输出为 36,513 bytes，重算 Git blob ID 为 `cfa740ffe6e329920d28b8ee5977b73f59582c42`，并与批量调用的内容相等。该检查读取源码树清单与一个实际 blob。

| 对象 | bytes | SHA-256 |
| --- | ---: | --- |
| `/usr/bin/git` | 200,560 | `34129c71a01a74f7f3b2443521519b2e5447553fa187f5fcafaaf8c42cc192e2` |
| `/usr/bin/xcrun` | 199,024 | `bbe7671518a3905f9d3fce54312fbc77c2876b0d62aca74a0688fa869d31a8a9` |
| `/usr/bin/xcode-select` | 184,448 | `49cf1e59551a8a401d86ac444aa6b2a9ab7ec6d3882c98c004dab02a0e484e53` |
| `/Applications/Xcode.app/Contents/Developer/usr/bin/git` | 3,838,240 | `775851091335fd0f0e3eba68e92667b95115208e57ad5ca312936d10edb9ffd3` |
| Xcode `Contents/_CodeSignature/CodeResources` | 32,759,061 | `cc6ee4a07c45ceb1332d52ac3b5327e71b2fe4a7eb3738bfebb0051fafc13cfe` |

## 安装归属、签名和许可

`Info.plist` 与 `version.plist` 给出 Xcode 27.2（27B52）。`pkgutil --file-info` 将实际 Git 文件归到 `com.apple.pkg.Xcode` 版本 `27.2.0.0.1792721698`，安装收据的版本一致。四个命令文件及整个 Xcode 应用包均通过本机 `codesign --verify --strict --requirements '=anchor apple'`。从应用资源封印逐项读回 `Developer/usr/bin/git`、`Resources/Acknowledgments.pdf` 和 `Resources/en.lproj/License.rtf` 的 `hash2`，三个文件均与其封印摘要相同。Git 的签名标识为 `com.apple.git`，CDHash 为 `c6bc766780e7df21ce04dab18fb8c9189ea48169`。

随包 `Acknowledgments.pdf` 对 `git` 有独立条目，声明适用 GNU GPL Version 2，并提供向 Apple 索取源码的途径。Xcode 协议及独立 Git 许可分别留证。上游 Git `v2.54.0` 的 `COPYING` 已留存作为上游许可依据。Apple 公开 Git 仓库的精确 `Git-157` tag 查询为 HTTP 404，开发工具 `developer-tools-27` 前缀查询无结果。已公开的 `Git-155` 只作为相邻记录留存。当前可核实的边界是经 Apple 签名且绑定到本机 Xcode 包的 Git 二进制与随包许可，`Git-157` 的精确 Apple 源码和源码到二进制的构建对应仍缺。 [Git 上游许可](https://github.com/git/git/blob/v2.54.0/COPYING) · [Apple 开源分发入口](https://opensource.apple.com/releases/) · [Apple Git 源码索引](https://github.com/apple-oss-distributions/Git/tags)

## 漂移时如何阻断

保持源码快照的精简 Git 环境。构建前从该环境读取活动开发者目录与无缓存解析结果，对照外部登记的路径、Xcode 版本、Apple 签名及入口和实际文件摘要。源码快照完成后重核相同身份，失败、路径切换或文件变化均应让该次构建失败。以现有 Command Line Tools 目录作为仅对子进程生效的 `DEVELOPER_DIR`，无缓存查找会解析到 `/Library/Developer/CommandLineTools/usr/bin/git`，与固定 Xcode 候选不同。恢复精简环境后原选择仍匹配。这验证了只固定入口路径仍会受选择状态影响。

现行检查器固定 `/usr/bin/git` 的文件引用，构建执行该入口。上述实时选择核对仍待接入。前后读回覆盖可观察漂移，一次构建仍须明确接受宿主在快照期间不并行切换选择器或替换工具的约束。后续还需收口 target 发布清单的信任范围、Cargo 解析数据的来源与许可及固定宿主信任。L3 总体为 **`not-accepted`**，target 保持未安装。 [现行工具校验](../../scripts/check-linux-channel-inputs.py) · [L3 接续](../query/solver-linux-channel-l3.md)

## 复核材料

诊断方法、只读输出、签名检查和许可原字节引用在本机忽略目录 `.tmp/l3-apple-git-review-20261107.25wkT7F9/`。从对应干净提交运行 `python3.14 -I -S -B <任务目录>/observe-apple-git.py <任务目录>` 可重跑执行链探针。PID 会随执行变化。Xcode 致谢文本使用本机 PDFKit 提取，许可协议以本机 `textutil` 读取。两份文件的原始摘要来自独立的签名封印读回。整个 Xcode 包的签名检查以 45 秒为上限，正常退出。

| 本机文件 | SHA-256 |
| --- | --- |
| `observe-apple-git.py` | `093ea5420f9e5c317d50b78f1be0ddc22a9c51578046540bb84646f09ebcf580` |
| `observation.json` | `28a8299daa743d22094981f5e3d33b289c7843e89c4fdd67d03cb1aaed7fb62f` |
| `xcode-bundle-verify.json` | `114a3e9106841aa818b550723c1d4faf420411180fcd4723835272579a03568a` |
| `xcode-resource-readback.json` | `fa0f1f4d429763892d51b2e446fdb9cbcd86f51bcdd89f129f56db21f8de30db` |
| `apple-git-pkg-info.txt` | `641c9cddc51a0edafbe7502efd8eaf4fe757e59cf4748abf021881ffd41c41b6` |
| `xcode-pkg-info.plist` | `d498a40e0860b1f8c75d4924dfc97f9bf08e14542371e7ff1607f82a3c6b3f2d` |
| `xcode-acknowledgments.txt` | `8072c3746f2a2846650a5b920aeab16c895f9f2b96914730e1149f5726930f89` |
| `xcode-license.txt` | `ab77ea3cf8f799f28966ef33ada0ab6e5c98cc678eabae590718542aa933ed87` |
| `upstream-git-v2.54.0-COPYING.txt` | `5b2198d1645f767585e8a88ac0499b04472164c0d2da22e75ecf97ef443ab32e` |
| `git-157-tag.stderr` | `d2c8985c89b29a842ac4946d13bdbc297709f44f20bb968faf9682664b211db6` |
| `developer-tools-27-tags.json` | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| `apple-git-build-options.txt` | `3d260785341695cc0d0650ac8202e3abed6a8cc275d079a7b2534e149e10b5a0` |
