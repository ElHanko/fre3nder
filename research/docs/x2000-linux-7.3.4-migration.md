# X2000 migration from Linux 6.6.162 to 7.3.4

Recorded on 2026-11-14 for the reference Ender-3 V3 KE. This is a migration
and qualification record, not a claim about every KE hardware revision or a
replacement for the deployment and recovery procedures.

## Source and build basis

The port moves the regular X2000 kernel from Linux stable `6.6.162`
(`5139929c698c273e07cb0635732f6a918a7b8e78`) to the exact kernel.org stable
source pinned in [`sources.json`](../../configs/x2000/sources.json):

| Identity | Value |
| --- | --- |
| Linux release | `7.3.4`, local version `-fre3nder` |
| Upstream commit | `7595a62d45ee1a2297eafa5f2ef5d0a45142d84d` |
| Upstream tree | `d07c331ebf5acbde9ebf9caea9eac6e33b07ad77` |
| Hardware-tested result tree, including diagnostics | `545677880c9413b3649e4db02e129645dd22925a` |
| Regular result tree, after removing test instrumentation | `8a84d48e9ca1424a9f9354570b281af0a9791902` |

At promotion, local `main` and `test/kernel-7.3-port` both pointed to
`746d9f7320b6761d322973f006717ea688ad5c1a`; neither branch was ahead. The
port was an uncommitted change in the test worktree. No merge or history
rewrite was required, and the test worktree was retained for review.

All five hardware patches remain in their established order:

1. `0001-x2000-platform.patch`: rebase the retained X2000 platform code onto
   7.3.4 and permanently fix the CPU-mask API usage described below.
2. `0002-x2000-display.patch`: retained unchanged.
3. `0003-x2000-touchscreen.patch`: refresh the upstream patch contexts.
4. `0004-x2000-wlan.patch`: retained unchanged.
5. `0005-x2000-board.patch`: retain board integration and the required 7.3
   API adaptations, including GPIO descriptors, driver lifetime/callbacks,
   serial-core FIFO handling and Device Tree build integration.

The Ingenic-derived platform code retains its provenance at
`a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b`. Display/touch integration retains
its NebulaOS/OpenKE provenance at
`88a0e1ecc6ace7c9e4ad99d6fa49e272180fd5a9`. These derived patches remain
GPL-2.0-only under the repository's path policy, with upstream notices
preserved; see [licensing and provenance](../../docs/licensing-and-provenance.md).
No third-party binaries or raw device logs are added by this migration.

The existing X2000 defconfig and Fre3nder configuration fragment already
provide the required functional options. SMP with two CPUs, PREEMPT,
ext4/JBD2, eMMC, SquashFS/OverlayFS and the KE drivers remain enabled. No
additional functional configuration change was needed. Buildroot
`2025.02.19`, GCC `13.4.0`, Binutils `2.43.1`, userspace package pins and the
separate kernel/userspace compiler contracts remain unchanged.

## First hardware failure

The first complete Fre3nder `2026.6.a` Development OTA booted from slot A
(`p5` kernel, `p7` immutable RootFS). At about 39 seconds, the eMMC
writeback worker `wb_workfn (flush-179:0)` faulted in
`ext4_mb_regular_allocator+0xe4/0x884`:

- EPC: `0x80281104`; RA: `0x80281074`.
- Bad virtual address: `0x00101320`.
- Fault instruction: `8ca40000`, `lw a0,0(a1)`.

The preserved ELF from that complete OTA matches the payload, function
size, offsets and all nine instruction words in the trace. The failing C
statement in that patched tree was the read of
`sbi->s_mb_last_groups[hash]` in `fs/ext4/mballoc.c:3044`. The build had no
DWARF line tables; this line association came from source/disassembly
comparison, not an `addr2line` source-line result.

The first trace was already tainted `W`, but the earlier WARN was missing
from the saved, incomplete boot log. The later `kernel/exit.c:913` warning
was `WARN_ON(tsk->plug)` after the worker died. The plain initial-console
warning does not explain WARN taint. No preceding eMMC I/O, ext4 or JBD2
error was present in the available excerpt.

`flush-179:0` identifies the shared eMMC backing device. It does not identify
SYS (`p9`) versus HOME (`p10`); the available registers do not resolve that
question. The operator subsequently observed Moonraker, the maintenance
watcher and `tail` waiting in `wait_transaction_locked`. Those later task
stacks were not part of the preserved dmesg file.

## Cause and permanent SMP fix

Linux changed `num_possible_cpus()` from a mask-weight calculation to a
cached count in upstream commit
[`35a5c37cb9f1`, cpumask: Cache num_possible_cpus()](https://github.com/torvalds/linux/commit/35a5c37cb9f1f947dff18e7cfc75a8cfcfd557ca).
The inherited XBurst-II `xburst2_smp_setup()` changed `cpu_possible_mask`
directly, bypassing that counter. Its attempt to clear CPU `NR_CPUS` also
did not clear the entire mask.

With `NR_CPUS=2`, the observed source path explains the failure:

1. `boot_cpu_init()` registers CPU 0 through the API: mask `{0}`, count 1.
2. XBurst-II setup directly sets CPU 1: mask `{0,1}`, cached count still 1.
3. MIPS `prefill_possible_map()` reads 1 and removes CPU 1 through
   `set_cpu_possible()`. The mask becomes `{0}`, but the count becomes 0.
4. The newer ext4 allocator sizes its global-goal table from
   `num_possible_cpus()`, producing zero entries and a zero-size allocation.

The ext4 table was introduced by
[`8f2c3b74865c`, ext4: utilize multiple global goals to reduce contention](https://github.com/torvalds/linux/commit/8f2c3b74865cac9b3bd87fb15633475b46069ca8).
The register values at the fault match this initialization exactly:
the divisor was 0 and the inferred table base was `0x10`, Linux's
`ZERO_SIZE_PTR`. The scaled index was `0x00101310`; adding it to `0x10`
produced the reported bad address. The existing MIPS compiler option
`-mno-check-zero-division` explains the absence of a preceding division
trap. A prior arbitrary memory corruption is unnecessary to explain this
specific fault.

The permanent fix in `0001-x2000-platform.patch`, file
`arch/mips/xburst2/core/smp.c`, initializes the masks through
`init_cpu_possible(cpumask_of(0))` and `init_cpu_present(cpumask_of(0))`,
then uses `set_cpu_possible(i, true)` and `set_cpu_present(i, true)` for
the remaining CPUs. The logical/physical CPU maps are unchanged.
The inspected online transitions already use `set_cpu_online()` and
needed no additional change. No ext4 clamp or allocator workaround was added.

## Corrected build and observed hardware results

The corrected kernel-only build passed the normal builder checks, including
patch/tree identity, effective configuration, board DTB, image format and
the 8-MiB limit. It used the same compiler binary as the failing build.
The corrected full OTA was subsequently composed from that kernel and the
unchanged RootFS of the first 7.3.4 OTA. Comparison of their recorded input
fingerprints showed only kernel patch/pin and diagnostic changes.

| Preserved artifact | SHA-256 |
| --- | --- |
| First complete OTA, which crashed | `14d5dd408d76fb5da636a6263c5f3ddcda03d0b35b16b1c8454ba9bb673db5a7` |
| Corrected kernel, 5947456 bytes | `50ceadecd2c8602fc508e8efbe5bbe7c02cd266bbee35659a003f4c0adfe601f` |
| Corrected complete OTA, 72171520 bytes | `c731c989b8ed5030de5ade7420460a131e7af2a41f92c56e843f1697a5cfcc77` |
| Shared immutable RootFS, 66195456 bytes | `1414c23a8d9fda9c5bac9d63d1966cf28342b1c11a93d5e75dbf862e632a5678` |

The corrected ELF Build ID is `72b52d8205d0dd416ab2bcd56a8dfb65fbf67535`.
Its build-input fingerprint is
`01076f80f21dbf8b212b8ef7657c1ea8b9222bfdf191b758f03db59a5abd3d7f`;
the original RootFS fingerprint is
`de84a23259a6a58416ba3a51447ccbd296d3a75276f6ff569d30e29d5e9802a7`.
These are separate component origins, not a claim that the RootFS was rebuilt
with the fix. The existing Composer retains general RootFS-build metadata;
the actual kernel is identified by its payload hash and
`component_provenance`, together with its preserved component manifest.

The corrected dmesg records confirm:

```text
after prefill_possible_map: possible=2 mask_weight=2 nr_cpu_ids=2
after SMP bring-up: online=2
```

They also show two CPUs brought online and SYS/HOME mounted read/write.
The operator reported 216 seconds of runtime without another Oops, an eMMC
cold start without a USB boot stick, and Fre3nderScreen and Klipper reaching
`ready` using the LAN access path. These are observations on the reference
system, not an exhaustive printer qualification or an endurance test.

The saved `dmesg-7.3.4-smp-fix-ke.log` and
`dmesg-7.3.4-smp-fix-ke-180s.log` have the same SHA-256:
`ef9ac63b877a1a949c42dfb910fbf075234c5c9a10372cc8bb992494de0982d3`.
They contain no new WARN/Oops. Their last emitted message is at about 68
seconds; the 216-second observation comes from the operator's runtime
check, not a fabricated later kernel timestamp.

## OTA state, manual return and WLAN limits

A follow-up OTA operation was temporarily blocked by an old persistent
activation record from the previous attempt. This was a retained OTA-state
problem, separate from package-signature validation and the SMP fix.
Do not interpret it as evidence that the corrected kernel failed to boot,
or assume that changing the selector automatically resolves pending OTA state.

The manual return to the known-good B pair with `6.6.162-fre3nder` also
needed a targeted SYS reset for `root=/dev/mmcblk0p8`. SYS is shared across
the immutable A/B pairs. A selector-only return can therefore retain an
unsuitable overlay even when the old kernel and RootFS are intact.
The targeted reset discards SYS `upper/` and `work/`; it preserves HOME
and does not format a partition. The established deployment/reset
contracts remain authoritative; see [OTA](../../docs/ota.md) and
[installation](../../docs/installation.md).

WLAN remains open for this port. SSH over WLAN initially worked, but later
HTTP and SSH became unavailable. A kernel regression was not demonstrated:
the available observations do not isolate the cause or provide a controlled
6.6/7.3 comparison of the outage. LAN results must not be presented as WLAN
qualification. No WLAN policy, firmware or provisioning change is included
in the promotion.

## Regular-path differences and review checks

The promoted source deliberately differs from the hardware-tested diagnostic
build in the following limited ways:

| Tested diagnostic build | Regular build inputs | Reason |
| --- | --- | --- |
| CPU-count printk immediately after `prefill_possible_map()` | Removed | The measurement established the invariant; it is not required for the fix. |
| Online-count printk in `smp_cpus_done()` | Removed | The normal SMP bring-up already reports the CPU count. |
| `CONFIG_LOG_BUF_SHIFT=18` test override | Existing `14` defconfig default retained | The larger buffer was for retaining the first warning during diagnosis; it is not a functional requirement. |
| Test-only TMPDIR logging changes in `scripts/build-x2000` | Existing regular wrapper retained | Temporary experiment-output isolation is not part of kernel enablement. |
| Test-only host TMPDIR mounts in `scripts/build-x2000-kernel` and `scripts/build-x2000-buildroot` | Existing regular wrappers retained | No dependency on a mandatory test TMPDIR is introduced. |

There are no other kernel-source differences from the tested result tree.
In particular, the complete XBurst-II SMP source containing the fix is
byte-identical to that tested tree. The changed result-tree and patch hashes
account for removal of the two printk blocks. The existing static kernel
test's three patch-digest expectations are updated accordingly.

The promotion checks used the pinned commit/tag and an isolated Git index:
all five SHA-256-verified patches passed ordered `git apply --cached --check`
and produced exactly the recorded regular result tree. The kernel-source
and patch-hash assertions from `tests/test-x2000-buildroot` passed in
isolation, and `git diff --check` passed. The test worktree, build artifacts
and hardware logs were left in place.

No new kernel/RootFS build, deployment or hardware test was run for this
source-only promotion. Consequently the artifact hashes and hardware
observations above qualify the instrumented test build, not a new binary
of the regular result tree. A regular build and its artifact checks remain
necessary before deploying that exact derivative.
