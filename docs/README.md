# Fre3nder documentation

These documents describe the current Fre3nder contract for the supported
reference scope. Source, fixture, build and hardware qualification are distinct
states; a procedure or API description does not qualify a new artifact.

## Using Fre3nder

- [Configuration](configuration.md): settings, calibration and persistent files.
- [Applications](apps.md): install/update packages and select frontends.
- [Display](display.md): Fre3nderScreen, touch and the Factory-app contract.

## Administration / Operations

- [Installation](installation.md): operator staging and activation; the general
  consumer installer remains future work.
- [Updates](updates.md): the current explicit platform-update sequence.
- [Backup](backup.md): HOME/SYS backup roles and verified archives.
- [Networking](networking.md): Ethernet/WLAN, SSH, provisioning and web access.
- [Recovery](recovery.md): reachable-state decisions and return-path limits.
- [Storage](storage-layout.md): supported backends, system pairs and protected areas.

## Development

- [Development](development.md) and [build](build.md).
- [Buildroot maintenance](buildroot-maintenance.md).
- [Hardware contract](x2000-hardware-contract.md) and
  [open host architecture](x2000-open-host-architecture.md).
- [F005](f005.md) and [MCU switching](f005-mcu-switching.md).
- [Moonraker](moonraker.md).
- [Versioning](versioning.md), [roadmap](roadmap.md) and
  [licensing/provenance](licensing-and-provenance.md).
- [Local-device template](local-device.example.md): non-secret private notes only.

## API Reference

- [API overview](api/README.md): supported interfaces and ownership boundaries.
- [CLI](api/cli.md) and [runtime/integration](api/runtime.md).
- [Application package format](fre3app.md), [OTA contract](ota.md) and
  [backup contract](backup.md).

## Troubleshooting

Start with [symptoms and read-only diagnosis](troubleshooting.md), then follow
the responsible service contract or the bounded recovery path. Do not turn a
missing prerequisite into an automatic selector, filesystem or firmware write.

[Research](../research/README.md) indexes historical investigations and exact
qualification evidence. It is a separate evidence layer, not a prerequisite for
normal operation or productive builds/tests. [AGENTS.md](../AGENTS.md) defines
operator-controlled build and hardware actions.
