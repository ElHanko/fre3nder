# Moonraker runtime bring-up — current state

Status date: 2026-09-11

## Current architecture

Each Fre3nder platform release is designed to carry a pinned stable Moonraker
baseline and its matching runtime directly in the immutable SquashFS RootFS:

```text
/rom
├── /opt/fre3nder/moonraker/       pinned upstream Git checkout
├── /opt/fre3nder/moonraker-env/   Python virtual environment
├── S61fre3nder-moonraker
└── Fre3nder integration

writable system OverlayFS upper
└── later Moonraker source and environment updates

/home/fre3nder/printer_data/
└── configuration, database, logs, G-code, and user state

/run/fre3nder-moonraker/
└── volatile PID, status, and Unix socket
```

Moonraker is not a separately installed Fre3nder managed-app payload. It has no
versioned `/opt/fre3nder/apps` hierarchy, `active-version` record, resolver, or
app-only build artifact. OverlayFS already provides the required separation
between a recoverable RootFS baseline and later writable application changes.

## Baseline and dependency construction

The baseline is the public upstream repository
`https://github.com/Arksine/moonraker.git`, pinned to the hardware-qualified
commit `985c1d0bbeb90bc057d34a232c9dc3b05e0c6c8d` (tag `v0.11.0`,
GPL-3.0-only).

The build stages the pinned checkout, including its `.git` identity, at
`/opt/fre3nder/moonraker`. Transient clone records are discarded and the index
is rebuilt from the pinned HEAD. The retained origin, refs, objects, and exact
HEAD make this a valid Git repository that the pinned Moonraker update manager
detects as its own `git_repo` source.

The immutable RootFS supplies native and Buildroot-compatible Python modules.
Hash-pinned pure-Python wheels are unpacked off-device into:

```text
/opt/fre3nder/moonraker-env/lib/python3.12/site-packages/
```

`moonraker-env` is a PEP 405 environment with `pyvenv.cfg`, `bin/activate`,
`bin/python`, and `bin/pip`. It uses `include-system-site-packages = true`, so
native modules remain owned by the RootFS while pure-Python packages can live
in the Moonraker environment. S61 launches the environment's Python directly.

The reference X2000 has about 244 MiB RAM and no swap. Target-side Pillow and
PyYAML source builds were previously killed under memory pressure. Normal boot
therefore performs no dependency installation, and S61 exports
`PIP_ONLY_BINARY=:all:` so a later updater cannot compile native Python source
on the printer. A future dependency transition without compatible wheels or
Buildroot packages must fail or be handled in a later platform release; that
lifecycle still requires qualification.

Git and TLS-capable libcurl are RootFS dependencies because Moonraker's updater
requires a functional HTTPS Git remote. System package updates are disabled in
Moonraker configuration.

## Service contract

S40 configures loopback as `127.0.0.1/8`. S60 starts Klippy with:

```text
-a /run/fre3nder-klipper/klippy.sock
```

S60 reports `active` only when the expected Klippy process is alive, its
identity matches, and that path is a real Unix socket. Its bounded readiness
failure states are `startup-timeout` and `startup-failed`. This contract and a
natural boot without the former S60/S61 race are qualified on the investigated
reference system.

S61 requires the active persistent root, active Klipper plus its UDS, a valid
fixed Moonraker baseline, its Python environment, and valid persistent printer
data. It creates a default configuration only when none exists and never
overwrites user configuration. It launches:

```text
/opt/fre3nder/moonraker-env/bin/python
    /opt/fre3nder/moonraker/moonraker/moonraker.py
    -d /home/fre3nder/printer_data
    -c /home/fre3nder/printer_data/config/moonraker.conf
    -l /home/fre3nder/printer_data/logs/moonraker.log
    -u /run/fre3nder-moonraker/moonraker.sock
```

The PID and exact command identity gate stop/restart operations. If the fixed
RootFS baseline or environment is absent, S61 reports `baseline-invalid` and
does not attempt installation or repair.

## Update ownership and current updater limit

The seeded configuration includes:

```ini
[update_manager]
channel: stable
enable_system_updates: False
```

At the pinned revision, Moonraker discovers its source from the executing
package path, requires a real Git repository and virtual environment, reads
`scripts/moonraker-requirements.txt`, and uses stable tags for the `stable`
channel. The RootFS layout prepares these prerequisites.

Fre3nder Klipper remains at `/usr/share/klipper` without `.git`. Moonraker's
automatic Klipper detection consequently classifies it as `none` and retains a
non-updateable base entry rather than a Git deployer. Moonraker system updates
are disabled. Kernel, RootFS, Klipper, A/B state, F005 firmware, and system
packages remain exclusively Fre3nder-owned.

The default now also contains `[include fre3nder/*.conf]`. The current S61
preparation supplies the fragment directory and app-neutral `00-base.conf`,
without migrating existing user configuration. The repository-only
[Fluidd app handler](apps.md) owns `fre3nder/fluidd.conf` and bootstraps its web
payload outside the RootFS. Existing installations must add the include
manually. Fragment changes report the existing S61 restart command.
Optional frontend-neutral Lighttpd/S62 infrastructure is now offline
implemented above the loopback-only Moonraker API. It proxies HTTP/WebSocket
without taking ownership of application updates. On the reference X2000,
Moonraker remained bound only to `127.0.0.1:17126` while Lighttpd exposed port
80. HTTP `/server/info` and a real Moonraker JSON-RPC WebSocket were validated
through that proxy over the LAN. Lighttpd also recovered backend availability
after a controlled Moonraker restart. See the app documentation for the
detailed evidence, routes, authorization ownership, opt-out, and remaining
qualification.

Self-update is not a `2026.2` acceptance criterion. With `provider: none`, the
pinned machine component's base provider raises `Service Actions Not
Available`. After a successful Git update, `GitDeploy.update()` asks
`restart_service()` to restart Moonraker; that schedules
`machine.restart_moonraker_service()`, whose asynchronous wrapper catches and
suppresses the provider failure. Source and Python-package changes could
therefore be written to the system OverlayFS without an automatic S61 restart.

A future self-update implementation must solve the dependency transition and
BusyBox/S61 post-update restart within the existing ownership boundary. It
must not gain ownership of the Fre3nder platform, boot slots, base Klipper, or
MCU firmware. This lifecycle is deferred beyond `2026.2`.

## Recovery contract

The platform recovery behavior is:

```text
SquashFS:             qualified Moonraker stable X
normal operation:     code/environment remain at the qualified baseline
normal reboot:        persistent config/state under /home remain visible
system-overlay reset: upper/work are recreated; RootFS stable X is visible again
/home reset effect:   none; printer_data remains retained
```

This replaces the discarded multi-version/`active-version` mechanism. The
system-overlay reset itself and retention of `/home` are hardware-qualified;
the RootFS-integrated Moonraker baseline was subsequently built and deployed
through the Stage-D RootFS path. Normal-reboot state retention and recovery of
that baseline after a system-overlay reset still require qualification with the
final `2026.2` candidate.

## Preserved hardware evidence

The architecture change does not invalidate the existing reference-hardware
results for the same pinned Moonraker version and dependency set:

- real Moonraker startup with persistent configuration under `/home` and a UDS
  under `/run`;
- connection to `/run/fre3nder-klipper/klippy.sock` with
  `klippy_connected=True` and `klippy_state=ready`;
- `/printer/info` reporting ready;
- working local HTTP API and network discovery; and
- S60 readiness plus natural boot without the observed startup race.

These results qualify the runtime and service behavior. The same pinned source
and dependency baseline was subsequently built and deployed through the Stage-D
RootFS path. Final-candidate normal-reboot state retention and OverlayFS
recovery remain open; self-update and post-update restart are deferred beyond
`2026.2`.
