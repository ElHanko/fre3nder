# Moonraker runtime and service contract

## Current architecture

Each Fre3nder platform release is designed to carry a pinned Moonraker
source baseline and its matching runtime directly in the immutable SquashFS RootFS:

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

The canonical build pin is `userspace.moonraker.commit` in
[sources.json](../configs/x2000/sources.json), currently
`9e676eba6b02661a4dfa3ec6e7ac3f3504498e6d`. Build/test consumers read it through
`scripts/source-value userspace.moonraker.commit`. Public upstream is
`https://github.com/Arksine/moonraker.git`, GPL-3.0-only.

The RootFS retains a valid Git checkout at `/opt/fre3nder/moonraker` and a
PEP-405 environment at `/opt/fre3nder/moonraker-env`, with system site packages
enabled. Native modules belong to Buildroot; hash-pinned pure-Python wheels
are recorded in [the wheel manifest](../configs/x2000/moonraker-python-wheels.json).
Boot performs no dependency installation. S61 launches the environment Python
and exports `PIP_ONLY_BINARY=:all:` so updates cannot compile native modules
on the printer. Git and TLS-capable libcurl are RootFS dependencies.

## Service contract

S40 configures loopback as `127.0.0.1/8`. S60 starts Klippy with:

```text
-a /run/fre3nder-klipper/klippy.sock
```

S60 reports `active` only when the expected Klippy process is alive, its
identity matches, and that path is a real Unix socket. Its bounded readiness
failure states are `startup-timeout` and `startup-failed`. Qualification is limited to the recorded reference artifacts.

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

The default uses `provider: none`, `[update_manager] channel: stable` and
`enable_system_updates: False`. Moonraker owns its application source/environment
only; Kernel, RootFS, base Klipper, A/B state, F005 and system packages remain
Fre3nder-owned. A Git checkout/environment does not establish a qualified
self-update lifecycle. Dependency transitions and BusyBox/S61 restart handling
still need explicit implementation/qualification within that ownership boundary.

The default includes `[include fre3nder/*.conf]`. S61 provides the fragment
directory and app-neutral `00-base.conf`. Existing user configuration is retained
and needs the include added manually if absent. Signed Fluidd packages do not
create a Moonraker updater fragment; legacy migration is separate.

## Authorization and HTTP access

Moonraker listens on `127.0.0.1:17126`. The platform
[HTTP proxy](api/runtime.md#http-routing) exposes the documented Moonraker and
WebSocket routes. Moonraker owns authorization; Lighttpd discards client-supplied
identity headers before supplying the actual connection address.

Fre3nder 2026.4 deliberately accepts the upstream
[authorization change](https://github.com/Arksine/moonraker/commit/fbfe3482c32c934b34cbe00d04c0a29f3abb0291):
an already trusted connection retains authorization after a failed credential
attempt. With API-key authentication enabled, an invalid nonblank API key remains
invalid and an untrusted client gains no trusted authorization. Existing
`trusted_clients` remain the trust boundary. No Fre3nder configuration change
was required. Fre3nder does not disable `enable_api_key` or force `force_logins`.
This contract makes no general safety claim about arbitrary LAN clients.

## Recovery contract

A SYS-overlay reset exposes the immutable RootFS Moonraker source/environment
again. HOME retains configuration, database, logs and G-code. Normal reboot
retains those user files; missing defaults are seeded without replacing existing
configuration. An invalid immutable baseline fails closed as `baseline-invalid`;
startup does not download or repair it.

The current pin has no new build/hardware qualification from the source refresh.
The older qualified baseline and dated service/proxy/recovery observations remain
in [the historical qualification](../research/docs/apps-web-qualification.md#moonraker-2026-09-14-documentation-snapshot).
