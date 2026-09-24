# Licensing and provenance policy

This project combines original documentation and tooling with analysis of
third-party open-source and vendor software.

The repository must remain reproducible without unnecessarily redistributing
third-party firmware, proprietary binaries, or device-specific data.

This document is a project policy, not legal advice.

## General rule

Do not commit or redistribute a third-party artifact unless its origin and
redistribution rights are understood.

When redistribution rights are unclear, prefer:

- an official source link;
- version and filename;
- cryptographic hashes;
- documentation describing the artifact;
- a locally executed import/extraction process;
- patches against publicly licensed source;
- an independently written implementation of required behavior.

## Upstream Klipper

Upstream Klipper is distributed under the GNU General Public License, version
3 (GPLv3).

Policy:

- preserve upstream license and copyright notices;
- record exact upstream revisions used for comparisons and builds;
- publish modifications according to the applicable upstream license;
- prefer patches or clearly maintained source history.

## Buildroot and X2000 kernel provenance

The productive RootFS is built from the official upstream Buildroot 2025.02.18
LTS source. Its exact release and commit are pinned in
`configs/x2000/sources.json`.

The RootFS uses an XBurst II target patch against upstream Buildroot and an
internal Buildroot toolchain. The patch records its exact Ingenic SDK and
upstream Buildroot provenance; no Ingenic userspace toolchain is redistributed.

The productive kernel source starts from the official stable Linux
`v6.6.157` release at commit
`79643295eba17affbd16ca97f3ef04c90266b28c`, tree
`e2963aecbdc92c10a52434a5ae11a82522dc38d5`.

Fre3nder applies an ordered five-patch hardware-support series from
`patches/kernel/`:

1. `0001-ingenic-x2000-platform-v6.6.157.patch` contains the retained
   Ingenic-derived X2000 platform support after Fre3nder pruning and
   forward-porting.
2. `0002-ender3-v3-ke-display-v6.6.157.patch` contains the Ender-3 V3 KE
   display integration derived from the public NebulaOS/OpenKE implementation.
3. `0003-ns2009-touch-v6.6.157.patch` contains the NS2009 touchscreen
   integration derived from the public NebulaOS/OpenKE implementation.
4. `0004-ingenic-ender3-v3-ke-wlan-v6.6.157.patch` contains the retained
   Ingenic-derived WLAN power/reset/detect integration required by the
   qualified Ender-3 V3 KE path.
5. `0005-fre3nder-ender3-v3-ke-integration-v6.6.157.patch` contains
   Fre3nder's board integration and the concrete forward-port adaptations
   required for Linux `v6.6.157`.

The Ingenic-derived layers are traceable to the public Ingenic X2000 kernel
repository at commit
`a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b`. The display and touch layers
record their derivation from `coreflake1/NebulaOS-kernel` at commit
`88a0e1ecc6ace7c9e4ad99d6fa49e272180fd5a9`.

Applied in order, the current five patches produce source tree
`fd3535dcfe9b4adca5c2e77f10b7672ae6a0a786`.

The original provenance split produced
`40d8b5cee4341505c12373e9bb1386e80241f0d6`, matching the source tree that had
already been built and hardware-qualified as `6.6.157-fre3nder`. The later
A/B slot-neutral kernel change updated the Fre3nder-specific board-integration
layer to remove embedded slot-specific boot arguments, producing the current
tree while retaining the same provenance-separated patch structure.

The historical Ingenic SDK and RT23 trees remain provenance and migration
reference material. Neither is a productive kernel source checkout.

All files under `patches/kernel/**` are classified as `GPL-2.0-only` by
`REUSE.toml`; upstream and third-party copyright notices remain applicable
where present.

Kernel and RootFS are both built with the upstream Buildroot internal GCC
13.4.0/binutils 2.43.1 toolchain. They remain separate compiler contracts:
the kernel uses Kbuild's MIPS32r5/O32/soft-float/legacy-NaN flags through the
underlying real cross-GCC, while userspace uses Buildroot's
MIPS32r2/O32/hard-float/FPXX/NaN2008 wrapper contract. Buildroot is not sourced
from the SDK, and no Ingenic toolchain is a productive build input.
The F005 build reuses that same Buildroot userspace wrapper for its X2000
`c_helper.so`; its separate `arm-none-eabi` toolchain targets only the
GD32F303 bare-metal MCU.

### CYW43430 WLAN firmware

Buildroot 2025.02.18 selects its regular `linux-firmware` package at release
`20250211` for the WLAN firmware. The upstream tag resolves to commit
`5bc5868b7ee5a243abdd73cfcd3bbf7166f4f42f`; Buildroot verifies the release
archive with SHA-256
`2de1345897bf839d532c5de0fdb348770ca2a5f4edfb21971582597abb45297d`.
The selected package supplies `cypress/cyfmac43430-sdio.bin` and
`cypress/cyfmac43430-sdio.clm_blob`, while upstream `WHENCE` defines the
`brcm/brcmfmac43430-sdio.bin` and `.clm_blob` driver aliases.

These two files are proprietary binary firmware, not open source. `WHENCE`
marks them redistributable and assigns `LICENCE.cypress`. That agreement
permits object-code reproduction and distribution solely for use with Cypress
integrated-circuit products; it does not grant a general right to use the
firmware with arbitrary compatible hardware. The agreement does not expressly
require its text to accompany every binary copy. Fre3nder nevertheless copies
the unmodified `LICENCE.cypress` from the unpacked Buildroot package into
`/usr/share/licenses/linux-firmware/` so the applicable terms travel with the
RootFS. The exact source, file hashes, license-file hash, and restriction are
recorded in `configs/x2000/sources.json`.

The generic `brcm/brcmfmac43430-sdio.txt` is the unmodified AZW372 file
`firmware/infineon/CYW43438/cyw43438_azw372.txt` from
[Radxa/rkwifibt commit `3d93dbcf5ff6e04fa760a56a0dad9f6077394072`](https://github.com/radxa/rkwifibt/blob/3d93dbcf5ff6e04fa760a56a0dad9f6077394072/firmware/infineon/CYW43438/cyw43438_azw372.txt).
It is 1016 bytes with SHA-256
`6167b8aaa5e80eabe09ac5bd8570760e5241aa3a9a6243a94be9fcba33cc1915`.
Fre3nder preserves every upstream byte, including `ccode=ALL`, the power
tables, and all RF values; it does not adapt them to Creality hardware.

Radxa/rkwifibt applies its repository-wide BSD-3-Clause license. The upstream
copyright notice and license are vendored unchanged and installed in the
RootFS under `/usr/share/licenses/radxa-rkwifibt/`; `REUSE.toml` records the
same copyright and license identity for both files. Source and binary
redistribution are therefore permitted subject to the BSD-3-Clause notice and
disclaimer requirements.

The WLAN licensing boundary is now:

- `.bin` and `.clm_blob` come from linux-firmware `20250211` and remain subject
  to `LICENCE.cypress`;
- the unchanged `.txt` comes from Radxa/rkwifibt and is BSD-3-Clause;
- no locally extracted Creality WLAN NVRAM remains a build input, so the WLAN
  BYOF requirement is gone; and
- embedding the Radxa NVRAM in a Kernel or including it in a RootFS no longer
  prevents public redistribution on account of that NVRAM. Distributions must
  still carry and follow both applicable license notices.

On 2026-09-14 the exact official linux-firmware `.bin` and `.clm_blob` and the
vendored Radxa NVRAM were qualified together on the investigated reference
system in Kernel SHA-256
`93207a7b627442759bbc74716876c94592edfacb94cacd0ea52f1a9c09ab9d13` and
RootFS SHA-256
`f86ad04f6a63653ef79f0f8280a91d951838102cba8d509e019e78332404055b`.
The runtime NVRAM matched its pinned SHA-256 and the resulting WLAN path passed
boot, WPA association, DHCP, and gateway traffic. This hardware evidence does
not alter either component's licensing terms and does not qualify Bluetooth.

## Moonraker RootFS baseline

Moonraker is consumed from `https://github.com/Arksine/moonraker.git` at
`985c1d0bbeb90bc057d34a232c9dc3b05e0c6c8d`, recorded in
`configs/x2000/sources.json` as GPL-3.0-only. The RootFS stages that public
source as a pinned Git checkout, including its license and upstream identity,
rather than embedding an untracked vendor binary.

Pure-Python dependencies that are not supplied by the qualified Buildroot
runtime are recorded in `configs/x2000/moonraker-python-wheels.json`. Each
entry records the exact package version, wheel filename, SHA256 digest,
upstream package URL, and applicable license. The wheel files themselves are
downloaded during the local build, verified against those hashes, and are not
committed to the repository.

Native Python dependencies remain reproducibly built with the Fre3nder
Buildroot toolchain. In particular, the project-local
`python-streaming-form-data` Buildroot package records version `2.1.0`, its
PyPI source URL and archive SHA256, MIT license, license-file hash, and its
`python-aiofiles` Buildroot dependency. Project-local Buildroot package
definitions record the corresponding source and license provenance where
applicable.

The pure-Python wheel contents are staged into the RootFS Moonraker environment;
the wheels themselves remain build inputs outside Git. Source, dependency, and
license provenance remains explicit in the source and wheel manifests.

## Fre3nderScreen RootFS baseline

Fre3nderScreen is consumed from the Fre3nder-maintained fork
`https://github.com/ElHanko/fre3nderscreen.git` at commit
`589275a7c3a7fd904184bb5f15b058b7c0376911`, under `GPL-3.0-only`. The Fre3nder source label is
`0.0.26-beta+fre3nder.589275a`. The repository retains the original GuppyScreen Git history and upstream provenance;
the application at this pin identifies as Fre3nderScreen.

The fork descends from the published `ballaswag/guppyscreen` `0.0.26-beta`
baseline at commit `cf5c6d7539a2dca090ca71c177f57a2d96df443a`. Exact source and
submodule identities are recorded in
`configs/x2000/sources.json`. The component builder fetches the pinned public
source and submodules before the network-disabled build phase and builds them
with Fre3nder's Buildroot GCC 13.4.0 MIPS userspace toolchain.

The pinned submodules remain LVGL 8.3.11 and lv_drivers under MIT, libhv under
BSD-3-Clause, and spdlog under MIT. The vendored wpa_supplicant control-client
source remains BSD-3-Clause. Their license texts are copied alongside the GPL
text into `/usr/share/licenses/fre3nderscreen/`.

Fre3nderScreen retains the three dependency patches shipped by the source tree.
The dedicated pin removes the old generic product matrix and carries its
runtime-path overrides, corrected touch rotation, fixed 272x480 portrait
layout, and flat single-printer configuration directly in source. Fre3nder
does not execute or redistribute the removed GuppyScreen installers or
Creality-specific binary payloads.

The previous pin `baa4f6689ac7334d240107529f6d3c42a1297319` is the local-UI source
covered by the recorded `2026.2.a` hardware qualification. The new
Fre3nderScreen pin is a development integration candidate and is not described
as hardware-qualified until a new build and hardware validation are recorded.

## Public Creality Klipper source

Creality publishes Ender-3 V3 KE Klipper source under the GPL.

Policy:

- preserve applicable copyright and license notices;
- document the exact source revision used;
- keep vendor modifications distinguishable from project-written changes;
- comply with applicable GPL requirements when distributing derived source.

The license of the public Klipper source repository must not automatically be
assumed to apply to unrelated files contained in complete Creality firmware
images.

## Creality firmware packages

Examples include official firmware images and OTA bundles.

Policy:

- do not commit them unless redistribution permission has been verified;
- link users to the official source where possible;
- record filename, version, source, size, and cryptographic hash;
- allow project tooling to consume user-supplied firmware files locally.

The preferred workflow is "bring your own firmware": users obtain vendor
firmware from its original source and project tooling processes the local file.

This also applies to Creality's `.ingenic` brick/wire-recovery images, OTA `.img`
bundles, Ingenic Cloner archive, and bundled drivers. Official URLs, filenames,
versions, published sizes, retrieval dates, and locally computed hashes may be
documented. The binaries themselves must remain outside this repository unless
their redistribution rights are separately verified.

The presence of recovery tools or binaries in a repository carrying a top-level
open-source license must not be treated, without file-specific evidence, as proof
that the firmware images, Cloner binary, or drivers may be redistributed under
that license.

## Extracted vendor binaries

Examples may include:

- Creality application servers;
- display binaries;
- upgrade binaries;
- vendor-specific shared libraries;
- compiled Python extension modules.

Policy:

- do not commit extracted binaries where redistribution rights are unclear;
- record names, hashes, architecture, dependencies, and interfaces where useful;
- associate them with their source firmware through provenance metadata;
- prefer replacement with open components where practical.

## Vendor-specific binary Klipper extensions

Vendor-specific binary modules may be technically important even when their
redistribution status is unclear.

Policy:

- do not publish a binary merely because it was found in a firmware image;
- document how it is loaded and which interfaces it exposes;
- identify corresponding publicly available source where it exists;
- distinguish observed behavior from copied implementation;
- prefer an open implementation of required functionality where feasible.

## Device backups

Examples include:

- complete eMMC images;
- boot0 and boot1 captures;
- partition images;
- `/overlay` archives;
- `/usr/data` archives.

Policy:

- never commit device backups;
- treat them as private recovery material;
- store hashes and non-identifying technical metadata separately where useful;
- protect backup media because it may contain credentials, certificates,
  network settings, print history, and other private data.

## Factory and identity data

Examples include:

- serial numbers;
- MAC addresses;
- factory identity partitions;
- pairing information;
- certificates;
- device-specific keys.

Policy:

- never publish concrete values;
- do not copy identity data between printers;
- keep values only in private local documentation or protected backups where required for recovery.

## Credentials and secrets

Never commit:

- passwords;
- private SSH keys;
- API keys;
- authentication tokens;
- cookies;
- private certificates or keys;
- Wi-Fi credentials;
- cloud credentials.

This prohibition also applies to Git-ignored documentation.

## Provenance records

Every externally sourced artifact used for analysis should, where practical,
have provenance information containing:

- artifact name;
- source project or vendor;
- source URL or repository;
- version;
- commit hash where applicable;
- retrieval date;
- cryptographic hash;
- applicable license or redistribution status;
- notes about modifications.

A future machine-readable manifest may be added for this purpose.

## Source comparison

When comparing Klipper trees, always record all three identities where applicable:

```text
upstream revision
public Creality revision
reference firmware version / extracted tree
```

Do not describe a difference as a Creality modification unless the comparison
basis supports that conclusion.

A difference may instead result from:

- different upstream ages;
- vendor patches;
- backported upstream commits;
- later unpublished vendor changes;
- build-generated files;
- local modifications on the inspected printer.

## Clean replacement strategy

The project goal is functional hardware support, not preservation of proprietary
implementations.

Where vendor-specific functionality is required but suitable redistributable
source is unavailable, prefer:

1. document externally observable behavior and interfaces;
2. determine the actual hardware requirement;
3. check whether modern upstream Klipper already provides an equivalent;
4. design an open implementation where necessary;
5. validate it against the hardware without copying proprietary code.

## Project licensing and license transition

The repository uses the path-specific assignments in `REUSE.toml`; complete
license texts are stored in `LICENSES/`. The root `LICENSE` is a concise
licensing overview and does not replace those assignments.

Repository revisions through
`bb22b9d915a2205d7d9b4b38adf436d512f4d8b7` were made available under the MIT
License. That historical grant remains valid and is not revoked.

Beginning with the license-transition revision, project-authored Fre3nder
system material is distributed under the GNU Affero General Public License,
version 3 or (at the recipient's option) any later version
(`AGPL-3.0-or-later`). This includes the productive Fre3nder system, build and
configuration tooling, tests, and product documentation unless a specific file
has a different applicable license.

Project-authored material in `research/` is distributed under the MIT License.
This exception applies only where the project owns the relevant rights; it does
not classify all research files as MIT.

Third-party and derived material remains subject to its respective license.
In particular:

- upstream Klipper material remains subject to Klipper's applicable license;
- Creality-published Klipper material remains subject to its applicable GPL
  terms;
- files derived from or incorporating GPL-covered source must continue to
  satisfy the applicable GPL requirements;
- third-party firmware and binaries remain subject to their own licenses or
  redistribution terms.

The license transition applies to distributions of the project beginning with
the transition revision. It does not rewrite history, alter existing tags, or
withdraw permissions already granted under MIT.

The F005 host/config candidates and sanitized pin matrix are project-authored
documentation/configuration material. They contain no vendor binaries, private
paths, device identity data, saved calibration or private calibration values,
or Creality binary extensions;
their stock-derived pin/function observations are documented as observations
of the investigated reference rather than redistributed firmware.

## Public GD32F303 MCU port

The public patches under `patches/klipper/` modify upstream Klipper source. They
are derived GPL-covered source and remain subject to Klipper's applicable GPLv3
terms, including preservation of notices and the corresponding source/license
obligations when redistributed. Their comparison basis is the recorded upstream
commit in `patches/klipper/0001-gd32f303-f005-mainline.patch` and
`docs/gd32f303-mainline-port.md`. `0002` is the narrow X2000 passive-UART
bring-up patch; `0003` is a test-only BLTouch no-auto-retry patch; and `0004`
is the separate production opt-in passive-UART patch used by the Develop
RootFS. The pinned upstream Klipper runtime source and `0004` remain GPLv3
material when staged in that RootFS; their exact commit and patch identity are
recorded in `configs/x2000/sources.json`.

The qualified F005 binary recorded in `configs/x2000/f005-mcu-release.json` is
GPL-3.0-only and is embedded in the immutable RootFS baseline by the X2000
build. It is a reproducible output from the recorded public upstream Klipper
revision, public patch series, and F005 configuration; it is not a vendor
binary. Distribution of a RootFS containing that binary remains subject to the
applicable GPL source and notice obligations.

The accompanying build recipe, configuration template, and explanatory
documentation are project-authored Fre3nder system material and are licensed
under `AGPL-3.0-or-later` where they do not incorporate third-party source.
They do not contain vendor firmware, device-backup data, extracted binaries,
or device-specific identity values.

## Trademarks

Product and company names may be used descriptively to identify compatibility
and source material.

This project is independent and should not imply endorsement by or affiliation
with Creality or the Klipper project.
