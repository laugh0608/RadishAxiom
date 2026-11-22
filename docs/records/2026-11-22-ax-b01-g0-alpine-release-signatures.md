# 2026-11-22 AX-B01 宿主候选 Alpine 发布验签

两份 Alpine `3.24.4` aarch64 发布对象的 OpenPGP 分离签名均通过。输入为前批留存的原包、分离签名和 `ncopa.asc`。签署主钥指纹为 `0482D84022F52DF1C4E7CD43293ACD0907D9495A`，与 Alpine 官方发布页一致，两份签名均由此主钥直接签署。留存公钥原文 SHA-256 为 `75a9a7e0cc35bfa946ce40c26133b3ed29a204fbd98a3b33331b659d927b3027`。 [官方发布页](https://alpinelinux.org/downloads/) · [启动输入复核](2026-11-22-ax-b01-g0-linux-host-input-review.md)

| 留存原包 | SHA-256 与时间 |
| --- | --- |
| `alpine-virt-3.24.4-aarch64.iso`，93,464,576 bytes | 原包 `cf88d8ba67389d20d9ed307366b52e487c15d7d3ee3233b62b95f709daa1d430`，分离签名 `85651b6c09c16780bb12ff69ac835feddf4a4b5c2e35200ffabf081b3ef7860e`，签署时间 `2026-11-05T11:43:19Z` |
| `alpine-minirootfs-3.24.4-aarch64.tar.gz`，4,029,843 bytes | 原包 `4b14c18f7e90a063b61462ea1462a5732c154bf6adad594974fe6487cd98a8de`，分离签名 `f906719b75ebbd63c7f387c8ba18190b81d7b56cdab4caa9d09aa6654e73c33c`，签署时间 `2026-11-05T11:43:03Z` |

使用已安装的 Go `1.26.7`（`darwin/arm64`）和本机缓存的 `golang.org/x/crypto v0.50.0`，在独立忽略目录编译一次性验签器。模块和 `go.mod` 校验和与 Go 官方 checksum database 两条声明一致；编译从本地 `file://` 模块代理读取，固定 `go.sum`，不触碰项目依赖或系统 keyring。该库采用 BSD-3-Clause，源码和本地二进制仅留在本批目录。首次编译检出 Go driver 与 compiler 版本混用并中止；显式绑定 `GOROOT` 至同一 `1.26.7` 安装后编译和验签通过。 [Go 模块校验和](https://sum.golang.org/lookup/golang.org/x/crypto@v0.50.0) · [上游许可证](https://github.com/golang/crypto/blob/v0.50.0/LICENSE)

对每份输入检查唯一 OpenPGP v4 二进制签名、签署时间、主钥自签名、签名用途和留存公钥材料中的有效期及撤销状态。对完整原包流同时复算 SHA-256 和校验 RSA 4096 / SHA-512 签名。每份原包各做两个负例，改动一个字节和换用另一份发布签名，四次均返回签名不匹配。复跑得到相同的签署者、输入摘要、两项正例和四项拒绝结果。撤销判断范围限留存的发行公钥材料。

本机 `.tmp/ax-b01-g0-openpgp-20261122/` 保留验签源码、固定模块材料、编译失败记录、验签程序及 JSON 回执。源码 SHA-256 为 `be166b938c620de567ce8ca9b2a7aeee2cffbd861b60ab10005779e047a76099`，验签程序为 `4f5eda221a81c220a12b9c18acec2a7078178aea7a82e87d871f015e03980746`，`verification.json` 为 `96c0399af83587cea64993baa1fc1e9873db5aa7599d38cb782aa71cc1118045`。

## 评审接续

本次证据覆盖这两份发布对象。来宾 OCI 的 APK 索引和包来源、许可闭包、派生 initramfs、宿主执行身份和实际配置仍需各自评审。G0 维持 `evidence-insufficient-stop-before-wiring`，`build_ready`、`execution_ready` 和 `runtime_qualification` 均为 `false`。

首次无盘检查的来宾报告应按具名非系统控制台端口定位。Linux 参考实现会动态分配 `vport` 设备号，固定 init 的设备选择须核对端口名和字符设备身份。裸 initramfs 的端口定位和写入须在同一个受控期限内结束。还须在固定 initramfs 前核定目标 virtio 传输及所需模块。已核内核配置的 `VIRTIO_PCI` 和 `VIRTIO_CONSOLE` 为内建，`VIRTIO_MMIO` 为匹配版本的模块。实际枚举、挂载属性与输出仍需在授权后的真实检查中读回。 [Apple 端口配置](https://developer.apple.com/documentation/virtualization/vzvirtioconsoleportconfiguration) · [Linux 端口设备参考实现](https://github.com/torvalds/linux/blob/v6.18/drivers/char/virtio_console.c#L1286-L1303)

下一批固定 Mac 首启程序、来宾 initramfs、entitlement、执行身份及 URL 路径保护，沿已登记的 90 s 无盘检查候选评审精确启动参数。本批未启动 VM、容器或守护进程，未挂载发布对象、安装依赖或执行来宾及 solver 制品。 [首启检查范围](2026-11-22-ax-b01-g0-linux-host-input-review.md#首次只读检查的候选范围)
