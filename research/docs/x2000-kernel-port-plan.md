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

## Productive kernel architecture

The productive kernel source relationship is now:

```text
official stable Linux v6.6.18
        +
Fre3nder XBurst2 / X2000 / Ender-3 V3 KE delta
        |
        v
Linux 6.6.18-fre3nder
```

The productive kernel workflow:

1. fetches the pinned official stable Linux `v6.6.18` source;
2. verifies its commit and tree;
3. verifies the Fre3nder direct-patch SHA256;
4. verifies that the patch produces the exact expected source tree;
5. applies the patch;
6. applies the reproducible Fre3nder kernel configuration;
7. builds the normal Fre3nder kernel artifacts.

The Ingenic SDK and the RT23 baseline are now migration history and provenance,
not productive kernel dependencies.

## Phase 3: maintained Linux 6.6.y

The next kernel migration phase is to move the same known-working Fre3nder
hardware support from Linux `v6.6.18` to a current maintained Linux `6.6.y`
baseline.

The migration should remain incremental:

1. select and pin the target stable `6.6.y` commit;
2. compare the current 344-path Fre3nder delta against that source;
3. identify support that newer upstream Linux already contains or supersedes;
4. adapt only genuine conflicts;
5. avoid unrelated redesign during the initial transplant;
6. reproduce the expected source tree exactly;
7. build the kernel through the productive workflow;
8. hardware-qualify the resulting kernel through the established p6 test path.

Cleanup and replacement of remaining Vendor-derived implementations can continue
after a working maintained-6.6.y baseline is established.

Migration to a newer suitable LTS kernel remains a later project phase.

Hardware deployment, partition writes and boot-selector changes remain separate
explicitly authorized operations.
