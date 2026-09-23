# Installing and updating Fre3nder

This is the current expert, host-side A/B deployment procedure. A guided
Stock-to-Fre3nder consumer installer is still [planned](roadmap.md). The
commands below describe the existing tools; a successful offline build or
preflight does not authorize a printer write. Persistent staging, selector
changes, and reboots require a separately authorized concrete operation under
[`AGENTS.md`](../AGENTS.md).

For a normal Kernel-and-RootFS `--write`, the active host must already run
Fre3nder with `/run/fre3nder-root/status` reporting `active`: after staging,
`deploy-x2000` arms the SYS reset on that runtime before selecting the new
slot. Its read-only preflight does not prove this later requirement. In
particular, this command is not a complete first-installation sequence from
Stock; a write run can stage the inactive pair before refusing the SYS reset.

The current Fre3nder runtime expects separately prepared external ext4
filesystems labelled `FRE3NDERSYS` and `FRE3NDERHOME`. Their roles and runtime
checks are in [storage layout](storage-layout.md). The repository does not yet
provide a general, qualified public procedure to create and verify those
backends for a first installation. This expert deployment procedure assumes
they have already been established; staging a host image does not prepare
them. A guided first-installation flow remains [roadmap work](roadmap.md#user-facing-installation-and-releases).

## Before staging

1. Establish the target's Point-of-Return and recovery material as described
   in [recovery](recovery.md). Check the actual active payload and selector;
   the names `STOCK_A` and `DEVELOP_B` label selector byte patterns, not the
   content of their slots.
2. Build and inspect the intended Kernel and RootFS pair as in
   [building Fre3nder](build.md). In
   `local/production/artifacts/x2000/full/build-manifest.json`, check
   `version`, `artifact_mode`, the Kernel and RootFS entries in `artifacts`,
   `component_provenance`, and `composition_provenance`. The combined manifest
   inherits its top-level `project_commit`, `project_worktree_status`, and, for
   development artifacts, `build_input_sha256` from the RootFS component.
   Use `component_provenance` to identify the Kernel and RootFS inputs and
   `composition_provenance` to identify the project state that performed the
   final assembly. `artifact_mode` is `release` or `development`: it describes
   build/provenance checks, not RootFS contents or access features.
   For `--compose-only` output, compare the Kernel and RootFS `artifact_mode`
   entries inside `component_provenance` explicitly; composition does not
   currently enforce their equality.
   The current manifest has no separate RootFS variant field. Use the recorded
   `rootfs.squashfs` hash, effective `buildroot.config`, and inspected RootFS
   contents to establish which system is being staged. Check the intended boot
   path and that the required network, SSH, diagnostic, and recovery access
   remain available. A change in RootFS contents is a functional change even
   if the slot and `artifact_mode` are unchanged.
3. Ensure non-interactive SSH access to the active `<printer-host>`. Before an
   authorized deployment reboot, check whether the persistent F005
   auto-transition opt-in is enabled. On an active Fre3nder runtime, this
   read-only check uses the same file, type, size, and content conditions as S60:

   ```sh
   ssh -o BatchMode=yes <printer-host> '
     if [ "$(cat /run/fre3nder-root/status 2>/dev/null)" != active ]; then
       echo F005_AUTO_TRANSITION=unknown
     else
       marker=/home/fre3nder/f005-auto-transition.enabled
       if [ -f "$marker" ] && [ ! -L "$marker" ] &&
          [ "$(wc -c < "$marker")" -eq 7 ] &&
          [ "$(cat "$marker")" = enabled ]; then
         echo F005_AUTO_TRANSITION=enabled
       else
         echo F005_AUTO_TRANSITION=disabled
       fi
     fi'
   ```

   If that persistent opt-in is enabled and the exact supported Stock MCU is
   detected after reboot, S60 can invoke the Stock-to-Fre3nder MCU transition.
   If Fre3nder HOME is not accessible from the running host, its opt-in state
   is unknown; do not infer that the file is absent or that a host deployment
   will leave the MCU untouched. Include a possible MCU transition in the
   concrete authorization. The exact gate and MCU limits are in
   [F005 switching](f005-mcu-switching.md#fre3nder-owned-mcu-lifecycle).
4. Run the read-only preflight from the repository root:

   ```sh
   scripts/deploy-x2000 <printer-host>
   ```

   For a development artifact, add `--develop` to the preflight. A normal
   deployment selects both Kernel and RootFS; `--all` is equivalent to the
   default. The tool verifies local `SHA256SUMS`, the build manifest, source
   identity, artifact size, the active A/B side, and inactive partition layout.
   It refuses a selector that does not point to the active slot.
   Read the printed plan and require the inactive target and selected pair to
   match the intended operation. The preflight makes no partition write,
   selector change, SYS reset, or reboot.

## Stage and activate a Fre3nder pair

Only within the explicitly authorized deployment sequence, run the same plan
with `--write`:

```sh
scripts/deploy-x2000 <printer-host> --write
```

For an authorized development artifact, use `--develop --write`. `--develop`
requires the stored X2000 build-input fingerprint to match the current
worktree and does not imply `--write`. Release artifacts retain the clean-tree
source gate.

The tool writes the selected pair only into the inactive p5/p7 or p6/p8 side,
performs complete artifact-length SHA-256 readback, and checks that the active
Kernel and RootFS did not change. For a normal Fre3nder deployment it then
marks SYS for the target-slot reset, selects the verified slot, reboots, and
validates the new active root, selector, and persistent-root runtime. A normal
successful result ends in `DEPLOY_X2000=PASS` and leaves the selector on the
newly active Fre3nder slot. Confirm that administrative access still works
through the intended network and SSH path.

A normal release deployment always stages Kernel and RootFS together.
`--kernel` or `--rootfs` alone is accepted only with `--develop`, for a
controlled component-development operation. Do not infer that the untouched
component was rebuilt or requalified by that operation. The exact partition
mapping and persistence roles are in [storage layout](storage-layout.md); the
update ownership and activation model are in [OTA architecture](ota.md).

If preflight refuses, resolve the reported mismatch before any write. If
staging or post-boot validation fails, keep the failure output and use the
[recovery decision path](recovery.md); do not assume a failed command left the
selector or partially written target in a usable state.

## F005 MCU firmware is separate

`deploy-x2000` does not itself install or update the F005; the persistent
auto-transition opt-in described above can affect the subsequent boot. The
current transitional
[`scripts/deploy-f005`](../scripts/deploy-f005) accepts an already running
Fre3nder B system with active persistent root and the historically named
`STOCK_A` fallback selector state. Its default invocation is read-only:

```sh
scripts/deploy-f005 <printer-host>
```

It checks the exact qualified release image, installed helpers, and MCU
identity. An authorized `--write` stages that image at
`/var/lib/fre3nder/firmware/f005/klipper-f005-mainline.bin` if needed and performs one existing open
Stock-to-Fre3nder transition only for an exact supported Stock MCU. An already
current Fre3nder MCU is not reflashed. The wrapper is fixture-confirmed; the
bounded underlying transition was separately qualified on the investigated
reference system. Read [F005 switching](f005-mcu-switching.md) before an MCU
operation. A newly built `build-f005` candidate is not automatically the
qualified deployment image.

## Stock-A staging and return

When Slot B is active and selected, the host tool can preflight a complete raw
Stock-A pair from `local/backup/stock/image/` or an explicitly supplied source
directory containing full-partition `p5.img`, `p7.img`, and `SHA256SUMS`:

```sh
scripts/deploy-x2000 <printer-host> --stock
```

An authorized `--stock --write` stages and verifies p5/p7 only. It does **not**
activate Stock, reboot, restore p9/p10, or switch the F005 MCU. Those are
separate steps in the [recovery decision path](recovery.md). Stock staging
cannot be combined with component selection or `--develop`.

## Qualification scope

The historical 2026-08-30 RootFS-only and full p6/p8 installation results,
including exact build IDs, byte counts, hashes, readback checks, and subsequent
runtime observations, are preserved in
[F005 reference hardware validation](f005-hardware-validation.md#2026-08-30-current-main-rootfs-installation-qualification).
Those results apply to the investigated reference system and historical
artifacts. They do not qualify a new artifact or a complete Stock return.
