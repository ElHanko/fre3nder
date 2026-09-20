# X2000 kernel port plan

## Goal

Maintain the Ender-3 V3 KE / Ingenic X2000 kernel support as an explicit,
reviewable Fre3nder hardware delta on top of a normal kernel.org Linux
baseline.

The Ingenic SDK remains provenance and implementation reference material. It is
not a productive kernel source.

The migration deliberately preserved known-working Vendor behavior before
removing unrelated Vendor and RT baseline dependencies.

## Source and provenance baselines

### Ingenic Vendor source

The original public Ingenic SDK kernel reference is:

* repository:
  `https://github.com/Llixuma/ingenic-linux-kernel6.6-x2000-v1.0-20250221`
* commit:
  `a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b`
* Vendor kernel tree:
  `30cd72f68ffa1739f7f5b8d1158aad5f7d5a97f8`

The original Vendor delta and the successive pruning patches are retained as
historical and provenance material under:

`research/x2000-kernel/vendor-baseline-port/`

The complete original Vendor delta is:

`research/x2000-kernel/vendor-baseline-port/history/0001-ingenic-x2000-vendor-delta-v6.6.18-rt23.patch`

SHA256:

`c0da10973471db5b47d6af6151c65fe6025b46e15a9f22c221a47832fc582e73`

The original mechanical Vendor delta against the reconstructed RT23 baseline
contained:

* 2853 added paths
* 212 modified paths
* 14 deleted paths
* 3079 changed paths total

### Historical RT23 baseline

The first reconstructed non-SDK baseline used:

* repository:
  `https://github.com/hexagon-geo-surv/linux-stable-rt.git`
* tag:
  `v6.6.18-rt23`
* commit:
  `fc3c8f4093aa9e32e67a51ba5eebd7338195b746`
* tree:
  `16880e7cebe5db9273d0ad7fbac7f86fec2585b2`

This baseline was used to separate the Ingenic/X2000 hardware delta from the
complete Vendor kernel.

It is no longer the productive Fre3nder kernel baseline.

### Productive upstream baseline

The productive kernel now starts directly from the official stable Linux tree:

* repository:
  `https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git`
* tag:
  `v6.6.18`
* commit:
  `d8a27ea2c98685cdaa5fa66c809c7069a4ff394b`
* tree:
  `7dcc6dd2e2f286a81498146dab92bb4b847d2f12`

The canonical read-only Fre3nder reference is:

`local/research/x2000-kernel/linux-upstream`

## Phase 1: Vendor reduction on RT23

Phase 1 reconstructed the complete Ingenic Vendor tree on top of the public
RT23 baseline and then removed Vendor code not required by the Ender-3 V3 KE.

The reduction remained conservative and was hardware-qualified before moving
away from RT23.

The successive pruning history is retained under:

`research/x2000-kernel/vendor-baseline-port/history/`

After the three Vendor-pruning rounds and the Ender-3 V3 KE integration, the
final Phase-1 Fre3nder source tree was:

`0163ea31f80116753af8de0bb7574247d34965c0`

Its direct delta against the RT23 baseline contained:

* 275 added paths
* 98 modified paths
* 0 deleted paths
* 373 changed paths total

The Phase-1 kernel release was:

`6.6.18-rt23-fre3nder`

The Phase-1 kernel was successfully built and hardware-qualified on the
investigated Ender-3 V3 KE reference system.

The former productive RT23 direct patch is intentionally no longer retained
under `patches/kernel/`. Its source history is reconstructible from the
preserved research material above.

## Phase 2: plain upstream Linux v6.6.18

Phase 2 transplanted the complete Phase-1 Fre3nder hardware support from the
RT23 baseline onto plain upstream Linux `v6.6.18`.

The initial comparison found:

* 165 paths differing between RT23 and plain upstream;
* 373 paths in the Phase-1 Fre3nder delta;
* 41 paths overlapping both sets.

A three-way transplant automatically resolved 12 of the 41 overlapping paths
and left 29 conflicts.

Review of all 29 conflict files established that their Phase-1 RT23-to-Fre3nder
changes did not contain identifiable X2000 or Ender-3 V3 KE functionality.
They consisted of formatting, indentation, comments, or braces around existing
single statements.

The functional differences in those files belonged to the RT23 baseline
itself, including scheduler, futex, printk, softirq, timer, serial-core and
related RT infrastructure.

All 29 conflicts were therefore resolved to the canonical plain-upstream
content.

No functional Fre3nder/X2000 conflict required retaining RT23 code.

### Productive direct delta

The productive direct patch is:

`patches/kernel/0001-fre3nder-x2000-direct-delta-v6.6.18.patch`

SHA256:

`640e8e31c0006d165939781aa67e730b7f0ea8fc4910b400d53c2ed7083be91e`

Applied to the pinned upstream `v6.6.18` commit, it produces exactly:

`7895b886ea7720311150a8d2dbedf80ea1838ad8`

The productive delta against plain upstream contains:

* 275 added paths
* 69 modified paths
* 0 deleted paths
* 344 changed paths total

The reduction from the original 3079-path Vendor delta to 344 productive
plain-upstream delta paths describes the reduced source-change surface. It is
not a statement that the kernel contains 89 percent less code.

## Kernel configuration migration

The Phase-1 effective configuration contained 3233 explicitly recorded config
symbols.

Comparing the Phase-1 and Phase-2 source trees showed:

* Phase-1 Kconfig symbols: 20041
* Phase-2 Kconfig symbols: 20038
* symbols removed with RT23: 3
* symbols added by the move to plain upstream: 0

The removed symbols were:

* `HAVE_PREEMPT_AUTO`
* `PREEMPT_AUTO`
* `PREEMPT_BUILD_AUTO`

Only two of them were referenced by the stored Fre3nder configuration:

* `CONFIG_HAVE_PREEMPT_AUTO=y`
* `# CONFIG_PREEMPT_AUTO is not set`

Those two obsolete RT23-only lines were removed.

`CONFIG_PREEMPT_RT` itself remains a valid symbol in plain Linux `v6.6.18` and
is explicitly disabled.

The productive preemption configuration remains:

```text
CONFIG_PREEMPT=y
# CONFIG_PREEMPT_RT is not set
```

The productive kernel release is:

`6.6.18-fre3nder`

## Phase-2 build validation

Status: passed on 2026-09-19.

The authorized kernel-only development build completed successfully using the
official stable Linux `v6.6.18` baseline plus the productive Fre3nder direct
delta.

The build gates reported:

```text
build-manifest.json: OK
kernel.uImage: OK
ender3-v3-ke.dtb: OK
effective-kernel-config: OK
```

The resulting artifacts were:

### Kernel

File:

`kernel.uImage`

File size:

`5189696` bytes

uImage payload size:

`5189632` bytes

SHA256:

`c134d2e2a468954aef10a6d3b3d9c987d292f78152b0d521e3c7c0900d14e7b8`

Image identity:

```text
Linux-6.6.18-fre3nder
MIPS Linux Kernel Image
Load Address: 0x80f00000
Entry Point:  0x80f00000
```

### Ender-3 V3 KE Device Tree

File:

`ender3-v3-ke.dtb`

Size:

`29083` bytes

SHA256:

`efe233868ed8c612557c3363242cab19801afdbf3ffd0bb32fa3d6b8366efd4b`

The DTB is byte-identical to the hardware-qualified Phase-1 RT23 DTB.

### Effective kernel configuration

SHA256:

`e4357047c2a28a2a387ced9c0ee218d76bf018f99dd4aad4f28d7d6641e9ca9a`

### Build manifest

SHA256:

`50b3220228c56a948184aa39c5157dc9332c9142e1367dca5a87a6478adf5c11`

## Phase-2 hardware validation

Status: passed on 2026-09-19 on the investigated Ender-3 V3 KE reference
system.

Only the experimental Slot-B kernel partition p6 was rewritten. The existing
qualified p8 Fre3nder RootFS was deliberately retained.

The established deployment workflow verified:

* development artifact fingerprint: PASS
* kernel p6 write: PASS
* kernel p6 readback checksum: PASS
* Stock kernel p5 unchanged: PASS
* Stock RootFS p7 unchanged: PASS
* RootFS p8 rewrite: skipped
* system-persistence reset: skipped
* Fre3nder B boot: PASS
* persistent Fre3nder runtime on p8: PASS
* administrative network/SSH access after boot: PASS
* final active root: `/dev/mmcblk0p8`
* final boot selector: `STOCK_A`

The running kernel reported:

```text
Linux fre3nder 6.6.18-fre3nder #1 SMP PREEMPT Sat Sep 19 20:42:13 UTC 2026 mips GNU/Linux
```

This establishes that the RT23 kernel baseline is not required to build or boot
the current Fre3nder X2000 kernel or to run the already qualified Fre3nder
p8 host/runtime stack on the investigated reference system.

This result does not by itself claim that PREEMPT_RT could never provide value
for a different latency-sensitive workload. It establishes that Fre3nder does
not require RT23 as its kernel source baseline for the currently qualified
printer stack.

## Phase-2 productive kernel architecture

At the end of Phase 2, the productive kernel source relationship was:

```text
official stable Linux v6.6.18
        +
Fre3nder XBurst2 / X2000 / Ender-3 V3 KE delta
        |
        v
Linux 6.6.18-fre3nder
```

That phase established that neither the Ingenic SDK checkout nor the RT23
baseline was required as a productive kernel source. The Phase-2 direct patch
is retained as migration history; the current productive architecture is
described by the Phase-3 section below.

## Phase 3: maintained Linux 6.6.y

Phase 3 advanced the same hardware support from Linux `v6.6.18` to the
maintained Linux `v6.6.157` baseline.

The migration remained incremental:

1. pin the target official stable commit and tree;
2. transplant the already qualified Fre3nder hardware support;
3. identify concrete Stable/API/Kconfig conflicts;
4. adapt only those observed incompatibilities;
5. reproduce an exact expected source tree;
6. build through the normal Fre3nder kernel workflow;
7. hardware-qualify the resulting kernel through the established p6 test path.

After qualification, the initially collapsed direct delta was mechanically
split again by provenance without changing the resulting kernel source tree.

Migration to a newer suitable LTS kernel remains a later project phase.

Hardware deployment, partition writes and boot-selector changes remain separate
explicitly authorized operations.

## Current stable 6.6.y migration

Status: passed on 2026-09-20.

After the plain upstream `v6.6.18` port was built and qualified on the
reference Ender-3 V3 KE, the productive kernel baseline was advanced to current
Linux stable `v6.6.157`.

The pinned upstream reference is:

* repository:
  `https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git`
* tag:
  `v6.6.157`
* commit:
  `79643295eba17affbd16ca97f3ef04c90266b28c`
* tree:
  `e2963aecbdc92c10a52434a5ae11a82522dc38d5`

The productive Fre3nder kernel delta is stored as an ordered provenance
patch series:

1. Ingenic-derived X2000 platform support:

   `patches/kernel/0001-ingenic-x2000-platform-v6.6.157.patch`

   SHA256:

   `df0ab5b4f8041faf8aa715500dd9f3c4aa4c6e34360bdf03836c4a1487da072e`

2. NebulaOS/OpenKE-derived Ender-3 V3 KE display support:

   `patches/kernel/0002-ender3-v3-ke-display-v6.6.157.patch`

   SHA256:

   `50e4ff298bea856a91183482ef8ed4d6578c6860e50833986601d9072f9c6516`

3. NebulaOS/OpenKE-derived NS2009 touchscreen support:

   `patches/kernel/0003-ns2009-touch-v6.6.157.patch`

   SHA256:

   `121c9ed5f0123864c21077a7dfb207d9b1f366bb783df8dd18916eff0fa04ac5`

4. Ingenic-derived Ender-3 V3 KE WLAN integration:

   `patches/kernel/0004-ingenic-ender3-v3-ke-wlan-v6.6.157.patch`

   SHA256:

   `01a8a472de7235f06630e599ade5645aed9c803c0a2e7c516a97362eb2578085`

5. Fre3nder Ender-3 V3 KE board integration and `v6.6.157`
   forward-port fixes:

   `patches/kernel/0005-fre3nder-ender3-v3-ke-integration-v6.6.157.patch`

   SHA256:

   `08f9eb4bf44d69d7083253b2d75f102e440f20bd0ccb41fdbf011fcefe8f4b30`

The series is provenance-oriented rather than merely file-oriented. The
Ingenic-derived layers remain traceable to the public Ingenic X2000 source,
the display and touch layers remain traceable to the NebulaOS/OpenKE source,
and Fre3nder-specific board integration and Stable forward-port work remain
separate.

Applying the complete ordered series to the pinned `v6.6.157` baseline
produces exactly:

`40d8b5cee4341505c12373e9bb1386e80241f0d6`

This is the same source tree that was built and hardware-qualified before the
mechanical patch-series split. The split therefore changes provenance and
maintenance structure, not kernel source content.

The resulting kernel release is:

`6.6.157-fre3nder`

The migration retained the existing Ender-3 V3 KE hardware support while
adapting the remaining out-of-tree X2000 delta to Stable changes between
`v6.6.18` and `v6.6.157`.

Required porting changes were limited to concrete observed incompatibilities:

* adapt the OF `of_property_for_each_u32()` iterator users to the current
  three-argument API;
* adapt the Ingenic pinctrl GPIO direction helpers from global GPIO numbering to
  the current `gpio_chip` plus offset API;
* remove a Stable-added DWC2 `PCGCTL` wakeup sequence that conflicted with the
  already qualified Fre3nder DWC2 delta where that register path is intentionally
  absent;
* repair two missing closing braces introduced while resolving the overlapping
  Stable/Fre3nder SDHCI changes;
* remove three obsolete Kconfig entries that no longer exist in the
  `v6.6.157` configuration space.

The managed kernel cache checkout was also changed to use a forced detached
checkout before reset and clean. This allows a previously patched managed cache
to transition reproducibly between pinned kernel baselines without requiring
manual cache removal.

### Build validation

The final kernel-only development build completed successfully.

Qualified artifacts:

* `kernel.uImage`
  SHA256:
  `485194f9d95168afcbc1da69eaf505354f1884c01010eaa5f388054d180e6258`
* `ender3-v3-ke.dtb`
  SHA256:
  `efe233868ed8c612557c3363242cab19801afdbf3ffd0bb32fa3d6b8366efd4b`
* `effective-kernel-config`
  SHA256:
  `93f7d6c3799c5707b9f24dda6909d7dfab6c91b8fa8b36b0531a85a59c0b667b`
* `build-manifest.json`
  SHA256:
  `c6d64d8b42bc7c98662c96156a04c09270cf64a335db450f9f4d67ad626bb136`

The generated uImage identifies itself as `Linux-6.6.157-fre3nder`, uses the
established MIPS load and entry address `0x80f00000`, and remains below the p6
kernel-slot size limit.

The Ender-3 V3 KE DTB remains byte-identical to the already qualified
`v6.6.18-fre3nder` DTB.

### Hardware qualification

The final `6.6.157-fre3nder` kernel was deployed to kernel slot p6 using the
established kernel-only A/B deployment procedure.

Deployment validation established:

* the p6 kernel write completed and exact artifact readback passed;
* stock kernel slot p5 remained unchanged;
* stock RootFS slot p7 remained unchanged;
* existing Fre3nder RootFS slot p8 was not rewritten;
* the reference printer booted successfully from p6 + p8;
* the existing Fre3nder runtime reached normal operation;
* network and SSH access remained available;
* the boot selector was restored to `STOCK_A` after qualification.

The runtime kernel identified itself as:

`Linux fre3nder 6.6.157-fre3nder #1 SMP PREEMPT Sat Sep 19 22:06:01 UTC 2026 mips GNU/Linux`

This demonstrates on the reference system that the Fre3nder X2000 hardware
delta is no longer technically tied to Linux `v6.6.18` or the earlier
Vendor/RT23 baseline.

The qualification establishes bootability and operation of the existing
Fre3nder p8 runtime, including the validated network and SSH access path. It
does not by itself establish equivalence for every possible peripheral,
workload, latency characteristic, or hardware revision.

Future 6.6.y updates should therefore follow the same incremental process:

upstream baseline update → ordered provenance-series apply/port → Kconfig and
API validation → kernel build → targeted hardware qualification.
