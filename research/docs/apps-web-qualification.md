# Managed apps and web reference qualification

License boundary: the existing records above the appended product-documentation
snapshots retain MIT. Appended snapshots are identified as
`AGPL-3.0-or-later`; the combined file is recorded as
`MIT AND AGPL-3.0-or-later` in `REUSE.toml`. Neither grant is withdrawn.

This records the offline, reference-X2000, and 2026.2.a candidate evidence moved from the current app interface document. The current interface and service contract remain in [docs/apps.md](../../docs/apps.md).

### Package and reference-X2000 validation

The local pinned Buildroot `2025.02.18`, commit
`d030e36bbc9669230c015be971b14b6e062cfdde`, defines Lighttpd `1.4.81`
(BSD-3-Clause). Only `BR2_PACKAGE_LIGHTTPD=y` and
`BR2_PACKAGE_LIGHTTPD_PCRE=y` are requested. PCRE selects PCRE2 for the routing
expression; the package also selects xxhash and libxcrypt on glibc. Optional
TLS, Lua, databases, compression and WebDAV features remain disabled.

The hash-checked upstream `1.4.81` source and Buildroot Meson definition were
inspected without building. `mod_proxy` is an unconditional dynamic module
with Buildroot's `-Dbuild_static=false`; `mod_setenv`, `mod_indexfile`,
`mod_staticfile`, and `mod_rewrite` are built into the executable. There is no Buildroot
`LIGHTTPD_PROXY` switch and no separate `mod_setenv.so` to require. Upstream
also compiles other standard modules, including CGI/FastCGI facilities; this
configuration does not activate them. No extra package patch is introduced
solely to remove unused upstream module code.

The pinned `src/mod_proxy.c` also implements `proxy.header` `map-urlpath` as a
prefix replacement on the request target. Although `mod_rewrite` is one of the
standard built-ins, the webcam route does not activate it; the already active
`mod_proxy` handles both routing and prefix stripping, with no new Buildroot
option. Host-side tests check the condition, loopback backend, prefix mapping,
unchanged Moonraker route/WebSocket block, and absence of a direct port-8080
listener declaration. A host-native Lighttpd binary was not available for an
additional `-tt` run.

The development RootFS was subsequently validated on the reference X2000 with
the persistent root active. It contained Lighttpd 1.4.81 as a 32-bit
little-endian MIPS32r2 PIE executable and the expected
`/usr/lib/lighttpd/mod_proxy.so`. Before frontend installation, S62 reported
`no-frontend`, with no Lighttpd process and no port-80 listener.

Because that development image carried `APP_REF=unpublished`, the repository
Fluidd handler was supplied explicitly through `FRE3NDER_APP_SOURCE_DIR`; its
local and transferred SHA256 identities matched. Installation produced a valid
payload with `index.html` and `release_info.json`, the expected Moonraker
fragment, desired-state marker, and active `fluidd` frontend selection.

After a controlled S62 restart, Lighttpd served Fluidd with HTTP 200 both on
loopback and over the reference LAN. Port 80 was listening on all IPv4
interfaces while Moonraker remained bound only to `127.0.0.1:17126`.
`/server/info` passed through the HTTP reverse proxy over the LAN after the
[Moonraker authorization configuration](../../docs/apps.md#platform-web-service)
was active. A real `/websocket` request returned HTTP 101 and carried Moonraker
JSON-RPC notifications,
including `notify_proc_stat_update`. When Moonraker was restarted, Lighttpd
temporarily reported the unavailable backend and automatically re-enabled it
after Moonraker returned.

The subsequently rebuilt and deployed camera integration was also qualified on
the investigated reference system. S61 seeded `fre3nder/camera.conf`, Moonraker
published the configured `fre3nder_camera`, and both
`/webcam/?action=snapshot` and the Fluidd live view traversed Lighttpd while
`mjpg_streamer` remained bound only to `127.0.0.1:8080`.

### Final-candidate restore and reboot result

The release-mode `2026.2.a` candidate was deployed with the authorized
system-persistence reset. The persistent Fluidd desired-state marker,
Moonraker fragment, and active frontend selection under `/home` survived while
the reconstructible `/opt/fre3nder/web/fluidd` payload was absent, causing the
expected `payload-unavailable` web-service state.

`fre3nder app status fluidd` reported `desired=installed`, a present compatible app
handler, a missing payload, and present Moonraker configuration/include state.
`fre3nder app restore fluidd` reconstructed the payload. After the documented web
and Moonraker restarts, Lighttpd returned HTTP 200, `/server/info` reported
ready Klippy state with no failed components or warnings, and the expected
qualified F005 MCU remained connected.

A subsequent authorized Fre3nder-to-Fre3nder reboot retained the Fluidd desired
state, handler, payload, and active frontend selection. The frontend again
returned HTTP 200 without another restore. This qualifies the explicit
system-overlay restore path and normal-reboot persistence on the investigated
reference system.

Subsequent testing on 2026-09-14 qualified normal printer status and control
through the Fluidd UI and the explicit `fre3nder app uninstall fluidd` path. The
resulting `web=no-frontend` state is expected after removing the selected
frontend and is not a service failure.


## Moonraker runtime qualification

### Preserved hardware evidence

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
and dependency baseline was built into the `2026.2.a` candidate tested on the
reference system. Final-candidate normal-reboot state retention and OverlayFS
baseline recovery are now hardware-qualified. Self-update, dependency
transition handling, and automatic post-update restart remain deferred beyond
`2026.2`.

## Moonraker 2026-09-14 documentation snapshot

This is a historical documentation snapshot from `docs/moonraker-bringup-current-state.md` at project
commit `a3a3cb263ab845a5590136545911b02306ada35b`. Statements and status labels describe that
recorded scope, not the current build or every hardware revision. The preserved
text remains `AGPL-3.0-or-later`; see `REUSE.toml`.

# Moonraker runtime and service contract

The reference-system qualification snapshot is dated 2026-09-14.

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
without migrating existing user configuration. Existing installations must add
the include manually. The signed Fluidd package does not create a Moonraker
updater fragment. A persistent fragment from the legacy installation is a
separate device-migration concern; its removal requires one S61 restart.
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
release-mode `2026.2.a` candidate qualified the complete recovery path on the
investigated reference system. An authorized system-overlay reset exposed the
RootFS-integrated Moonraker baseline while retaining `/home`; Moonraker started
from that baseline and returned to clean ready Klippy state. After the managed
Fluidd payload was explicitly restored, `/server/info` reported no failed
components or warnings. A subsequent Fre3nder-to-Fre3nder reboot retained the
persistent Moonraker configuration/state and returned to the same ready
runtime.

## Qualification record

The pinned Moonraker runtime, recovery, and reference-system service observations are preserved in [managed-app and web qualification](apps-web-qualification.md#moonraker-runtime-qualification). The current runtime contract is described above.
