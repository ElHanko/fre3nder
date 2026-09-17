# X2000 Clean-Port Implementation Plan

## Basis

Target: upstream Linux v6.6.18 at
`d8a27ea2c98685cdaa5fa66c809c7069a4ff394b`.

Architecture authority:
[`x2000-fre3nder-required-kernel-delta.md`](x2000-fre3nder-required-kernel-delta.md).
This document orders implementation work; it neither reopens those decisions
nor claims hardware qualification. The kernel uses plain `CONFIG_PREEMPT=y`.
Builds and hardware tests below are future, separately authorized gates.

Validation labels are `static`, `compile`, `DT compile`, `kernel link`, `boot`,
and `hardware`. Each patch lists only its earliest useful gate.

## KISS principles

- Extend upstream v6.6.18 where its abstraction already fits.
- Separate generic X2000 support from Fre3nder board/product support.
- Keep Kconfig, Makefile, binding and source changes together when inseparable.
- Add no future-board framework, helper, hook or compatibility layer.
- Add one final-form board DTS; do not create temporary DTS variants.
- Use vendor/OpenKE code as register and sequence evidence, not wholesale code.
- Do not port the exclusions settled in the architecture document.

## Dependency chain

```text
generic MIPS machine and built-in DT handoff
  -> X2000 clocks
  -> XBurst2/X2000 core IRQ
  -> X2000 OST
  -> XBurst2 secondary-cache maintenance
  -> existing upstream X2000 pinctrl/GPIO data
  -> X2000 DTSI + Fre3nder DTS
  -> X2000 SDHCI -> MSC0/eMMC -> rootfs
  -> XBurst2 SMP/CCU + per-CPU IRQ/OST
  -> UART, I2C/touch, PWM, USB host, MSC1/WLAN, GPIO endpoints
  -> direct-RDMA fbdev + Fre3nder panel
```

The first hardware attempt is a clean `CONFIG_SMP=n` build. This uses final
machine, clock, IRQ, OST, cache, pinctrl, DT and storage code, so it creates no
throwaway infrastructure. SMP is optional at this stage because vendor `smp.o`
and `xburst2_smp_ops` are conditional on `CONFIG_SMP`. Secondary-cache support
is not optional: CPU0 DMA/cache correctness needs it before the first boot.

## Patch series

### PATCH 01 — Add the minimal X2000 UP platform

Purpose:
Select X2000 in generic Ingenic MIPS, reuse the upstream DT handoff where
applicable, add XBurst2 secondary-cache maintenance and the minimal WDT
restart primitive.

Depends on:
Upstream Linux v6.6.18.

Files:
modify:
- `arch/mips/Makefile`
- `arch/mips/ingenic/Kconfig`
- `arch/mips/generic/board-ingenic.c`
- `arch/mips/mm/{c-r4k.c,sc-mips.c}`

Repository artifact:
- `research/patches/linux/0001-mips-ingenic-add-minimal-x2000-up-platform.patch`

Reference:
- vendor `xburst2/core/{prom.c,sc.c}` and `soc-x2000/{setup.c,reset.c}`

Minimal content:
- reuse generic MIPS CPU discovery and DT handoff; add X2000 CPU/DMA
  selections, the XBurst2 cache-geometry and DMA-invalidate edge fixes, and
  one-shot reboot
- preserve the qualified X2000 kernel compiler contract by applying
  `-mnan=legacy` only when `CONFIG_MACH_X2000=y`
- define `MACH_X2000` so existing upstream X2000 pinctrl data is reachable

Excluded:
- early print, SMP/CCU, watchdog class, PM, fastboot, proc/debug, DMMU

Validation:
`compile`

Risk:
high

### PATCH 02 — Add the X2000 clock provider

Purpose:
Express the required X2000 tree on the upstream Ingenic CGU framework.

Depends on:
Patch 01.

Files:
modify:
- `drivers/clk/ingenic/{Kconfig,Makefile}`
- `drivers/clk/ingenic/{cgu.c,cgu.h}` only if existing descriptors cannot fit
new:
- `drivers/clk/ingenic/x2000-cgu.c`
- X2000 CGU binding and clock-ID header

Reference:
- vendor `ingenic-v2/clk-x2000.c`; upstream `cgu.*` and `x1830-cgu.c`

Minimal content:
- clocks for CPU/buses, INTC, OST, UART1, MSC0/1, USB, I2C4, PWM and DPU

Excluded:
- debugfs and clocks exclusive to dropped audio/camera/GMAC/PDMA/MIPI paths

Validation:
`kernel link`

Risk:
high

### PATCH 03 — Add the XBurst2/X2000 interrupt topology

Purpose:
Provide CPU dispatch and the X2000 core interrupt domain.

Depends on:
Patches 01-02.

Files:
modify:
- `drivers/irqchip/{Kconfig,Makefile}`
new:
- reduced XBurst2/X2000 irqchip source
- X2000 interrupt binding, schema and ID header

Reference:
- vendor `irq-ingenic-{cpu,chip}.c`; OpenKE map-bounds correction

Minimal content:
- CPU0 dispatch, core domain, DT map parsing, required affinity, bounds check

Excluded:
- diagnostics and unrelated wake/PM extensions

Validation:
`kernel link`

Risk:
high

### PATCH 04 — Add the X2000 core OST

Purpose:
Provide the global clocksource and CPU0 clockevent, retaining only the final
per-CPU operations later used by SMP.

Depends on:
Patches 02-03.

Files:
modify:
- `drivers/clocksource/{Kconfig,Makefile}`
new:
- reduced X2000 core-OST source and DT binding

Reference:
- vendor `ingenic_core_ost.c`; OpenKE map-bounds correction

Minimal content:
- global counter, CPU clockevent, DT map parsing and bounded pair storage

Excluded:
- SYSOST/TCU alternatives and diagnostics

Validation:
`kernel link`

Risk:
high

### PATCH 05 — Add the reduced X2000 SoC description

Purpose:
Describe only required generic providers/controllers with upstream bindings.

Depends on:
Patches 01-04.

Files:
modify:
- none expected
new:
- `arch/mips/boot/dts/ingenic/x2000.dtsi`

Reference:
- vendor `dts/x2000/{x2000.dtsi,x2000-pinctrl.dtsi}`

Minimal content:
- CPUs, buses, clocks, INTC, OST, pinctrl/GPIO, UART1, MSC0/1, DWC2/PHY,
  I2C4, PWM and DPU; non-core devices disabled by default

Excluded:
- sound, GMAC, PDMA, hardware SPI, camera/ISP, SFC, watchdog, MIPI/LVDS

Validation:
`static` until Patch 06 supplies the including DTS

Risk:
medium

### PATCH 06 — Add the complete Fre3nder board description

Purpose:
Add one final-form Ender-3 V3 KE DTS and built-in DTB selection.

Depends on:
Patch 05.

Files:
modify:
- `arch/mips/ingenic/Kconfig`, `arch/mips/boot/dts/ingenic/Makefile`
- `Documentation/devicetree/bindings/mips/ingenic/devices.yaml`
new:
- `arch/mips/boot/dts/ingenic/ender3-v3-ke.dts`

Reference:
- `configs/x2000/ender3-v3-ke.dts` and the architecture document

Minimal content:
- memory/root bootargs without `console=ttyS4,115200`; MSC0; UART1 PC23/PC24
- MSC1 GPA1 regulator, GPD4 pwrseq with at least 100 ms asserted, RTC32K on
- GPC9 VBUS regulator, host-only DWC2, upstream PHY, no GPD17
- I2C4/NS2009, PWM3/beeper, panel/reset, backlight and GPIO-SPI ADXL345

Excluded:
- manual WLAN insertion, watchdog node, UART4, USB gadget/OTG, temporary DTS

Validation:
`DT compile`

Risk:
medium

### PATCH 07 — Add X2000 SDHCI for MSC0 and MSC1

Purpose:
Add one controller implementation shared by eMMC and SDIO.

Depends on:
Patches 02-03 and 05-06.

Files:
modify:
- `drivers/mmc/host/{Kconfig,Makefile}`
new:
- `drivers/mmc/host/sdhci-ingenic.c` and X2000 SDHCI binding

Reference:
- vendor `sdhci-ingenic.c/.h`; OpenKE MSC clock-register fix

Minimal content:
- required clock, reset, tuning and ADMA behavior for both controllers
- low-speed writes use the selected controller's `cpm_msc` register

Excluded:
- `ingenic_sdio.c`, raw GPD4, software card-present, power cycle/manual rescan

Validation:
`kernel link`

Risk:
high

### PATCH 08 — Add two-core XBurst2 SMP/CCU support

Purpose:
Enable CPU1 only after the UP eMMC/rootfs path is qualified.

Depends on:
Patches 01, 03-04 and successful UP qualification through Patch 07.

Files:
modify:
- `arch/mips/ingenic/{Kconfig,Makefile}`
- Patch 03 IRQ and Patch 04 OST sources for secondary-CPU initialization
new:
- reduced XBurst2 CCU/SMP source under `arch/mips/ingenic/`

Reference:
- vendor `xburst2/core/smp.c`, `core_base.h` and `ccu.h`

Minimal content:
- two CPUs, secondary entry/reset, mailbox IPI, per-CPU IRQ/clockevent init

Excluded:
- CPU hotplug, debug dumps, tests and unrelated XBurst2 SoCs

Validation:
`kernel link`

Risk:
high

### PATCH 09 — Extend upstream 8250 Ingenic for X2000 UART1

Purpose:
Provide productive `/dev/ttyS1` without the vendor UART driver.

Depends on:
Patches 02-03 and 05-06.

Files:
modify:
- `drivers/tty/serial/8250/8250_ingenic.c`
- `Documentation/devicetree/bindings/serial/ingenic,uart.yaml`

Reference:
- vendor `ingenic_uart.c/.h`; upstream X1000 data; settled divisor decision

Minimal content:
- X2000 match, 64/32 FIFO data, module/24 MHz baud clocks
- divisor hook initializing UMR/UACR: D=8/M=13 at 230400; D=13/M=16 at 115200

Excluded:
- DMA, standalone driver, arbitrary UACR search, console/earlycon changes

Validation:
`kernel link`

Risk:
medium

### PATCH 10 — Admit X2000 in the upstream Ingenic I2C driver

Purpose:
Use unchanged upstream X1000 controller data for I2C4.

Depends on:
Patches 02-03 and 05-06.

Files:
modify:
- `drivers/i2c/busses/i2c-jz4780.c`
- `Documentation/devicetree/bindings/i2c/ingenic,i2c.yaml`

Reference:
- upstream `x1000_i2c_config`; vendor driver only for register comparison

Minimal content:
- X2000 match/fallback and PIO binding without fabricated DMA properties

Excluded:
- vendor driver/debug, 10-bit claim, `I2C_M_NOSTART`, DMA/filter surface

Validation:
`compile`

Risk:
low

### PATCH 11 — Add the NS2009 touchscreen endpoint

Purpose:
Add the small I2C input driver used by Fre3nder.

Depends on:
Patch 10 and Patch 06 GPC15 board data.

Files:
modify:
- `drivers/input/touchscreen/{Kconfig,Makefile}`
new:
- `drivers/input/touchscreen/ns2009.c` and NS2009 binding

Reference:
- `configs/x2000/ke-touch.patch`; OpenKE GPC15 finding

Minimal content:
- address 0x48, polled X/Y, optional active-low pendown GPIO, evdev

Excluded:
- GT9xx and unrelated touchscreen features

Validation:
`compile`

Risk:
low

### PATCH 12 — Add the small ordinary X2000 PWM provider

Purpose:
Drive `pwm-beeper` on PWM3/PC03 through `.apply()`.

Depends on:
Patches 02 and 05-06.

Files:
modify:
- `drivers/pwm/{Kconfig,Makefile}`
new:
- reduced X2000 PWM provider and binding

Reference:
- ordinary-output path in vendor `pwm-ingenic-v2.c`

Minimal content:
- MMIO, clocks, prescaler, period, duty, normal level, enable/disable

Excluded:
- IRQ, DMA, capture, complementary/dead-time, sync, waveform, debug/test/M300

Validation:
`kernel link`

Risk:
medium

### PATCH 13 — Add the minimal X2000 direct-RDMA fbdev

Purpose:
Provide the fixed parallel-RGB display through standard `/dev/fb0`.

Depends on:
Patches 02-03 and 05-06; intentionally late.

Files:
modify:
- `drivers/video/fbdev/{Kconfig,Makefile}`
new:
- minimal X2000 fbdev source, binding, and only any necessary private registers

Reference:
- vendor `fb_stage/{ingenicfb.c,dpu_ctrl.c,dpu_reg.h,dpu_dma_desc.h}`

Minimal content:
- one 480x272x4 coherent buffer mapped with `dma_mmap_coherent()`
- one self-linked direct-RDMA descriptor/channel, 32-bpp input, RGB565 output
- blank/unblank, fixed frame-0 pan, polled stop, all DPU IRQs masked

Excluded:
- extra buffers, pageflip/VSYNC, IRQ handler, DMMU, Composer, vendor ioctls,
  MIPI/LVDS, writeback/V4L2, CSC, debug/sysfs, custom cache/PFN mappings

Validation:
`kernel link`

Risk:
high

### PATCH 14 — Add the Fre3nder RGB panel

Purpose:
Keep product timing/reset data separate from generic DPU support.

Depends on:
Patch 13 and Patch 06 panel node.

Files:
modify:
- Kconfig/Makefile location selected by Patch 13's minimal panel interface
new:
- Fre3nder panel source beside that interface and its DT binding

Reference:
- `configs/x2000/ke-display.patch`; OpenKE RGB565 finding

Minimal content:
- fixed 480x272@60 timing, parallel RGB565 and PB16 reset

Excluded:
- PC21 supply, other panels, dynamic modes, MIPI and LVDS

Validation:
`kernel link`

Risk:
low

No USB driver patch is planned: Patch 06 selects upstream X2000 DWC2/PHY,
host-only mode and GPC9 `vbus-supply`. No separate pinctrl patch is planned:
Patch 01 makes existing X2000 data reachable and Patches 05-06 use it.

## Boot milestones

### A — First clean kernel that compiles/links

Patches 01-06 link as a UP kernel and the complete board DT compiles. This is
offline only, not boot qualification.

### B — First plausible X2000 boot

The UP image reaches clocks, IRQ, OST and the root-mount attempt with secondary
cache handling active. With no required early console, B may be observed in the
same authorized run as C, while retaining its separate acceptance criterion.

### C — Rootfs reachable from eMMC

Patch 07 enumerates MSC0 and mounts/reads the intended p8 SquashFS root while
preserving the established access and recovery path.

### D — Basic printer operation

Patches 08-12 are present; UART1 communicates with the F005 at 230400 and a
required network/access path is qualified. Display is not a prerequisite.

### E — Full currently demonstrated Fre3nder hardware surface

Patches 13-14 are present and the demonstrated eMMC, UART, WLAN, USB, touch,
beeper, ADXL345, backlight and display paths pass their qualification points.

## Hardware qualification points

These are later tests, not work performed by this plan.

- Core UP: reach root-mount attempt with CPU0 clockevents/interrupts active.
- Cache/MSC0: exercise DMA, then mount and read the intended eMMC rootfs.
- SMP: bring CPU1 online; verify mailbox IPI and per-CPU OST activity.
- UART1: F005 communication at 230400; 115200 only in an authorized bootloader
  workflow.
- WLAN: GPA1 active; GPD4 low for at least 100 ms then high; first normal SDIO
  enumeration and `brcmfmac` bind without manual insertion/rescan.
- USB: mass-storage cold boot/hotplug, CDC-NCM and UVC; then early attachment
  and PHY behavior without preemptive quirks.
- Touch: NS2009 coordinate/release reporting through GPC15 pendown.
- PWM: 260 Hz, normal polarity and 50% duty on PWM3/PC03.
- GPIO endpoints: PC22 backlight and ADXL345 through GPIO SPI.
- DPU: alternating patterns through `dma_mmap_coherent()`; blank/unblank; no
  stale regions or IRQ storm with interrupts masked; tearing is acceptable.
- Restart: ordinary reboot through the one-shot WDT path, without `/dev/watchdog`.

## Implementation work packages

1. **UP platform:** Patch 01 only; stop before any unauthorized build.
2. **Clocks:** Patch 02 and its binding/IDs.
3. **Interrupt/time:** Patches 03-04; OST depends on clock and IRQ parents.
4. **DT baseline:** Patches 05-06; reach Milestone A.
5. **Storage/rootfs:** Patch 07; qualify UP milestones B/C before SMP.
6. **SMP:** Patch 08; qualify CPU1 independently of peripherals.
7. **Printer peripherals:** Patches 09-12 in order. USB and WLAN use the
   upstream/generic paths wired in DT, not extra driver patches.
8. **Display:** Patches 13-14 last; complete Milestone E.

Package completion records implementation status only. Hardware qualification
remains separate until the named test passes.

## Current next step

Implement **work package 1 / Patch 01 only**. Do not start Patch 02 or run a
build without a new explicit instruction.
