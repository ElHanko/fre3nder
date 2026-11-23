# X2000 kernel audit, November 2026

Recorded on 2026-11-23 for Fre3nder `2026.6.a` on the reference Creality
Ender-3 V3 KE. The source comparison ends at
`9d43d1d3f8540f6d7c93d7d1cfabd45141ee44c9` on
`fix/x2000-l2-dma-invalidation`. The [integration record](x2000-kernel-fix-integration-2026-11.md)
holds the four local fixes, build identities and test results. Keep the
conclusions tied to this configuration and these revisions during a later
kernel upgrade.

## Source references

| Source | Reference and role |
| --- | --- |
| Fre3nder | [Project repository](https://github.com/ElHanko/fre3nder). The audited source is the pinned Linux base plus five X2000 patches. The board input is `module_drivers/dts/x2000/ender3-v3-ke.dts` in the reproduced kernel. The compiled DTB, effective configuration and ELF were inspected. |
| Linux stable | [Linux 7.3.4 at `7595a62d45ee1a2297eafa5f2ef5d0a45142d84d`](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/commit/?id=7595a62d45ee1a2297eafa5f2ef5d0a45142d84d), baseline tree `d07c331ebf5acbde9ebf9caea9eac6e33b07ad77`. Basis for generic MIPS, MMC/SDHCI, Serial Core, timekeeping and GPIO behavior. |
| Original Ingenic SDK | [February 2025 Linux 6.6 SDK at `a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b`](https://github.com/Llixuma/ingenic-linux-kernel6.6-x2000-v1.0-20250221/tree/a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b/kernel/kernel-6.6). Source of the retained Ingenic platform delta. The [vendor-baseline history](../x2000-kernel/vendor-baseline-port/README.md) records extraction and pruning. |
| Later Ingenic source | [K1 Debian kernel](https://github.com/k1-debian/linux). The MMC, TLB and GPT commits linked below provide inspectable later Ingenic code. The K1 tree and its board data are comparison sources. |
| NebulaOS/OpenKE | [KE kernel at `1e6ab35fc75758397e1ef69b2834b699e149aaba`](https://github.com/NebulaOS-KE/NebulaOS-kernel/tree/1e6ab35fc75758397e1ef69b2834b699e149aaba/kernel/kernel-6.6). Board-specific fixes and diagnostics on an Ingenic-derived 6.6 tree. Fre3nder's existing display and touch patches preserve the earlier `88a0e1ecc6ace7c9e4ad99d6fa49e272180fd5a9` source attribution. |

The [Ingenic developer portal](https://forum.ingenic.com),
[Gitee documentation](https://gitee.com/ingenic-dev/ingenic-linux-docs) and
[official GitHub organization](https://github.com/ingenic-official) were
surveyed for later SDKs. The release note for 5.10 V11.0 describes
release packaging, Halley5 board configurations and changes to GPT end-LBA
handling, USB gadget serial, and restart without the watchdog-class
driver. Driver comparisons use the public 6.6 SDK mirror and the later K1
commits. The source checks left three releases unverified: a complete
5.10 V11.0 archive, a complete 5.10 V12.0 archive and a separate newer
official X2000 6.6 source release. The X2000-v12 SPL discussed in earlier
research belongs to the bootloader tree. [5.10 V11.0 release note](https://forum.ingenic.com/official-docs/id-809.html),
[X2000-v12 SPL evidence](x2000-fre3nder-required-kernel-delta.md#watchdog-retention-decision).

[`configs/x2000/sources.json`](../../configs/x2000/sources.json) is the
canonical version and digest list. The five-patch replay order is
[`0001` platform](../../patches/kernel/0001-x2000-platform.patch),
[`0002` display](../../patches/kernel/0002-x2000-display.patch),
[`0003` touchscreen](../../patches/kernel/0003-x2000-touchscreen.patch),
[`0004` WLAN](../../patches/kernel/0004-x2000-wlan.patch) and
[`0005` board](../../patches/kernel/0005-x2000-board.patch). The audited
result tree is `7abdbf56ee232e7e789e7183ff98b7a2b12ec1a6`. To review the
closed branch range, use `git log 8d33ef3..9d43d1d3` and `git show` with
the commit IDs in the integration record. Source filenames below are
relative to the reproduced kernel. The build derives that tree from the
pins and patch files, with the artifact proof described in the
[build guide](../../docs/build.md). GPL-covered kernel material retains its
source notices and the existing [licensing policy](../../docs/licensing-and-provenance.md).

### Upstream boundaries and remaining vendor paths

The 2026-11-12 MIPS v2 review submission covers platform selection, DT
boot policy, PRID and CPU probing. The 7.3.4 baseline recognizes the
original XBurst-II implementation ID but classifies it as `CPU_XBURST`.
The proposal adds an explicit `CPU_XBURST2` type and extends the generic
Kconfig, board matches and load addresses. It makes a bootloader DT or a
built-in fallback selectable. This can reduce the Fre3nder platform
initialization delta once equivalent changes land and the KE DT handoff
is qualified. Fre3nder's XBurst-II cache, SMP/INTC and OST implementations
remain separate porting work. The series reports PRID checks on other
boards. [MIPS v2 cover letter](https://lkml.rescloud.iu.edu/hypermail/linux/kernel/2611.1/14346.html),
[7.3.4 CPU probing](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/arch/mips/kernel/cpu-probe.c?id=7595a62d45ee1a2297eafa5f2ef5d0a45142d84d).

Generic MIPS TLB generation, SMP CPU-mask APIs, MMC, Serial Core,
Clocksource and gpiolib already provide services used by the vendor code.
The demonstrated `num_possible_cpus()` accounting failure and its SMP API
fix are the subject of the earlier migration. That boot-time ext4 fault
has a specific trace and explanation. [7.3.4 migration record](x2000-linux-7.3.4-migration.md).

| Area | Effective implementation and comparison |
| --- | --- |
| SMP, INTC and IRQ migration | Fre3nder uses vendor XBurst-II bring-up, CPU interrupt dispatch and `cpu-intc-map`. In `irq-ingenic-chip.c`, `xburst2_set_affinity()` updates routing by masking the previous CPU-local INTC bank and restoring the enabled state on the target. `ingenic_irq_migration()` checks pending bits and looks for a CPU in both the IRQ affinity and idle masks. The older upstream Ingenic IRQ controller uses a different topology. NebulaOS moved the `cpu-intc-map` bounds check before the write. Fre3nder stores the valid four cells but can report the size warning at the final cell. The NebulaOS change affects DT parsing. IRQ loss or misrouting would require separate evidence. [NebulaOS INTC fix](https://github.com/coreflake1/NebulaOS-kernel/commit/e123bb14fd8e3fd03a5550cf187a5a9f64faf281). |
| OST and clocks | The vendor core/global OST driver and X2000 clock provider are active. Generic timekeeping and `sched_clock_register()` are upstream. The separate upstream Ingenic OST variants do not bind the compiled `ingenic,core-ost` node. See [OST locking](#ost-locking). |
| MMC and SDIO | The generic MMC/SDHCI framework is upstream. The X2000 SDHCI platform driver, instance clock selection and the KE WLAN power and rescan sequence are active vendor or Fre3nder code. An alternative generic power sequence must reproduce the physical REG_ON and first-rescan behavior. See [MMC signal voltage](#mmc-signal-voltage). |
| USB/DWC2 | The 7.3.4 baseline has X2000 DWC2 parameters (HS, 16-bit UTMI, 16 host channels) and the generic X2000 PHY implementation. The effective build uses dual-role DWC2 with the vendor legacy PHY and external VBUS detection. The board uses GPC9 to drive VBUS and GPD17 to detect it, as checked against OpenKE's stock-DTB finding. Generic DWC2 and PHY are candidates for a host-only reduction. Replacing the current path also requires a decision on role switching and qualification of board VBUS control. [Upstream DWC2](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/usb/dwc2/params.c?id=7595a62d45ee1a2297eafa5f2ef5d0a45142d84d), [OpenKE USB wiring](https://github.com/coreflake1/NebulaOS-kernel/commit/c902097d1a79c21ef6717d7e4ecc1db2a9233990). |
| Watchdog and reset | The effective `CONFIG_INGENIC_WDT` driver unconditionally clears the pre-timeout mask in `ingenic_wdt_probe()` with `IRQ_SWITCH=0`. NebulaOS reproduced a shared TCU interrupt storm after the counter reached its pre-timeout compare in a watchdog test. Its mask fix covers that driver defect. Relevance to the KE workload depends on an armed counter reaching the same state. The productive inputs define no watchdog feeder. The independent `jz_wdt_restart()` path remains required for platform reset. NebulaOS's later pre-timeout capture adds diagnostics and panic behavior. [Watchdog mask fix](https://github.com/NebulaOS-KE/NebulaOS-kernel/commit/785b600f7807b39707eee6658f222a72a15ef5bf), [Pre-timeout capture](https://github.com/NebulaOS-KE/NebulaOS-kernel/commit/ece4732b0ab0f21c43aa6abddca111c06cb572cb). |
| I²C4 | The NS2009 touch device uses `ingenic,x2000-i2c`. `i2c_ingenic_reset()` and `i2c_disable_clk()` lack NebulaOS's interrupt-mask writes. The compiled KE I²C4 node has `clk-always-enable`, so the transfer and timeout cleanup paths skip clock gating on this controller. The reported NebulaOS gated-MMIO path requires that gating. Upstream `i2c-jz4780.c` has the similar X1000 controller model and would need an X2000 match and board qualification. [Upstream I²C](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/i2c/busses/i2c-jz4780.c?id=7595a62d45ee1a2297eafa5f2ef5d0a45142d84d), [NebulaOS I²C fix](https://github.com/NebulaOS-KE/NebulaOS-kernel/commit/95d0321ef4270adb3e080fe2125ab81fcb232b91). |
| Pinctrl/GPIO | The board uses the vendor pin-mux, GPIO banks and IRQ bindings. Baseline `drivers/pinctrl/pinctrl-ingenic.c` already has X2000 data gated by `CONFIG_MACH_X2000`, which the baseline MIPS Kconfig lacks. A migration can make the generic data selectable and translate the DTS bindings. The 7.3.4 descriptor API and optional-`NULL` semantics already apply to the current consumers. [Upstream pinctrl](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/pinctrl/pinctrl-ingenic.c?id=7595a62d45ee1a2297eafa5f2ef5d0a45142d84d). |

The [required kernel delta study](x2000-fre3nder-required-kernel-delta.md)
contains the earlier file-by-file inventory of these subsystems and the
clean-port alternatives. Its classifications apply to the stated historical
trees. The active 7.3.4 board bindings and configuration govern this audit.

## TLB probe and RiXi

**Decision: do not port without an X2000-specific TLB-probe race.** The
Ingenic commit `b8040d22e088c4256206d2c4d5797d5de24349f7` changes two
independent paths. In `arch/mips/mm/tlbex.c` it forces
`cpu_has_tlbex_tlbp_race()` true for `CONFIG_MACH_XBURST2` and suppresses
the warning in the RiXi load fallback for that build. In
`arch/mips/include/asm/elf.h` it clears `READ_IMPLIES_EXEC` in native
MIPS32 `SET_PERSONALITY2` before generic ELF loading can set the flag for the
new program. The latter addresses inherited execution policy, with no change
to the TLB probe instructions. [Ingenic commit](https://github.com/k1-debian/linux/commit/b8040d22e088c4256206d2c4d5797d5de24349f7).

The original SDK and Linux 7.3.4 already generate the probe-miss guard when
`cpu_has_htw` or `cpu_has_shared_ftlb_ram` is true. In
`build_r4000_tlbchange_handler_head()`, the relevant sequence is `TLBP`,
`EHB`, `MFC0 C0_INDEX`, `BLTZ` to `label_leave` and its delay-slot `NOP`.
The guard skips the update if `C0_INDEX.P` reports a miss even though the
software page table had an entry. Forcing the predicate would emit this
existing guard on XBurst-II when both feature tests are false. Replacement
of a probed entry between a successful `TLBP` and `TLBR` remains possible.
In `build_r4000_tlb_load_handler()`, the legacy RiXi fallback for a valid
PTE with `cpu_has_rixi && !cpu_has_rixiex` executes `TLBR`, then reads the
selected `C0_ENTRYLO0` or `C0_ENTRYLO1`. Its Valid bit determines whether
to enter the page-fault path for a possible RI/XI fault. The Ingenic change
removes the generation-time warning on that path while retaining the
potentially racing readback. Linux 7.3.4 also has a warning in its separate,
conditional huge-page fallback.
[Upstream TLB generator](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/arch/mips/mm/tlbex.c?id=7595a62d45ee1a2297eafa5f2ef5d0a45142d84d).

The effective Fre3nder build is 32-bit MIPS32r5 with `MACH_XBURST2`, SMP,
two hardware threads and 4 KiB pages. Its X2000 feature override makes
`cpu_has_rixi` true. `cpu_probe()` tests whether `PageGrain.IEC` sticks before setting the
dedicated exception feature `MIPS_CPU_RIXIEX`. HTW is separately detected
from CP0 and can be disabled by setup. `cpu_has_shared_ftlb_ram` is a
specific probed feature. Two Linux CPUs alone do not set it. The
`CPU_XBURST2` TLB write arm in Fre3nder's `build_tlb_write_entry()` emits the
chosen TLB write and a trailing `NOP`. This is a distinct write-side hazard
sequence. The applicable native 32-bit `SET_PERSONALITY2` in the audited
tree has no unconditional `READ_IMPLIES_EXEC` clear. The separate 64-bit
macro does. The linked `mips_elf_read_implies_exec()` checks the stack mode
in this build. A reproducible sticky-flag test would be grounds for a
separate ELF fix.

Static ELF inspection covers the generator and the probe predicates. The
actual exception handlers are assembled at boot from CPU and CP0 state,
so compiler disassembly does not prove which guard or RiXi fallback was
emitted on the printer. A later comparison would need feature evidence
and a handler or fault trace from the reference CPU. The suppressed warning
alone gives no indication that the race has been handled. [Fre3nder MIPS
delta](../../patches/kernel/0001-x2000-platform.patch),
[Upstream CPU probing](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/arch/mips/kernel/cpu-probe.c?id=7595a62d45ee1a2297eafa5f2ef5d0a45142d84d).

## MMC signal voltage

**Decision: do not port `268722060e121a9cf4ce27ee257e935df40edc01` for the
KE.** The patch adds the platform `voltage_switch()` callback on the 3.3 V
branch of `sdhci_start_signal_voltage_switch()`. It runs after the
`SDHCI_CTRL_VDD_180` clear and before the regulator request and settling
check. The existing 1.8 V branch already calls the platform callback after
its regulator step and host-control update, including in Linux 7.3.4. The
current 3.3 V branch clears the host bit and handles `vqmmc`, with no call
to the platform callback. The K1 vendor driver additionally switches on
`mmc->ios.signal_voltage` instead of testing the `SDHCI_SIGNALING_180`
capability bit, so a request to return to 3.3 V can actually undo a previous
1.8 V board selection. Its board DTS adds the switching GPIO for MSC2 on
M300 `gewu_v12`. The platform helper manipulates `CPM_EXCLK_DS` bit 31,
the Port E MSC pad voltage selection. [Ingenic MMC commit](https://github.com/k1-debian/linux/commit/268722060e121a9cf4ce27ee257e935df40edc01),
[Upstream SDHCI](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/mmc/host/sdhci.c?id=7595a62d45ee1a2297eafa5f2ef5d0a45142d84d).

The effective KE DTB instead uses MSC0 eMMC on **PD17–PD26** and MSC1
WLAN on **PD08–PD13**. MSC0 advertises eight-bit `mmc-hs200-1_8v` at up to
100 MHz with tuning. That property describes signaling capability, while
the `voltage-ranges` property describes the host OCR range. Neither is a
measurement of a rail. The KE supplies no `vqmmc` regulator or external
`ingenic,sdr` switch for MSC0. Its vendor reset descriptor is absent. MSC1
is fixed SDIO with four-bit high-speed support, a 3.3 V `vmmc` supply, a
32 kHz clock and a separate GPD4 `wlan-reg-on` sequence. The manual detect
and rescan path powers and enumerates the WLAN device. It has no Port E
voltage switch or `vqmmc`. MSC2 and its **PE00–PE05** pin group are
inactive on this board. None of these paths needs the M300 external
voltage selection. The independently adopted MSC clock-register fix
corrects controller selection at identification speed.
[Ingenic MSC wiring and binding reference](https://gitee.com/ingenic-dev/ingenic-linux-docs/blob/ingenic-master/zh-cn/X2000/X2000-halley5/kernel/eMMC_SD_SDIO_%E6%8E%A5%E5%8F%A3.md),
[Fre3nder board patch](../../patches/kernel/0005-x2000-board.patch),
[Fre3nder WLAN patch](../../patches/kernel/0004-x2000-wlan.patch).

On 7.3.4, `gpiod_set_value(NULL, ...)` is a no-op through `validate_desc()`.
The older `IS_ERR()` test around `sdr_v18` therefore does not imply a NULL
dereference. It can still let a voltage callback with an absent switch
change the unrelated Port E pad bit. The optional power/reset setters have
the same descriptor distinction. `sdhci_ingenic_power_set()` is not
registered in the active ops. A NULL reset descriptor leaves the delay
sequence but drives no GPIO. K1's `IS_ERR_OR_NULL()` skips those cases,
yet its parse path still accepts real descriptor errors and downgrades
their logs, including a possible `-EPROBE_DEFER`. The true allocation and
probe-error issues are listed below. No later NebulaOS change in the audited
branch established a KE need for the M300 callback or GPIO. The voltage
change can affect enumeration or timing on a board with the relevant
switch. The KE source and DT provide no evidence tying it to a full Linux
freeze. [Upstream gpiolib](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/gpio/gpiolib.c?id=7595a62d45ee1a2297eafa5f2ef5d0a45142d84d).

## OST locking

**Decision: defer the NebulaOS trylock.** A common lockless read for the
Clocksource and `sched_clock` is the preferred later change if the register
semantics are confirmed. The SDK and Fre3nder have the same read, timer
and PM paths in `module_drivers/drivers/clocksource/ingenic_core_ost.c`.
Fre3nder's SDK-to-7.3.4 difference in this file is the OF iterator API and
one blank line. NebulaOS `3b6086868516c618bf9108fcfd02eaffe0993557` adds
`nebulaos_ost_read_cnt()` and switches only the scheduler callback to an
IRQ-saving trylock with a lockless fallback. It preserves the blocking
`raw_spin_lock_irqsave()` in `core_clocksource_get_cycles()`.
[NebulaOS OST diff](https://github.com/NebulaOS-KE/NebulaOS-kernel/commit/3b6086868516c618bf9108fcfd02eaffe0993557),
[Fre3nder OST source in the platform patch](../../patches/kernel/0001-x2000-platform.patch#L33920).

### Effective hardware and initialization

| Item | Audited implementation |
| --- | --- |
| Global counter | DTB `ingenic,core-ost` window at `0x12000000`. `G_OSTER` at `+0x04` enables counting, `G_OSTCR` at `+0x08` clears it. `G_OSTCNTH` at `+0x0c` and `G_OSTCNTL` at `+0x10` expose the halves used by the driver. `G_OSTCNTB` at `+0x14` is defined and unused by the Linux reader. |
| Per-CPU clockevents | `0x12100000` and `0x12100100`, CPU-local IRQ input 4, one 32-bit event timer for each hardware thread. `core_timerevent_interrupt()` clears the flag and updates the event under the local event lock, then releases it before invoking `event_handler()`. These are separate register banks and locks from the global counter. |
| Rate and gate | 24 MHz `ext`, divisor 1. The X2000 clock provider gives both timer classes handles to `gate_ost`, `CPM_CLKGR` bit 20. CPU frequency changes do not select the OST clock. |
| Effective kernel | `CLKSRC_INGENIC_CORE_OST`, `GENERIC_SCHED_CLOCK`, high-resolution timers, two CPUs, `PREEMPT`, `DEBUG_SPINLOCK` and `SUSPEND` are enabled. The older Upstream Ingenic timer variants and hard-lockup detector are not enabled. The existing ELF shows the OST callback's `G_OSTER` guard and jump to the locked reader. |

`core_clocksource_init()` initializes `clocksource_lock` and `tmr->lock`,
enables the gate handle and programs the global counter before registering
`jz_clocksource` and `sched_clock`. Jiffies supply the early scheduler clock
before registration. The two registrations use a 63-bit Clocksource mask
and a 64-bit scheduler counter. The callback's mapping/enable guards can
return zero before counter enable. `tmr_src_enable()` and
`tmr_src_disable()` write `G_OSTER` under `tmr->lock`, separate from
`clocksource_lock`. Clocksource selection can disable the source while the
scheduler callback remains registered, which can affect scheduler time.
Removing the read lock would not change that lifecycle.

On the syscore suspend path, the scheduler clock is frozen and fast
timekeeping is halted before `tmr_src_suspend()` drops the shared gate
references. The ELF's initcall order registers timekeeping before
`sched_clock`, so syscore suspend runs their callbacks in reverse and
resume re-enables the gates before the scheduler re-samples its epoch.
`tmr_src_resume()` enables both handles. The OST has no
`CLOCK_SOURCE_SUSPEND_NONSTOP` flag. The vendor code does not use
`clocksource_lock` to serialize these gate changes.
[Ingenic OST guide](https://forum.ingenic.com/official-docs/id-698.html?model=72&ver=v1.0),
[Linux scheduler-clock framework](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/kernel/time/sched_clock.c?id=7595a62d45ee1a2297eafa5f2ef5d0a45142d84d),
[Linux timekeeping](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/kernel/time/timekeeping.c?id=7595a62d45ee1a2297eafa5f2ef5d0a45142d84d).

### Counter consistency and progress

On MIPS32, each `readl()` reads one 32-bit device register. The built
sequence is High, Low, High with `sync` barriers. Matching High probes
identify the Low sample's high period when they are ordered, live views of
the same monotonic counter. An intervening Low carry changes High, so the
reader retries. Low wraps about every 178.957 seconds at 24 MHz. A full
64-bit rollover also changes the two High samples if it occurs during the
read. The normal counter is monotonic modulo its width. Overlapping readers
may complete in a different order from their Low samples. The barriers
order accesses and provide no atomic 64-bit hardware snapshot.

Whether two readers can interleave safely depends on the hardware. A Low
read that populates a separate, unused buffer is compatible with this
algorithm if `G_OSTCNTH` remains live. A shared latch changing what the
second High read returns would require its documented read protocol. The
public X2000 data sheet confirms the global/event timer split. The XBurst-II
CPU manual covers the OST IRQ registers. Neither describes this particular
counter latch behavior or gated-device read completion. The published
X2000 SYSOST proposal uses a single Low read, which does not verify the
High behavior. Linux 7.3.4 uses lockless High/Low/High for both time paths
on the ARM Global Timer. This is an algorithm comparison. The X2000
register semantics still need independent confirmation.
[X2000 data sheet](https://www.lumissil.com/assets/pdf/core/X2000_E_H_DS.pdf#page=9),
[XBurst-II CPU manual](https://www.manualslib.com/manual/2646351/Ingenic-Xburst-2-Cpu-Core.html?page=93),
[X2000 SYSOST proposal](https://lkml.iu.edu/2112.1/02156.html),
[Upstream ARM example](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/clocksource/arm_global_timer.c?id=7595a62d45ee1a2297eafa5f2ef5d0a45142d84d).

The retry is unbounded if the hardware presents inconsistent High values
indefinitely. A valid stopped counter returns a stable sample. A blocked
MMIO transaction cannot reach the next retry and either implementation can
stall there. Free-running register reads, correct latch behavior and
gate availability are separate prerequisites for a trustworthy timestamp.

### Locking failure paths

- **CPU loses progress with `clocksource_lock` held.** The other CPU can
  wait indefinitely in either clock path with its own IRQs disabled. This
  is a demonstrated source dependency and a possible way to propagate an
  existing stall to the other hardware thread.
- **Same-CPU reentry.** Ordinary local IRQs are masked. An NMI or
  synchronous exception can still enter diagnostics. For example, the
  MIPS data bus error handler logs through `printk()` and can reenter the
  same lock if the fault occurred inside the read. Spinlock diagnostics
  may themselves log before the lock is available. Healthy MMIO reads
  have no direct recursive call.
- **First diagnostic record.** `vprintk_store()` gets `local_clock()`
  before reserving the record. In this configuration it reaches the
  registered OST scheduler callback. With a busy lock,
  `raw_spin_trylock_irqsave()` returns with the original IRQ flags and no
  lock held. On success the flags are restored on unlock. The NebulaOS
  fallback can therefore keep this path running with a frozen owner,
  assuming functional counter reads. Displaying timestamps is a separate
  option from generating the timestamp.
- **Remaining blocking reader.** `ktime_get()`, timekeeping updates, the
  high-resolution timer IRQ and fast NMI-capable timekeeping can all use
  `core_clocksource_get_cycles()` when the OST is selected. A diagnostic
  callback using these interfaces can still block. The timer machinery
  can also block before invoking a software watchdog callback. The
  NebulaOS watchdog dump improves observability, but the dump's first
  message itself still needs working OST MMIO for its timestamp.

[Printk record creation](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/kernel/printk/printk.c?id=7595a62d45ee1a2297eafa5f2ef5d0a45142d84d),
[MIPS exception handlers](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/arch/mips/kernel/traps.c?id=7595a62d45ee1a2297eafa5f2ef5d0a45142d84d),
[IRQ-saving trylock](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/include/linux/spinlock_api_smp.h?id=7595a62d45ee1a2297eafa5f2ef5d0a45142d84d).

Keeping the present code retains the blocking dependency. The trylock
alternative mitigates one path but already assumes safe concurrent MMIO
when it matters. The common-reader alternative removes both reader waits
and avoids duplicated paths, with broader effects if the assumption is
wrong. Once the X2000 assumption is validated, the minimal backport is to
keep the ordered reads in `core_clocksource_get_cycles()`, assemble the
result from two `u32` halves and remove its `flags`, lock and unlock.
`sched_clock()` continues to use that function with its existing guards.
Remove `clocksource_lock` and its initialization, keeping `tmr->lock` and
the per-CPU locks. The Clocksource mask, registration rate and PM sequence
need no change. A future port would update only the platform patch and
its source pins.

Targeted offline tests would model a stable counter, a Low carry at each
read boundary, full wrap and interleaved readers. Lifecycle tests should
cover early fallback, enable guards and suspend/resume ordering. Verify the
final MIPS read order in the ELF. The release decision additionally needs
a register specification or controlled X2000 evidence over a Low rollover
with concurrent reads. Simulated MMIO can validate the algorithm but cannot
establish the device's latch behavior.

## Open findings

| File and function | Technical finding | KE relevance and risk | Decision and next evidence |
| --- | --- | --- | --- |
| `ingenic_core_ost.c`, `ingenic_ost_init()` | `of_io_request_and_map()` returns error pointers in 7.3.4. The two mapping checks only compare against `NULL`. | Confirmed failure-path bug. The effective DTB has both resources and the current build has a valid OST registration path. A mapping failure could reach invalid MMIO during startup. | Separate probe fix. Verify error handling and resource cleanup using a failed-map fixture. |
| `ingenic_core_ost.c`, `ingenic_ost_init()` `cpu-ost-map` | The limit is checked after storing and incrementing, so the last valid entry raises the overflow message. With the current loop the break also stops processing before a fifth value when `NR_CPUS=2`. | Confirmed misleading warning with the four values in the effective DTB. The valid map is stored in full. An out-of-bounds write is not demonstrated for this loop. | Compare NebulaOS's pre-write check and test exact-length, odd and oversized maps. [`2d507671c`](https://github.com/coreflake1/NebulaOS-kernel/commit/2d507671c4aff8f424cbc90e7c0fb7ae525606a1). |
| `ingenic_core_ost.c`, `core_clocksource_get_cycles()` | Live High/Low and `G_OSTCNTB` latch behavior on simultaneous reads is unverified. | Hardware-dependent. An inconsistent sample can affect both timekeeping and the scheduler. | Defer lockless reads pending the evidence specified above. |
| `sdhci-ingenic.c`, `sdhci_ingenic_parse_dt()` and probe | Optional `ingenic,sdr`, power and reset descriptor errors are logged and swallowed. `-EPROBE_DEFER` can disappear. `card_gpio` allocation failure returns success and can leave `pdata->gpio` unset for later dereference. | Confirmed error-path issues. The optional switches are absent on the KE. The distinct `wlan-reg-on` path propagates descriptor errors. Allocation failure is possible and has not been observed here. | Separate correction with tests for optional absence, `-EPROBE_DEFER`, other error pointers, `-ENOMEM` and probe cleanup. Leave the board-voltage policy separate. |
| `ingenic_uart.c`, `serial47xx_get_divisor()` | Multiple ports share the writable `quot1` divisor array. Per-port locks do not serialize simultaneous `set_termios()` on separate ports. | Source-level concurrency risk. UART1 is the qualified MCU connection. Concurrent cross-port baud changes are not established for the normal KE workload. | Investigate only with a multiport case. A later fix can use call-local divider values. |
| `block/partitions/efi.c`, `efi_partition()` | `get_capacity()` returns 512-byte sectors while GPT entries use logical-block LBAs. The fallback still compares these and uses `disk_size - 1`. | The 4Kn all-ones fixture demonstrates the wrong adjustment followed by rejection. The current eMMC path uses 512-byte logical sectors. | Leave this out of the integrated fix. Use explicit logical-LBA units and test both 512-byte and 4096-byte fixtures before changing the policy. |
| `block/partitions/efi.c`, `efi_partition()` | The retained fallback uses the physical last LBA. A standard GPT table reserves space beyond `last_usable_lba` for its backup metadata. | Existing behavior confirmed by boundary fixtures. Standard GPT compatibility and the reference eMMC's historical whole-disk fallback may require different handling. | Keep the present policy pending a separate decision backed by standard and vendor-layout fixtures. |

## Full Linux freezes

The operator reported complete Linux stalls during long prints, including
one after roughly 2.5 hours. Ethernet/SSH and the display lost progress.
The audit has no fault trace identifying a single cause for these incidents.
NebulaOS independently reported a partial hang with Klipper and the display
still working on 2026-11-06, and a full mid-print stall on 2026-11-08 with a
60-second watchdog reset and no surviving kernel log. Its later pre-timeout
and pstore work aims to preserve evidence. [NebulaOS freeze report](https://github.com/NebulaOS-KE/NebulaOS-kernel/blob/1e6ab35fc75758397e1ef69b2834b699e149aaba/wiki/Freeze-Diagnosis.md).

| Hypothesis | What the evidence supports |
| --- | --- |
| L2/DMA ordering or coherence | The SDK lacks the pre-read in the active Hit-based L2 invalidation branch. The ordering change is technically justified. No freeze trace or completed comparative endurance result attributes the stalls to this path. |
| OST/Clocksource deadlock | The shared blocking lock can amplify a stall or hide its diagnosis. Reentry is possible in fault context. The audited record has no OST lock-owner or backtrace evidence for the reported freezes. |
| Hardware MMIO stall | Noncompleting MMIO could hold a CPU and any lock it owns. NebulaOS described a gated-I²C access path following a timeout. The KE I²C4 transfer path keeps its clock enabled, and a bus stall on the KE still lacks a register or trace identifying the affected block. |
| UART synchronization | The TX/kfifo races are established in code and can stop MCU traffic. They do not explain why both CPUs and unrelated services lost progress. The audited console path lacks evidence of an active Ingenic UART1 kernel console or a matching deadlock trace. |
| TLB probe race | A mis-handled probe could lead to translation faults or memory corruption on affected silicon. The inspected K1 change and the static ELF supply no X2000 failure trace or proof that this happened. |
| Other kernel/driver paths | SDIO, IRQ routing, watchdog, I²C and other paths still need matching device evidence. Several NebulaOS changes are board-specific fixes or diagnostic changes, with separate validation requirements. |

There is no evidence-based ordering of these hypotheses. **None of the
integrated fixes has been shown to eliminate the complete Linux hangs.**
The installed L2-only diagnostic kernel and the four-fix local image are
distinct. Use the artifact identities in the
[integration record](x2000-kernel-fix-integration-2026-11.md#build-identities)
when interpreting future print, log and watchdog observations.

## Decision matrix

| Topic | Source | Finding | Decision | Commit | Open validation |
| --- | --- | --- | --- | --- | --- |
| L2 Hit invalidation | Ingenic SDK, NebulaOS and Fre3nder MIPS cache code | Leading uncached read added for the affected range branch. | Integrated | `9996a96c` | DMA ordering on hardware, long prints and freeze attribution. |
| MSC clock at identification rate | OpenKE/NebulaOS `858509a4a` | MSC1 formerly programmed the MSC0 clock register. | Integrated | `87527bf` | WLAN enumeration and eMMC behavior on the new image. |
| GPT adjusted range | K1 Debian `35fd77723d` | In-memory end and size used different values, with endian and range concerns. | Integrated | `cd6246f6` | KE boot using this image. 4Kn and usable-LBA policy are separate. |
| UART PIO and console | NebulaOS `bc785d6f`, `73422bd7` | Lock TX/flush, RX and modem state, defer SysRq and preserve console IER. | Integrated | `9d43d1d3` | MCU load, live IRQ timing and endurance. |
| TLBP predicate and RiXi warning | K1 Debian `b8040d22e0` | Existing feature-gated guard. Forcing it leaves the TLBR fallback race unhandled. | Deferred | — | X2000-specific probe miss and emitted handler evidence. |
| MSC signal-voltage callback | K1 Debian `268722060e` | Board switch applies to M300 MSC2 on Port E. KE uses MSC0/1 on Port D. | Not required | — | Revisit for a board with the actual switch. |
| OST scheduler trylock | NebulaOS `3b6086868` | Protects `printk` timestamps from lock wait and retains Clocksource blocking. | Deferred | — | X2000 register-latch and parallel-read evidence. |
| OST probe and CPU-map validation | Fre3nder source and NebulaOS `2d507671c` | Error-pointer handling and misleading size warning. | Further investigation required | — | Failed mappings and DT parser fixtures. |
| MSC optional GPIO and allocation failures | Vendor SDHCI and upstream GPIO | NULL descriptor no-op, genuine probe errors can be lost. | Further investigation required | — | Failure propagation and cleanup fixtures. |
| UART shared divisor | Vendor UART | Global `quot1` used across ports. | Further investigation required | — | Simultaneous termios on distinct ports. |
| GPT 4Kn and usable end | Vendor fallback and Fre3nder fixtures | 512-byte capacity units and physical end limit are inherited. | Further investigation required | — | Logical-LBA tests and policy for standard and vendor GPT. |
| Upstream replacement of vendor platform paths | Linux 7.3.4 and MIPS v2 series | Generic framework already reused. Active X2000 glue still supplies controller behavior and board wiring. | Further investigation required | — | Compare landed changes by reached call path and qualify replacements. |
| Watchdog, IRQ migration and gated I²C | Fre3nder and NebulaOS comparison | Masking/diagnostic fixes and vendor IRQ routing require their own checks. | Further investigation required | — | Verify the effective KE IRQ, timeout and clock-gating paths against a matching failure trace. |
