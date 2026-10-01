# Fre3nder research

`research/` is an active project layer, not a discard or archive directory.
It contains hardware analysis, reverse engineering, experiments, bring-up
work, historical development paths, and rejected alternatives.

Qualified results may be distilled into the productive Fre3nder tree. The
productive tree must not load, copy, source, or build from `research/`; links
from productive documentation to research are the only intended dependency.

Historical status labels such as `IN PROGRESS`, `Phase 2`, or `REQUIRES
QUALIFICATION` describe the state at the time of the document and must be read
in that context.

New hardware research starts here, including work on the display, touch,
camera, sensors, MCU protocols, bootloader, and other platform details.

## X2000 / Boot / Kernel

- [A/B bring-up](docs/x2000-ab-bringup-plan.md) and
  [nonpersistent boot investigation](docs/x2000-nonpersistent-boot-plan.md).
- [Kernel/DT feasibility](docs/x2000-kernel-dt-feasibility.md),
  [kernel-port audit](docs/x2000-kernel-port-audit.md) and
  [kernel-port plan](docs/x2000-kernel-port-plan.md).
- [Required kernel delta](docs/x2000-fre3nder-required-kernel-delta.md),
  [clean-port implementation](docs/x2000-clean-port-implementation-plan.md) and
  [patch workflow](docs/x2000-clean-port-patch-workflow.md).
- [Hardware/boot qualification snapshots](docs/x2000-hardware-qualification.md).
- [Vendor-baseline/RT23 history](x2000-kernel/vendor-baseline-port/README.md)
  and [Ingenic USB tool patch provenance](patches/ingenic-usbboot/README.md).

## Build / Toolchain

- [Build history and source-refresh audits](docs/x2000-build-history.md).
- [Toolchain audit](docs/x2000-toolchain-audit.md) and
  [prototype build](docs/x2000-prototype-build.md).
- [Lifecycle investigation](docs/x2000-lifecycle.md).

## Storage / Recovery

- [Stock storage/GPT/EXT_CSD investigation](docs/storage-layout.md).
- [System inventory](docs/system-inventory.md) and
  [evidence-producing SSH command log](docs/ssh-command-log.md).
- [Recovery analysis](docs/recovery-analysis.md),
  [recovery state/evidence](docs/recovery-current-state.md) and
  [validation record](docs/recovery-validation-plan.md).

## F005 / MCU

- [Reference hardware/print qualification](docs/f005-hardware-validation.md).
- [First-print reproduction](docs/f005-first-print-reproduction.md) and
  [host/config milestone](docs/f005-mainline-config-milestone.md).
- [Stock Klipper comparison](docs/klipper-stock.md) and
  [GD32F303 initial port study](docs/gd32f303-mainline-port.md).
- [Switching and host-handoff history](docs/f005-mcu-switching-history.md),
  [open MCU flasher](docs/f005-open-mcu-flasher.md) and
  [serial bootloader request](docs/f005-serial-bootloader-request.md).
- [Staged historical fixtures](configs/klipper-f005/stages/README.md).

## Apps / Web / Moonraker

- [Managed-app, web, proxy and Moonraker qualification](docs/apps-web-qualification.md).
  Its appended snapshot retains the old qualification pin; it is not the current
  build source of truth.

## Display / Touch

- [Display/Screen qualification and source/package boundaries](docs/display-qualification.md).
  Hardware bring-up, old standalone UI and Factory-app results remain separate
  scopes even when they share this file.

## Backup

- [Reference capture plan and complete recovery-set inventory](docs/backup-plan.md).
  This is distinct from the current HOME/SYS runtime backup capability.

## Project history

- [Roadmap, gates and phase history](docs/roadmap-history.md).

## Preserved documentation licenses and current contracts

Historical product-documentation snapshots retain `AGPL-3.0-or-later` through
specific `REUSE.toml` assignments. Existing MIT records with appended AGPL
snapshots identify the section boundary and have the combined expression
`MIT AND AGPL-3.0-or-later`. Moving a record does not withdraw its existing grant.

Current operational instructions and normative contracts remain in
[the documentation index](../docs/README.md). Read historical status labels,
dates, source commits, hashes, slots and hardware variants together; never
generalize a qualified record to different artifacts or releases.
