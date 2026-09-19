# X2000 kernel port plan

## Goal

Replace the productive Ingenic SDK kernel checkout with a reproducible Linux
baseline plus an explicit, reviewable Ingenic hardware delta.

The migration deliberately preserves the known-working Vendor behavior first.
Reduction and upstream cleanup happen only from a verified baseline.

## Established baseline

Fre3nder 2026.2 used the public Ingenic SDK kernel from:

- repository:
  `https://github.com/Llixuma/ingenic-linux-kernel6.6-x2000-v1.0-20250221`
- commit:
  `a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b`
- Vendor kernel tree:
  `30cd72f68ffa1739f7f5b8d1158aad5f7d5a97f8`

The reconstructed baseline starts from public Linux RT:

- repository:
  `https://github.com/hexagon-geo-surv/linux-stable-rt.git`
- tag:
  `v6.6.18-rt23`
- commit:
  `fc3c8f4093aa9e32e67a51ba5eebd7338195b746`
- tree:
  `16880e7cebe5db9273d0ad7fbac7f86fec2585b2`

The complete Ingenic delta is stored as:

`patches/kernel/0001-ingenic-x2000-vendor-delta-v6.6.18-rt23.patch`

SHA256:

`c0da10973471db5b47d6af6151c65fe6025b46e15a9f22c221a47832fc582e73`

Mechanical delta:

- 2853 added paths
- 212 modified paths
- 14 deleted paths
- 0 type changes
- 3079 changed paths total

Applying the complete delta to the pinned RT23 baseline produces exactly:

`30cd72f68ffa1739f7f5b8d1158aad5f7d5a97f8`

Applying the Fre3nder 2026.2 Ender-3 V3 KE layer afterwards produces exactly:

`507fd25ccb3cbd4f737ffb0a0e1357c0921ae34e`

The complete Vendor patch intentionally preserves the original Vendor source,
including its whitespace. It must not be reformatted while it serves as the
exact reconstruction baseline.

## Productive baseline port

The productive X2000 kernel workflow now:

1. fetches the pinned public `v6.6.18-rt23` baseline;
2. verifies the baseline commit and tree;
3. verifies the complete Ingenic delta SHA256;
4. verifies that the delta produces the exact known Vendor tree;
5. applies the complete Ingenic delta;
6. applies the existing Fre3nder Ender-3 V3 KE layer;
7. configures and builds through the normal productive kernel workflow.

The productive build no longer requires the Ingenic SDK checkout as its kernel
source. The SDK remains provenance and reference material for the Vendor delta.

## Kernel identity

The reconstructed productive kernel uses:

`CONFIG_LOCALVERSION="-fre3nder"`

with:

`# CONFIG_LOCALVERSION_AUTO is not set`

Kbuild is invoked with an explicit empty `LOCALVERSION` environment value so the
intentionally modified Git worktree does not append an unwanted `-dirty` suffix.

The resulting kernel release is:

`6.6.18-rt23-fre3nder`

This intentionally changes the kernel version string and effective kernel config
relative to the original Fre3nder 2026.2 Vendor build.

## Baseline validation gate

Status: passed on 2026-09-19.

Validation established:

- productive kernel-only development build completed successfully;
- kernel release is `6.6.18-rt23-fre3nder`;
- kernel image is a MIPS Linux Kernel Image with load and entry address
  `0x80f00000`;
- kernel image payload size is 5193728 bytes;
- Ender-3 V3 KE DTB is byte-identical to the qualified Fre3nder 2026.2 Vendor
  reference;
- DTB SHA256 is
  `efe233868ed8c612557c3363242cab19801afdbf3ffd0bb32fa3d6b8366efd4b`;
- effective kernel config differs from the Fre3nder 2026.2 Vendor reference only
  by the intentional `CONFIG_LOCALVERSION="-fre3nder"` setting;
- the complete Vendor delta still reconstructs exactly
  `30cd72f68ffa1739f7f5b8d1158aad5f7d5a97f8`;
- the complete prepared Fre3nder source still reconstructs exactly
  `507fd25ccb3cbd4f737ffb0a0e1357c0921ae34e`;
- no hardware deployment was performed as part of this validation.

## Next phase: conservative Vendor-delta reduction

After the reconstructed baseline is committed, reduce the complete Vendor delta
while remaining on the RT23 baseline.

The complete 3079-path Vendor patch remains the immutable reference.

Initial reduction is conservative and based on actual Fre3nder build
reachability:

- keep compiled source;
- keep headers referenced by compiled objects;
- keep active DTS and DTSI dependencies;
- keep active Kconfig, Makefile, linker, architecture, and common
  infrastructure;
- classify unrelated SoCs, reference boards, demos, tests, disabled drivers, and
  clearly unused subsystems as removal candidates;
- retain uncertain indirect dependencies until they are understood.

Do not initially prune inactive preprocessor branches inside otherwise required
source files.

Each meaningful reduction should remain separately reviewable and should be
validated against the known-working reconstructed RT23 baseline before further
reduction.

## Plain upstream migration

Once the reduced RT23 hardware delta is stable, transplant the remaining
complete required hardware support onto the canonical plain upstream Linux
`v6.6.18` reference:

- commit:
  `d8a27ea2c98685cdaa5fa66c809c7069a4ff394b`

For each Vendor-modified path:

- apply directly where upstream and RT23 baseline content are equivalent;
- identify genuine RT-versus-upstream conflicts;
- adapt only those conflicts;
- do not combine the initial upstream transplant with unrelated redesign or
  cleanup.

The first plain-upstream target is completeness and bootability, not minimality.

PREEMPT_RT is treated separately from X2000 hardware enablement.

## Later cleanup

After a complete plain `v6.6.18` X2000 kernel is functional:

- remove remaining unused Vendor infrastructure incrementally;
- replace Vendor-specific implementations with upstream or established community
  equivalents where appropriate;
- remove unrelated SoC and reference-board support;
- simplify configuration and source layout;
- advance from `v6.6.18` to a suitable maintained 6.6.y or later LTS baseline.

Hardware deployment, boot testing, partition writes, and other persistent
printer changes remain separate explicitly authorized gates.
