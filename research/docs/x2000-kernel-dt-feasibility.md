# X2000 kernel and Device Tree feasibility

This Phase-3.2 result concerns the investigated Ender-3 V3 KE reference
system. It reconciles the prior upstream-only comparison with the public
Ingenic 6.6 X2000 release identity, a public source mirror, and the separate
NebulaOS KE implementation. It does not build, boot, flash, install, or change
the printer.

## Decision

**Select Ingenic Linux 6.6.18 X2000 SDK as the Phase-3 kernel source basis.**
The reproducible public source basis is the Llixuma mirror commit
`a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b`; the selected approach is that
base plus a small, separately reviewed Ender-3 V3 KE board patch set. It is not
a selection of NebulaOS as a distribution, firmware image, update model,
Klipper fork, or PRTouch implementation.

This supersedes the earlier conclusion that no public, versioned
XBurst2/X2000 platform basis existed. That conclusion was false because the
upstream-only review did not account for the released Ingenic SDK platform.
Linux 6.12 remains useful as an upstream comparison target, but it is not the
leading implementation basis: reproducing XBurst2 platform support there would
require a large forward-port effort before board work could begin.

Phase 3.2 is **complete** as a feasibility and source-basis decision. Its
Phase-3.3 entry condition was a separately authorized, non-persistent prototype
using a new KE DTS and a minimal, attributed patch series; it must not copy an
image or adopt NebulaOS wholesale.

That was the Phase-3.2 entry decision. The later `2026.1.a` result establishes
the first functional Open-Host alpha on the investigated reference system, so
the active work is now development, stabilization, and integration toward final
`2026.1`. It does not retroactively broaden this feasibility decision or qualify
unvalidated peripherals.

## Provenance boundary

Three distinct facts must not be conflated:

| Category | Evidence | What it establishes | What it does not establish |
| --- | --- | --- | --- |
| Ingenic release identity | Ingenic's public Gitee repository `ingenic-dev/ingenic-linux-docs` lists `ingenic-linux-kernel6.6-x2000-v1.0-20250221`. | Ingenic publicly documented a Linux 6.6 X2000 release. | A GitHub repository was published by Ingenic. |
| Public source mirror | `Llixuma/ingenic-linux-kernel6.6-x2000-v1.0-20250221`, pinned at `a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b`. | A reviewable public source tree for the selected basis. | Official Ingenic authorship or a signed/hash-verified identity with the Gitee release. |
| Community KE prior art | `coreflake1/NebulaOS-kernel`: its `main` branch is exactly `a98…`; `openke` descends from it. | A separately reviewable KE board adaptation and reported hardware qualification. | Automatic applicability to this reference system or permission to reuse all of NebulaOS. |

The mirror is therefore described only as a **public source mirror**. The
remaining provenance limitation is explicit: no official source-to-mirror
checksum or signature was found in this bounded review. The kernel subtree at
the pinned commit declares GPL-2.0 in `kernel/kernel-6.6/COPYING`; the SDK as a
whole is multi-component and must be licensed per selected file. Any adopted
NebulaOS-derived kernel change must retain its file notices, identify the exact
commit and author, and be carried as a small GPL-compatible patch. Firmware,
NVRAM, user-space, and other non-kernel material require separate provenance
and redistribution review.

## X2000 SDK evidence

The pinned source tree identifies itself as Linux **6.6.18**. It contains:

- XBurst2 CPU nodes, X2000 interrupt controller and core OST timer in
  `module_drivers/dts/x2000/x2000.dtsi`;
- X2000 clock-controller binding `ingenic,x2000-clocks` and implementation
  `module_drivers/drivers/clk/ingenic-v2/clk-x2000.c`;
- X2000 pinctrl, UART (`ingenic,8250-uart`), I2C, SPI, SDHCI/eMMC/SDIO,
  USB PHY/DWC2, watchdog, display and DPU nodes in `x2000.dtsi`;
- a Halley5-v30 board basis in `dts/x2000/halley5_v30.dts`; and
- `arch/mips/configs/x2000_halley5_v30_linux_defconfig`.

This is a complete XBurst2/X2000 **platform basis**, not an upstream board
enablement and not an Ender-3 V3 KE DTS. XBurst2 core, clocks,
interrupt/timers, I2C, MMC/SDIO, display, USB PHY/DWC2 and watchdog are
vendor-driver/platform paths. Generic `spi-gpio`/spidev, UVC/V4L2, much of the
input framework, and `brcmfmac` are upstream components that can be used around
that platform. The existing upstream
6.12 X2000 pinctrl, SPI, DWC2 and DWMAC pieces do not replace the missing core
platform, clocks, MMC, I2C, display and watchdog work.

## KE board reconciliation and NebulaOS prior art

NebulaOS changes `halley5_v30.dts`; it does not provide a separately named KE
DTS. Treat it as board-specific prior art to be reduced into a new KE DTS, not
as a drop-in Halley5 board file.

| Required area | SDK / NebulaOS evidence | Classification for this project |
| --- | --- | --- |
| X2000 core, clocks, interrupt/timer, pinctrl | SDK provides the platform; NebulaOS adds small bounds fixes in core-OST and IRQ-map parsing. | SDK platform is required; the two fixes are **CODE EXISTS**, to be individually reviewed. |
| eMMC | SDK has X2000 SDHCI; NebulaOS corrects Halley5-derived `msc0` to the observed 8-bit eMMC route. | **CODE EXISTS** and boot is part of NebulaOS hardware qualification; exact KE DTS still required. |
| `ttyS1` / F005 | SDK supplies UART1; NebulaOS adds the narrow UART1 TX/RX pin group and enables it. | **PROVEN BY NEBULAOS HARDWARE** for its Klipper/MCU connection; keep the project's Mainline-F005 path as the acceptance reference. |
| ADXL / Host MCU | The SDK's Halley DTS contains a disabled `spi-gpio`/spidev template; its reviewed defconfig does not enable `CONFIG_SPI_GPIO`. NebulaOS does not provide an ADXL345-specific change. | **INFERRED**: enable the generic driver deliberately and use the observed reference endpoint only after resolving GPIOs and adapter numbering in the KE DTS. |
| NS2009 touch | NebulaOS adds GPL-licensed `drivers/input/touchscreen/ns2009.c`, its Kconfig entry, an I2C4 `nsiway,ns2009` node, and an optional `pendown-gpios` board extension. | **CODE EXISTS**; its interface must be isolated and accepted on this reference. No upstream-Linux support claim follows. |
| Display / 480x272 | NebulaOS enables the DPU and adds `panel-openke-general-480x272.c` plus board GPIO wiring. | **PROVEN BY NEBULAOS HARDWARE** for GuppyScreen display output; panel timings and GPIO ownership remain board-specific review items. |
| SDIO / CYW43438 / WLAN | SDK provides SDHCI; NebulaOS carries MSC1 power/reset/clock and SDIO handling changes. Its public documentation reports Wi-Fi qualification on the product family. | **PROVEN BY NEBULAOS HARDWARE** for Wi-Fi; the upstream `brcmfmac` route, the bounded KE Network-Smoke path, and the WLAN firmware/NVRAM provenance are now documented. Redistribution and production behavior remain open. |
| USB / UVC camera | SDK supplies X2000 USB PHY/DWC2; NebulaOS corrects board VBUS wiring and enables standard UVC userspace support. | **PROVEN BY NEBULAOS HARDWARE** for camera; our observed USB-UVC route is consistent, while appliance USB roles remain deliberately narrow. |
| Watchdog/reset | SDK supplies `ingenic,watchdog`; NebulaOS adds an explicit stop-at-probe fix. | **CODE EXISTS**; it was not separately named in the hardware-qualification scope. Preserve BootROM recovery independently. |

NebulaOS's public release documentation pins its hardware-qualified developer
baseline to kernel commit `295b7101d751fd888ae39e6f1746a4a940664a5f` and
records, on 2026-08-15: boot, Wi-Fi, Klipper/MCU connection, Moonraker,
Mainsail, GuppyScreen, camera, `G28` homing, PRTouch and Z-offset calibration
passed. It explicitly does **not** claim pause/resume/cancel or a full
representative print. This is strong external prior art, not a substitute for
our later reference-device acceptance. In particular, PRTouch is **not** a
requirement for this project's already proven Mainline-F005 first-print path.

### Later Phase-3.3b reference-system evidence

This Phase-3.2 table records the information available for the source-basis
decision; it is not retroactive evidence for that decision. A later bounded
Slot-B Network-Smoke on 2026-08-23 directly proved the project-selected SDIO
path on the investigated reference system: SDIO enumeration, `brcmfmac`
firmware start, WPA association, DHCP/default route, ICMP, and non-interactive
public-key SSH all worked while the automatic p1 rollback to Stock A was already
armed. This closes the local functional acceptance item for that exact bounded
configuration. The firmware/NVRAM provenance is documented in
[`x2000-prototype-build.md`](x2000-prototype-build.md); redistribution,
production persistence, normal-reboot behavior, and any other board peripheral
remain separate questions. The detailed evidence is recorded in
[`x2000-ab-bringup-plan.md`](x2000-ab-bringup-plan.md).

## Candidate comparison

| Candidate | X2000 / KE work needed | Patch burden (0--4) | Decision |
| --- | --- | --- | --- |
| A. Ingenic Linux 6.6.18 X2000 SDK + minimal KE board work | Retain vendor XBurst2 platform; write a KE DTS; carry only needed UART1, eMMC, SDIO/WLAN, USB, display, NS2009 and watchdog fixes after per-patch review. | **2 — bounded board adaptation.** The SoC core already exists; NebulaOS identifies small, separable KE prior-art changes. | **Selected.** |
| B. Upstream Linux 6.12 LTS + forward ports | First provide XBurst2 core, clocks, interrupt/timer, I2C, MMC/SDIO, display, USB-phy/DWC2 integration and watchdog platform support, then the same KE DTS/peripheral work. | **4 — platform forward port plus board adaptation.** | Not selected. |

The maintained upstream 6.6 LTS line has a shorter projected kernel.org
maintenance horizon than 6.12, but an embedded appliance benefits more here
from a bounded, auditable vendor patch set than from a much larger 6.12 forward
port. The SDK's 6.6.18 baseline is not itself a current stable point release;
future maintenance must be an explicit, reviewed 6.6 stable-backport policy,
not an assertion that the vendor tree is current.

## Historical Phase 3.3 entry boundary

Phase 3.3 may prepare a non-persistent prototype only from the selected pinned
source and a project-authored KE DTS/patch series. It must first enumerate each
adopted change, its upstream or vendor origin, license, and reference-system
evidence. It must retain the existing lower boot boundary and use a separately
authorized temporary handoff method. No installer, partition ownership,
Buildroot system, flash, reboot, or printer access is authorized by this
decision.

This is the boundary that preceded the bounded `2026.1.a` result; it is not a
description of the current development state. Current Slot-B and Production
development boundaries are recorded in
[`x2000-ab-bringup-plan.md`](x2000-ab-bringup-plan.md).

## Sources

- [Ingenic public Linux documentation repository](https://gitee.com/ingenic-dev/ingenic-linux-docs),
  inspected 2026-08-21; it lists the X2000 release identity stated above.
- [Public Llixuma X2000 6.6 mirror](https://github.com/Llixuma/ingenic-linux-kernel6.6-x2000-v1.0-20250221),
  inspected at `a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b` on 2026-08-21.
- [NebulaOS kernel](https://github.com/coreflake1/NebulaOS-kernel), inspected
  2026-08-21: `main` resolves to `a98…`; `openke` resolves to
  `88a0e1ecc6ace7c9e4ad99d6fa49e272180fd5a9`.
- [NebulaOS release documentation](https://github.com/coreflake1/NebulaOS),
  inspected 2026-08-21, for the stated hardware-qualification scope and limits.
- [Linux kernel releases](https://www.kernel.org/category/releases.html),
  inspected 2026-08-21, for the maintained-LTS comparison.

## Preserved Phase-3.1 selection criteria and decision

These criteria and the then-current Phase-3.2 decision were moved from the hardware-interface contract. They describe the historical choice before the productive Linux-stable migration.

Phase 3.1 made no open partition, A/B, installer, rollback, or bootloader
decision. A valid later outcome at that time was to keep stock structures
reserved and choose a separate image/update strategy after stock-return
effects were understood. The later Fre3nder A/B design superseded that
deferral; see [OTA architecture](../../docs/ota.md).

### LTS and Buildroot selection criteria

Phase 3.2 must compare pinned, maintained candidates rather than selecting a
kernel or Buildroot release for novelty. A candidate must be evaluated in this
order:

1. X2000 CPU/SMP, DRAM, eMMC, UART, SPI, I2C, display/touch, SDIO WLAN, camera,
   USB as required, and reset/watchdog needs;
2. maintainable LTS/security and bug-fix support;
3. upstream support before vendor patches, with each unavoidable patch scoped;
4. reproducible, pinned source and toolchain inputs;
5. practical boot time and memory footprint for 256 MiB RAM; and
6. a read-only image, separate persistent data, controlled image activation,
   and rollback design that does not consume stock structures by assumption.

Buildroot must likewise be a stable, pinned release used to construct an
appliance, not a rolling general-purpose distribution.

### Phase-3.2 feasibility result

The authorized sanitized binding capture and the public source reconciliation
are complete. This feasibility record
selects the pinned Ingenic Linux 6.6.18 X2000 SDK mirror as the source basis.
It also limits NebulaOS to attributable KE prior art; Phase 3.3 must create a
project-authored KE DTS and only the smallest reviewed patch set.
