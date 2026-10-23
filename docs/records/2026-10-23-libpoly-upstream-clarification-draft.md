# LibPoly 上游许可澄清草稿

日期：2026-10-23。状态：**本地草稿，未发送**。用途：供项目所有者审阅后，作为上游 issue 或邮件正文使用。此前许可研究已提交为 `2246519`；依据见[历史核对记录](2026-10-23-libpoly-license-history.md)。本文件不是上游答复或许可接受决定，C1 仍为 `not-accepted`，`build_ready=false`。

以下英文标题和正文可独立使用；不包含内部验收信息、本地路径或私人联系方式。不预设声明冲突是笔误，不要求上游更换许可证。请求聚焦固定版本的既有许可及来源事实。

## 建议标题

Clarification of licensing, Polyxx coverage, and open_memstream.c provenance in LibPoly v0.2.1

## 英文正文

Hello LibPoly maintainers,

We are reviewing LibPoly **v0.2.1, commit `3d5e6fbd98639cb0941b029e23ca17c0e3c4a80a`**, for downstream use. Could you help clarify the existing licensing of this exact revision in the following three areas?

### 1. Overall license and conflicting Debian metadata

At this revision, the root [LICENCE](https://github.com/SRI-CSL/libpoly/blob/3d5e6fbd98639cb0941b029e23ca17c0e3c4a80a/LICENCE) contains LGPL v3. Source-file notices also refer to LGPL v3 or any later version. However, [debian/copyright](https://github.com/SRI-CSL/libpoly/blob/3d5e6fbd98639cb0941b029e23ca17c0e3c4a80a/debian/copyright) applies a `GPL-3+` label to `Files: *`, repeats that label in the license paragraph, then describes the GNU Lesser General Public License and points to the GPL-3 text.

The history we found is:

- [2015-07-08: `1e570302`](https://github.com/SRI-CSL/libpoly/commit/1e570302ff1fb53b6ea2d5bc09a286fb19947730) added the root LGPL text.
- [2017-06-13: `9d25ed27`](https://github.com/SRI-CSL/libpoly/commit/9d25ed278c2faf4772f581ed6593448b4550ba2b) introduced `debian/copyright` with this discrepancy already present.
- [2017-07-25: `41dde08f`](https://github.com/SRI-CSL/libpoly/commit/41dde08ff67a5db23d62f8ce5c1cafc5d0715f81) added project/contact/source metadata without changing the license wording. We did not find an explanation of the discrepancy in the associated [issue #12](https://github.com/SRI-CSL/libpoly/issues/12).

**Which license and version choice apply to LibPoly's own code at the fixed revision: LGPL-3.0-or-later, LGPL-3.0-only, or another grant? Which Debian fields, if any, should be corrected?** Please also identify any exceptions or separately licensed components relevant to that answer. We do not want to assume that the conflicting label is merely a typo.

### 2. Coverage of the Polyxx implementation and public headers

[PR #25](https://github.com/SRI-CSL/libpoly/pull/25) introduced Polyxx as LibPoly's C++ wrapper. The implementation/build integration in [`fabc345b`](https://github.com/SRI-CSL/libpoly/commit/fabc345b836bea35883602cecf2aadac103412aa) and the headers in [`79474f7b`](https://github.com/SRI-CSL/libpoly/commit/79474f7b4218938b30382917eaefbfbf3c8188bf) were added on 2020-06-11, after the root LGPL text was present.

**Does the project license confirmed above cover `src/polyxx/`, `include/polyxx/`, and `include/polyxx.h` at the fixed revision, including files without an individual license notice?** If any files or contributions have different terms or require additional attribution, could you identify them and the applicable terms?

We understand that a project-wide license can cover files without repeating a notice in each file; the question is to confirm the intended coverage of this revision in light of the conflicting metadata.

### 3. Origin and permission for the older open_memstream.c

The older [src/utils/open_memstream.c](https://github.com/SRI-CSL/libpoly/blob/3d5e6fbd98639cb0941b029e23ca17c0e3c4a80a/src/utils/open_memstream.c) was introduced by [`53d544c1`](https://github.com/SRI-CSL/libpoly/commit/53d544c110acfbf6e755d3810f021aa16d020c37) on 2017-10-19. We did not find an author/copyright notice, original source reference, or separate license grant in that `.c` file or its introduction commit. The companion `.h` does contain an SRI/LGPL notice.

**Was this `.c` implementation written for LibPoly or adapted from an external source?** If external, could you provide the original author/rightsholder, source URL and revision, applicable license or permission, and any notices that should be retained? If it was original work for LibPoly, could you confirm its authorship and the license under which it was contributed?

This question concerns the older `open_memstream.c`, rather than `u_memstream.c/.h`: the latter explicitly record their Mesa source and MIT terms in [`59ee683e`](https://github.com/SRI-CSL/libpoly/commit/59ee683e544b573101bcdac213cd7a494d67b86a) / [PR #66](https://github.com/SRI-CSL/libpoly/pull/66), with background in [issue #65](https://github.com/SRI-CSL/libpoly/issues/65#issuecomment-1471933726). We would preserve those MIT notices.

A public clarification from the relevant maintainer or rightsholder, or a documentation correction, would be very helpful. Please state explicitly whether it applies to **`3d5e6fbd98639cb0941b029e23ca17c0e3c4a80a`**, rather than only a newer revision. If an existing statement already answers these questions, a pointer to it would be appreciated.

Thank you for maintaining LibPoly and helping downstream users record its licensing accurately.
