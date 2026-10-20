# Installable applications and frontends

The signed `.fre3app` package core is implemented in the platform. The recorded
Development Fre3nderScreen Factory-app path is qualified on the investigated
reference system; that does not qualify another package or release binary.
Fluidd's signed-package migration has no hardware qualification from its earlier
Legacy-app/web result. Exact scopes remain in [display](display.md#configuration-and-qualification-boundary)
and [web qualification](../research/docs/apps-web-qualification.md).
Use the [CLI reference](api/cli.md) for complete syntax, rights and output limits.

## Package lifecycle

`/usr/libexec/fre3nder/package-core` verifies Ed25519 signatures and file hashes
before installing a package. The `fre3nder` CLI exposes:

```text
fre3nder app verify <package.fre3app>
fre3nder app install <package.fre3app> [--storage sys|home]
fre3nder app update <package.fre3app> [--allow-downgrade]
fre3nder app remove <app>
fre3nder app list
fre3nder app status <app>
fre3nder app display {list|status|disable}
fre3nder app display select <app>
fre3nder app key {list|show|add|remove} ...
```

The exact verified package is cached in root-managed persistent state under
`/home/.fre3nder/packages/<app>/package.fre3app`. S58 verifies that copy again,
reconstructs missing SYS runtimes, and calls the unprivileged service's
`restore` action after a system-overlay reset. Valid HOME runtimes are retained.
Recovery needs neither a network download nor a web-service restart. S65 starts
packages marked for autostart.
See [the package format](fre3app.md) for its trust and service
contract.

## Image system applications

Official signed packages placed by the image build under
`/usr/share/fre3nder/system-apps/<name>.fre3app` are **required system apps**.
This directory is RootFS-owned; a manifest cannot grant itself system status.
At boot, `S58fre3nder-system-apps` runs *after* signed-cache recovery and
*before* services start. `package-core reconcile-system-apps` verifies each
seed against the built-in official Ed25519 publisher key and checks its exact
filename. It installs missing apps, updates only packages with a greater
`release_serial`, and otherwise retains the installed version. Development
serial zero has no ordering. No network access, downgrade or service start
occurs during reconciliation. Ordinary manual updates remain supported.

System role is persisted in root-controlled app metadata, survives SYS reset,
image/OTA rollback and an image no longer listing the app, and cannot be
relinquished by a manual package update. Removing a system app is denied by
Package-Core even when called directly, including through Maintenance. The
Maintenance UI displays the protected role and offers no Remove control.
A matching filename belonging to a different publisher is rejected rather
than overwritten. Verification and reconciliation errors are logged as
DEGRADED, while the boot continues so that SSH recovery remains possible.

For reproducible builds, the caller can supply
`FRE3NDER_SYSTEM_APP_PACKAGES_DIR=<verified-seed-directory>` to the RootFS
post-build hook. This stage copies regular `.fre3app` files into the image;
the runtime independently verifies signatures and identities before acting.
An image with an empty system-app directory performs no reconciliation.

## Fixed app storage roles

| Local installation choice | Runtime | Platform update behavior |
| --- | --- | --- |
| `sys` (default) | `/opt/fre3nder/apps-v2/<app>/` | Reconstructed from the signed HOME cache after SYS reset |
| `home` (explicit) | `/home/.fre3nder-runtime/apps-v2/<app>/` | Retained and checked against the signed cache; reconstructed only if missing or invalid |

Package-Core stores `storage` in Root-controlled installation metadata. An absent
field means `sys`; the signed package manifest is unchanged. Updates preserve
the recorded role. There is no automatic migration or arbitrary runtime path.
Web and display managers consume the same Core resolution. Cache and application
data stay at their existing HOME locations for both roles.

Before install or update, Core budgets the complete new extraction beside the
old runtime and a new persistent package copy, with 32 MiB operating headroom.
HOME runtime and cache requirements are combined when they share a filesystem.
Transaction directories reside beside the selected runtime for atomic rename
and rollback. Installed app data is not a rollback snapshot.

Fluidd is the first official web-frontend `.fre3app`. Its complete static web
payload lives in signed `payload/` members. Fluidd's service validates that
payload, but does not download files, change Moonraker configuration, select a
frontend, or run a daemon. Fluidd updates come from another signed `.fre3app`
through the package core or a future optional package-repository application.
Moonraker's `[update_manager fluidd]` is no longer part of the current design.

Older installations may retain the previous `fre3nder/fluidd.conf` in `/home`.
Removing that fragment and restarting Moonraker once is a separate controlled
device-migration step. Ordinary `.fre3app` install, update, and remove actions
do not restart Moonraker or edit the main `moonraker.conf`. The platform-owned
`[include fre3nder/*.conf]`, camera fragment, and generic Moonraker update
manager remain independent of Fluidd.

## Web frontend selection

A package may declare `[web] frontend = true`. This generic capability requires
a signed, nonempty `payload/index.html` and is recorded in package metadata.
It cannot change during a normal package update. Without `[web]`, the capability
is false.

The package core owns `/home/.fre3nder/frontend/active`, a root-managed file
containing exactly `<app>\n`. Installing the first web frontend selects it;
installing another preserves a valid existing selection. Updating a package
preserves the selection. Removing the selected package clears it, while removing
any other package leaves it alone. Boot recovery never invents a selection.
The former selection under `/home/fre3nder/.fre3nder/frontend/active` is not
read by the new platform code.

After a successful interactive install or update of the selected frontend,
or removal of that frontend, the privileged package core requests an S62 web
restart. A restart failure produces a warning and does not roll back an already
completed package transaction. S62 respects
`/home/fre3nder/.fre3nder/web/disabled` as an opt-out for the selected
application frontend. The independently enabled core Maintenance UI can still
require Lighttpd. Package services do not start S62.

## Local display frontend selection

A package may declare `[display] frontend = true` with `api = 1`. Display
frontends must set `runtime.autostart = false`; the generic S65 application
runtime must never start them in parallel. The capability and API version are
signed package metadata and cannot change during a normal update.

The package core owns `/home/.fre3nder/display/active`, a root-managed file
containing exactly `<app>\n`. Unlike the web frontend's first-install default,
installing a display frontend never changes this selection. Selection is
explicit through `fre3nder app display select <app>`, and only an installed
display-capable package can be selected. `fre3nder app display disable` clears
the selection. Updating the selected package preserves it; removing the selected
package clears it; boot recovery never invents it.

Display Frontend API v1 separates application lifecycle from hardware privilege.
The platform display manager owns framebuffer, touch, optional backlight, and
optional beeper discovery and permissions, then supplies their paths to the
selected unprivileged package service through `FRE3NDER_DISPLAY_*` environment
variables. Applications must not hard-code printer-specific input device names
or perform privileged device setup.

The platform display manager is `/etc/init.d/S64fre3nder-display`. It owns
hardware discovery and permission setup, then asks the package core to run only
the explicitly selected Display Frontend API v1 application. The generic S65
application runtime skips display frontends entirely. Packaging Fre3nderScreen
itself as a `.fre3app` uses this same generic display path.

## Fre3nderScreen factory app

The separate X2000 Fre3nderScreen cross-build produces a neutral app artifact.
`fre3nder-apps` imports that artifact and signs a `.fre3app`. The RootFS build
verifies the finished package with the package core and the official publisher
key, then embeds it unchanged at
`/usr/share/fre3nder/factory-apps/fre3nderscreen.fre3app`.
This package is a seed for a new system, not an update channel: later app
updates, replacement, selection, and removal use the normal package core.

`S63fre3nder-factory-app` runs after the platform services and before
`S64fre3nder-display`. It uses the package core for separate `install` and
`display-select` operations. Bootstrap failures are reported without blocking
Klipper, Moonraker, or SSH.

The root-controlled file `/home/.fre3nder/factory-apps/fre3nderscreen`
contains either `pending` or `complete`:

- With no marker and no existing display-app or user decision, write
  `pending`, install the factory package through the package core, explicitly
  select `fre3nderscreen`, then write `complete`.
- With `pending`, resume the interrupted install or selection idempotently.
- With `complete`, never automatically install, update, or select the
  factory package again.
- Preserve any existing user decision instead of replacing it with the
  factory default. A later Fre3nderScreen removal, another selected display,
  or `display-disable` leaves `complete` in place.
- An OTA may deliver a newer factory seed, but `complete` prevents its
  import on an already initialized system. Damaged or ambiguous package
  state must fail closed without automatic overwrite.

The seed path may change during an OTA. A `complete` marker remains in
persistent `/home`, so the new seed is never imported over a later user choice.

## Platform web services

The selected application frontend and core Maintenance UI use independent
Lighttpd service instances and separate browser origins.

`S62fre3nder-web` owns the selected application frontend on port `80`. It uses
the Core-resolved active frontend runtime to serve its `payload/`, on SYS or HOME.
`/etc/lighttpd/fre3nder.conf` remains frontend-neutral platform configuration:
`/websocket` and the Moonraker `/printer`, `/api`, `/access`, `/machine`, and
`/server` paths proxy to Moonraker at `127.0.0.1:17126`. `/webcam/` proxies to
the local `mjpg_streamer` camera backend at `127.0.0.1:8080`. This listener runs
as `nobody:nobody` and has no access to the Fre3nder Management socket.

`S62fre3nder-maintenance-web` independently owns the explicitly enabled core
Maintenance listener on port `8081`. It serves the Maintenance UI at `/` and
only the documented Management API status and browser-authentication routes.
Its Lighttpd worker runs as `nobody:fre3nder-management` so it can reach the
local Management Unix socket. A failure or opt-out of either web service does
not suppress the other.

Neither service installs packages or downloads a frontend. Camera capture,
Moonraker authorization and WebSocket handling remain platform services when a
selected frontend is absent. The RootFS post-build hook removes Buildroot's
competing `S50lighttpd` script, leaving the two Fre3nder-owned S62 services as
the automatic Lighttpd start paths.

The application-frontend opt-out marker stays in user-owned
`/home/fre3nder/.fre3nder/web/disabled`. Maintenance state is separate and
root-managed under `/home/.fre3nder/maintenance/`. The package core's frontend
selection remains independent of that Maintenance state.

## Manual Maintenance app administration

The explicitly enabled port-8081 Maintenance page provides an **Apps** section
for installed-app inspection, signed `.fre3app` upload and verification,
explicit installation, update and removal, and existing display selection.
A successful upload does not install a package. The Package-Core still decides
publisher trust, update ordering, service lifecycle and frontend effects.

The page reports the existing selected web frontend but does not switch it:
Package-Core has no supported manual web selection operation. Removing the
selected frontend clears port-80 selection; Maintenance stays available on
port 8081. Removing the selected display frontend similarly clears its
selection and can leave the screen without an active UI. The Factory-app
bootstrap and persistent user choice rules remain unchanged.

An app's Update button binds verification and confirmation to that app's name.
A different package cannot be confirmed until the selected update is cancelled
and a general upload is started. Version and publisher policy stays in Package-Core.

CLI and Maintenance mutations acquire the existing OTA transition lock
(`/run/fre3nder/ota/write.lock`) before the package lock
(`/run/.package-operation.lock`). Both are nonblocking and held by Package-Core
for the complete operation, then released on success or failure. OTA transitions
use the same first lock. Package verification and metadata inspection do not
acquire these mutation locks.

Maintenance stages app uploads privately in `/home/.tmp/fre3nder/uploads/`.
Its Apps and OTA requests share `/home/.tmp/fre3nder/lighttpd/` as the proxy
buffer; the separate port-80 listener is unaffected. App upload checks budget
staging, proxy and a future cache copy together with 64 MiB HOME headroom.
Core separately checks actual installation capacity at the chosen runtime.
The reserved `/home/.tmp` area is safely cleared at every regular boot before
services start. Uninstalled uploads are deliberately discarded by printer reboot,
while a Maintenance-service restart preserves them.
