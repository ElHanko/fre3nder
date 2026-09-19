X2000 kernel port audit

Status note

This document is a historical research record of the initial source-audit
state before the complete RT23 Vendor baseline reconstruction was established.
Statements describing missing proof, pending audits, or an unexecuted build
refer to that earlier state.

The current migration plan and validated baseline status are documented in:

`research/docs/x2000-kernel-port-plan.md`

Purpose

This document tracks the migration of the Fre3nder X2000 kernel support away
from the Ingenic vendor kernel towards a maintainable kernel.org based support
stack.

The goal is not to preserve the Ingenic SDK as a kernel source.

The goal is to identify, isolate and maintain only the architecture, SoC,
board and peripheral support required by the Ender-3 V3 KE / Ingenic X2000.

The migration strategy is deliberately conservative:

1. establish a kernel.org Linux 6.6.18 baseline with sufficiently complete
    Ingenic/XBurst2/X2000 behaviour to boot the hardware;
2. separate the required hardware support from unrelated vendor changes;
3. move that support stack to the current Linux 6.6 LTS release;
4. hardware-qualify the resulting kernel;
5. later migrate the same support stack to a newer suitable LTS kernel.

Bootability comes before simplification.

Repository work branch

Working branch:

x2000-vendor-baseline-port

The branch starts from the Fre3nder main branch.

The existing x2000-clean-port-integration branch remains preserved as
research evidence. Its minimal P01-P14 clean-port work is not discarded, but
it is no longer the starting point for establishing the first bootable
kernel.org baseline.

Canonical source references

Upstream Linux 6.6.18

Repository:

https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git

Commit:

d8a27ea2c98685cdaa5fa66c809c7069a4ff394b

Version:

6.6.18

Canonical read-only Fre3nder reference:

local/research/x2000-kernel/linux-upstream

Ingenic vendor kernel

Repository:

https://github.com/Llixuma/ingenic-linux-kernel6.6-x2000-v1.0-20250221.git

Commit:

a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b

Kernel subtree:

kernel/kernel-6.6

The vendor kernel Makefile identifies the source as Linux 6.6.18:

* VERSION = 6
* PATCHLEVEL = 6
* SUBLEVEL = 18

The tree also contains:

localversion-rt = -rt23

Therefore the vendor source identifies itself as 6.6.18-rt23.

The official Linux RT archive contains a corresponding
6.6.18-rt23 PREEMPT_RT patch series.

This establishes that PREEMPT_RT must be treated as a separately identifiable
baseline component during the audit.

It does not yet prove that the Ingenic tree is byte-for-byte equivalent to:

Linux 6.6.18 + official PREEMPT_RT 6.6.18-rt23 + Ingenic changes

That equivalence must be established by direct source comparison before the
remaining difference is called the Ingenic/X2000 delta.

Current LTS target

As of 2026-09-19, the current Linux 6.6 LTS release is:

6.6.157

The migration sequence is therefore currently:

kernel.org 6.6.18
        +
required XBurst2/X2000 support
        |
        v
bootable Fre3nder baseline
        |
        v
kernel.org 6.6.157
        +
same maintained hardware support
        |
        v
hardware-qualified Fre3nder 6.6 LTS

A migration to a newer LTS kernel is a later project phase and is not part of
the initial bring-up.

Architecture principle

The maintained Fre3nder kernel should eventually consist conceptually of:

kernel.org Linux
    |
    +-- XBurst2 architecture support
    |
    +-- X2000 SoC support
    |
    +-- Ender-3 V3 KE board/device-tree description
    |
    `-- required peripheral drivers

The complete Ingenic SDK must not become a permanent build dependency merely
because it contains the known-working implementation.

Vendor sources are evidence and implementation references, not the desired
long-term architecture.

Initial support classification

The first audit must classify the vendor delta rather than immediately remove
parts of it.

A. XBurst2 architecture support

Expected areas to audit include:

* PRID / CPU identification;
* CPU feature overrides;
* CP0 behaviour;
* L1 instruction and data cache handling;
* L2 / secondary-cache handling;
* TLB handling;
* exception behaviour;
* SMP boot and secondary CPU handling;
* DMA cache coherency handling;
* XBurst2-specific hazards and barriers.

These are architecture support, not ordinary device drivers.

B. X2000 core SoC support

Expected areas to audit include:

* platform initialization;
* interrupt controller;
* clocks / CGU / PLL;
* OST / timer / clocksource;
* reset/watchdog integration;
* pin control where required;
* SoC DMA or other core infrastructure where required.

Each item must be verified from the actual vendor delta before being declared
required.

C. Required peripheral drivers

Expected areas include at least the hardware required to reach and operate the
Fre3nder root filesystem and basic system:

* UART;
* MMC/SDHCI;
* I2C where required;
* PWM where required;
* display/touch support in a later functional layer.

Peripheral support should use an existing upstream driver where possible.
Vendor implementation should only be carried when the required X2000 hardware
behaviour is absent upstream.

D. Board description

This includes:

* Ender-3 V3 KE device tree;
* X2000 device-tree data required by that board;
* board-specific wiring and configuration.

Board description must remain separate from reusable XBurst2/X2000 support
where technically possible.

E. Vendor code not automatically retained

The following classes are not automatically part of the maintained support
stack:

* unrelated Ingenic SoCs;
* ISP/camera vendor frameworks;
* multimedia vendor frameworks;
* debug-only infrastructure;
* vendor procfs/debug interfaces;
* CPUFreq/PM implementation not required for bring-up;
* proprietary or product-specific application integration;
* unrelated SDK compatibility code.

These items may only enter the maintained stack when a concrete dependency is
demonstrated.

PREEMPT_RT policy

PREEMPT_RT and X2000 hardware enablement are separate concerns.

The first source audit must determine the vendor tree as:

upstream Linux 6.6.18
        +
PREEMPT_RT delta
        +
Ingenic/XBurst2/X2000 delta
        +
board/peripheral delta

as far as the available source permits.

Fre3nder must not permanently depend on PREEMPT_RT solely because the vendor
kernel used it.

Whether PREEMPT_RT remains part of the final Fre3nder kernel is a separate
runtime and latency decision.

Evidence already established by previous clean-port work

The previous x2000-clean-port-integration work remains useful evidence.

It established, among other things:

* upstream kernel.org Linux 6.6.18 can be built for this target;
* a substantial amount of XBurst2/X2000 support can be expressed as isolated
    Linux patches;
* the initial minimal P01-P14 port builds successfully but does not boot on
    the reference hardware;
* replacing the upstream compressed-image wrapper with the working Ingenic
    xImage wrapper while keeping the same clean-port vmlinux, config and DTB
    still fails;
* therefore the outer boot wrapper is not the sole cause;
* real behaviour differences remain inside the architecture/platform support;
* at least one concrete example has already been found:
    the vendor XBurst2 local_flush_tlb_all() path differs from the generic
    upstream 6.6.18 TLB invalidation path and was not included in the minimal
    clean port.

The lesson from that work is not that a kernel.org port is infeasible.

The lesson is that the first port removed vendor behaviour too early.

Revised bring-up strategy

The new baseline follows the opposite direction:

working vendor behaviour
        |
        v
identify complete relevant hardware delta
        |
        v
reproduce that behaviour on kernel.org 6.6.18
        |
        v
prove boot
        |
        v
remove or replace unnecessary vendor behaviour
        |
        v
move maintained stack to current 6.6 LTS

The first kernel.org baseline should prefer behavioural completeness over
minimal patch size.

Simplification starts only after bootability has been established.

Audit gate 1: establish the real baseline

Before implementation, determine:

1. whether the vendor tree corresponds to the official
1. 6.18-rt23 source plus Ingenic changes;
2. the complete source delta between that baseline and the pinned vendor tree;
3. which delta files affect MIPS/XBurst2;
4. which affect X2000 core SoC support;
5. which affect required Ender-3 V3 KE peripherals;
6. which are unrelated vendor/SDK modifications;
7. which existing upstream implementations can already replace vendor code.

No new kernel implementation should be based solely on filename similarity or
assumed hardware relevance.

Audit output required before the first implementation

The source audit should produce a table in the following form:

Area	Vendor files/functions	Upstream equivalent	Classification	Required for first boot	Port strategy
XBurst2 CPU	TBD	TBD	ARCH	TBD	TBD
L1/L2 cache	TBD	TBD	ARCH	TBD	TBD
TLB	TBD	TBD	ARCH	TBD	TBD
SMP	TBD	TBD	ARCH	TBD	TBD
X2000 clocks	TBD	TBD	SOC	TBD	TBD
X2000 IRQ	TBD	TBD	SOC	TBD	TBD
X2000 OST	TBD	TBD	SOC	TBD	TBD
UART	TBD	TBD	DRIVER	TBD	TBD
MMC	TBD	TBD	DRIVER	TBD	TBD
Device tree	TBD	TBD	BOARD	TBD	TBD

TBD is intentional at this stage. The table is to be filled from direct
source evidence.

Current status

At creation of this audit:

* no new kernel code has been written on the new baseline branch;
* no build has been authorized or executed;
* no hardware deployment has been authorized or executed;
* no hardware state has been changed;
* the previous clean-port branch remains intact;
* the working vendor-based kernel on main remains the hardware-qualified
    reference.

The next operation is a read-only source audit.
