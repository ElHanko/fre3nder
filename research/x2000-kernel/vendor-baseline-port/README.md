# Fre3nder X2000 vendor-baseline port

This directory documents how Fre3nder reduced the Ingenic X2000 Linux 6.6 vendor kernel delta to the subset currently required for the Creality Ender-3 V3 KE.

The purpose of preserving this work is to document the reasoning, provenance and reproducibility of the kernel reduction process.

It records which parts of the Ingenic vendor kernel were present, which parts were retained for the Ender-3 V3 KE, which parts were removed, and how the resulting Fre3nder kernel delta was derived.

* which parts of the Ingenic vendor kernel were present;
* which parts were required by the Ender-3 V3 KE;
* which parts could be removed;
* which printer-specific changes Fre3nder added afterwards;
* how the resulting kernel support can be expressed as a direct delta against the Linux RT baseline.

## Scope

The target of this work is specifically the Creality Ender-3 V3 KE based on the Ingenic X2000.

The filtering rule used during the reduction was:

* required by the Ender-3 V3 KE: keep;
* generic X2000 functionality not used by this printer: remove;
* support for unrelated Ingenic/X2000 boards and peripherals: remove;
* uncertain functionality that might still be required: keep until proven unnecessary.

The goal was not to create a generic Ingenic X2000 kernel.

The goal was to identify the smallest currently justified vendor-derived kernel support for the Ender-3 V3 KE while keeping the result reproducible and maintainable.

## Starting point

### Linux RT baseline

Repository:

`https://github.com/hexagon-geo-surv/linux-stable-rt`

Tag:

`v6.6.18-rt23`

Commit:

`fc3c8f4093aa9e32e67a51ba5eebd7338195b746`

Tree:

`16880e7cebe5db9273d0ad7fbac7f86fec2585b2`

### Ingenic vendor source

Repository:

`https://github.com/Llixuma/ingenic-linux-kernel6.6-x2000-v1.0-20250221`

SDK commit:

`a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b`

Vendor kernel tree:

`30cd72f68ffa1739f7f5b8d1158aad5f7d5a97f8`

The Ingenic kernel identifies itself as Linux `6.6.18-rt23`.

Because the vendor kernel and the selected RT baseline share the same Linux version, the vendor changes could be reconstructed as a direct tree-to-tree delta rather than treating the SDK kernel as an opaque independent source tree.

## Initial vendor delta

The initial comparison between the RT23 baseline and the Ingenic vendor kernel contained:

* 2,853 added paths
* 212 modified paths
* 14 deleted paths
* 3,079 changed paths total

This delta included considerably more code than the Ender-3 V3 KE actually requires.

The complete original vendor delta is preserved as:

`history/0001-ingenic-x2000-vendor-delta-v6.6.18-rt23.patch`

This patch reconstructs the Ingenic vendor kernel tree from the RT23 baseline.

It is retained for provenance and reproducibility and is no longer intended to be part of the productive Fre3nder kernel build path.

## Reduction process

The vendor delta was reduced in several explicit stages.

Each stage was kept separately so that the decisions remain reviewable and the complete reduction process can be reconstructed.

The historical chain is:

```text
Linux 6.6.18-rt23
  + Ingenic vendor delta
  + Sieve 1
  + Sieve 2
  + Sieve 3
  + Ender-3 V3 KE DTS
  + WLAN
  + Display
  + Touch
```

## Sieve 1: unrelated vendor device trees

The first reduction removed vendor-added device trees for unrelated Ingenic boards and platform variants.

Historical patch:

`history/0002-prune-unused-vendor-dts.patch`

Result:

* 86 files removed
* 18,276 semantic deletions
* resulting tree:
  `70240a8b33c471156106fbad5a22a3e3b5127a73`

After this reduction:

* the kernel still built successfully;
* the Ender-3 V3 KE DTB remained byte-identical.

This established that the removed board descriptions were not required for the target printer build.

## Sieve 2: unrelated vendor subsystems

The second reduction removed large vendor-added subsystems that were not used by the Fre3nder kernel configuration or by the hardware paths needed for the Ender-3 V3 KE.

Historical patch:

`history/0003-prune-unused-vendor-subsystems.patch`

Result:

* 2,233 vendor-added paths removed
* 9 Kconfig/Kbuild hook files adjusted
* resulting tree:
  `2255f2cd3048897a627f58ddf693c1f7249e444c`

A complete kernel build passed after this reduction.

The Ender-3 V3 KE DTB remained byte-identical.

## Sieve 3: Ender-3 V3 KE-specific reduction

The third reduction stopped treating generic X2000 support as sufficient reason to keep vendor code.

Instead, the remaining delta was evaluated against the actual Ender-3 V3 KE requirements.

Historical patch:

`history/0004-prune-ender3-v3-ke-vendor-delta.patch`

This step:

* removed 262 additional vendor-added paths;
* reverted 115 vendor modifications that were not required by the target;
* restored all 14 files that the vendor tree had deleted from the RT23 baseline.

Resulting vendor-only tree:

`b837270f06fae68e4721ff8b71ef74f475129434`

The remaining vendor delta after Sieve 3 was:

* 272 added paths
* 96 modified paths
* 0 deleted paths
* 368 changed paths total

Compared with the original 3,079 changed paths, approximately 88% of the vendor-changed paths had been eliminated.

This percentage describes changed paths, not semantic lines of code.

## Fre3nder printer integration

After reducing the vendor kernel support, the Fre3nder-specific Ender-3 V3 KE integration was applied.

The historical inputs are retained as:

* `history/ender3-v3-ke.dts`
* `history/ke-wlan.patch`
* `history/ke-display.patch`
* `history/ke-touch.patch`

These contain the printer-specific device tree and the WLAN, display and touchscreen integration used by Fre3nder.

The complete resulting source tree is:

`0163ea31f80116753af8de0bb7574247d34965c0`

Relative to the original RT23 baseline, this final tree contains:

* 275 added paths
* 98 modified paths
* 0 deleted paths
* 373 changed paths total

The difference between the 368-path Sieve-3 vendor delta and the 373-path final Fre3nder delta is caused by the Fre3nder-specific printer integration applied after the vendor reduction.

## Integration issues exposed by Sieve 3

The reduction also exposed two hidden dependencies in the earlier Fre3nder build path.

Both were useful findings because they identified places where the build still depended on unrelated vendor or reference-board state.

### Display patch context

Sieve 3 removed unused panel entries from:

`module_drivers/drivers/video/fbdev/ingenic/displays/Makefile`

The existing Fre3nder display patch had originally been created against the larger pre-Sieve-3 Makefile.

Its Makefile hunk therefore no longer applied after the pruning.

The actual Ender-3 V3 KE display change was still valid.

Only the patch context had become stale.

The display patch was rebased onto the reduced Makefile while keeping the actual Fre3nder display integration unchanged.

This was the first direct patch-context conflict caused by the pruning process.

### Halley5 defconfig dependency

The next kernel build exposed another dependency.

Fre3nder still initialized its kernel configuration through:

`x2000_halley5_v30_linux_defconfig`

Sieve 3 had removed this file because Halley5 is an Ingenic reference board and is not the Ender-3 V3 KE.

Instead of restoring that reference-board dependency, Fre3nder introduced its own kernel configuration baseline:

`configs/x2000/kernel-fre3nder.defconfig`

The productive configuration flow therefore became Fre3nder-owned instead of being based on an unrelated Ingenic board configuration.

The current configuration model is:

```text
kernel-fre3nder.defconfig
  + kernel.fragment
  + Fre3nder runtime build settings
  -> olddefconfig
  -> effective kernel configuration
```

## Successful Sieve-3 build

The final Sieve-3 source tree built successfully as:

`Linux-6.6.18-rt23-fre3nder`

Kernel payload:

`5,193,728 bytes`

Complete U-Boot uImage including its 64-byte header:

`5,193,792 bytes`

DTB size:

`29,083 bytes`

Sieve-3 artifact SHA256 values:

### kernel.uImage

`9c5f9066af3d8b0446b26c842452654e40d55ba859a6f06343831977a932c8b3`

### ender3-v3-ke.dtb

`efe233868ed8c612557c3363242cab19801afdbf3ffd0bb32fa3d6b8366efd4b`

### effective-kernel-config

`ff9fc80f3cbf3c87abb37a117f02514b5d99e745de9b8067d3bbf86e2e98ec12`

The Sieve-3 DTB is byte-identical to the Sieve-2 reference DTB.

The effective kernel configuration differed only in two relevant ways:

1. several unchanged symbols moved because the associated Kconfig menu structure had changed;
2. disabled symbols disappeared when the corresponding unused vendor drivers were removed.

No required active Ender-3 V3 KE kernel configuration was intentionally removed by this difference.

## Direct Fre3nder delta

After the historical chain had been reconstructed and validated, the complete resulting source tree was collapsed into one direct patch against the untouched RT23 baseline.

Productive patch:

`patches/kernel/0001-fre3nder-x2000-direct-delta-v6.6.18-rt23.patch`

SHA256:

`4fa9baebb56e2700defa77ddfe8eb5ef65a9fd551bc36ff1b3b1d81866c987ee`

The direct patch was independently applied to the RT23 baseline through a separate Git index.

The resulting tree was:

`0163ea31f80116753af8de0bb7574247d34965c0`

This exactly matched the tree produced by the complete historical transformation chain.

Therefore, at source-tree level, these transformations are equivalent:

```text
Linux 6.6.18-rt23
  + Ingenic vendor delta
  + Sieve 1
  + Sieve 2
  + Sieve 3
  + Ender-3 V3 KE DTS
  + WLAN
  + Display
  + Touch
```

and:

```text
Linux 6.6.18-rt23
  + Fre3nder direct X2000 delta
```

The productive Fre3nder kernel build can therefore use the direct delta without losing the source state established by the historical process.

## Why preserve the historical chain?

The direct patch is substantially easier to consume and maintain, but it does not explain how the result was obtained.

The historical files preserve that reasoning.

They provide:

* an exact reconstruction of the Ingenic vendor delta;
* a reproducible comparison against Linux `6.6.18-rt23`;
* staged removal of unrelated board support;
* staged removal of unused vendor subsystems;
* an Ender-3 V3 KE-specific filtering step;
* the printer-specific DTS, WLAN, display and touch integration;
* known Git tree identities after every major stage;
* evidence of dependencies exposed by the reduction process.

## Hardware qualification

The reduced direct-delta kernel was hardware-tested on the Fre3nder Ender-3 V3 KE.

The kernel-only A/B deployment wrote the new kernel to the secondary kernel
partition (`/dev/mmcblk0p6`) while leaving the existing Fre3nder root filesystem
on `/dev/mmcblk0p8` unchanged.

Deployment verification reported:

```text
KERNEL_P6=PASS
ROOTFS_P8=SKIPPED
SYSTEM_PERSISTENCE_RESET=SKIPPED
FINAL_ACTIVE_ROOT=/dev/mmcblk0p8
FINAL_SELECTOR=STOCK_A
DEPLOY_X2000=PASS
The deployed kernel booted successfully as:

Linux fre3nder 6.6.18-rt23-fre3nder #1 SMP PREEMPT Sat Sep 19 19:45:18 UTC 2026 mips GNU/Linux

The deployment process also verified that the Stock kernel and root filesystem
partitions remained unchanged and that the Fre3nder persistent-root runtime
contract remained valid.

This completes the Linux 6.6.18-rt23 vendor-baseline reduction phase.

## Next migration stage

This reduction solves a different problem from the final upstream port.

At this stage the source model is:

```text
Linux 6.6.18-rt23
  + reduced Fre3nder X2000 delta
```

The next migration stage is to determine which parts of that remaining delta are:

* already supported by upstream Linux;
* vendor implementations that can be replaced by upstream equivalents;
* actual missing X2000 support that still requires a patch;
* Ender-3 V3 KE-specific platform integration.

The immediate target after this historical reduction is therefore a clean port from the RT-based source onto plain upstream Linux `v6.6.18`, followed later by migration to a current 6.6.y kernel and eventually a newer LTS kernel.

## Qualification scope

The Git tree-equivalence checks documented here are source-level proofs.

The final Sieve-3 source tree was also successfully built through the historical chain.

The direct patch was independently proven to reproduce the exact same source tree.

These checks establish reproducibility of the source transformation.

They do not by themselves establish hardware behavior on every Ender-3 V3 KE hardware or firmware revision.

Hardware qualification remains a separate Fre3nder project gate.

## Licensing and provenance

The files in `history/` contain Linux-kernel-derived material and remain subject to the applicable Linux kernel licensing, currently recorded by Fre3nder as `GPL-2.0-only`.

The Fre3nder-authored research documentation in this directory is licensed according to the repository's `research/` licensing policy.

The relevant source provenance is deliberately retained so the kernel migration can be traced back to:

* the selected Linux RT baseline;
* the Ingenic vendor kernel;
* the individual reduction stages;
* the final Fre3nder direct delta.

See the repository `REUSE.toml` and licensing documentation for the authoritative file-level license assignments.
