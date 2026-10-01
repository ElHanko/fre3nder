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
fre3nder app install <package.fre3app>
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
reconstructs `/opt/fre3nder/apps-v2/<app>/`, and calls the unprivileged service's
`restore` action after a system-overlay reset. Recovery needs neither a network
download nor a web-service restart. S65 starts packages marked for autostart.
See [the package format](fre3app.md) for its trust and service
contract.

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
completed package transaction. S62 respects the persistent opt-out marker
`/home/fre3nder/.fre3nder/web/disabled`. Package services do not start S62.

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

## Platform web service

S62 uses the active name to serve
`/opt/fre3nder/apps-v2/<app>/payload` through Lighttpd. It requires the active
Fre3nder root, available userdata, a safe payload directory, and a regular
nonempty `index.html`. An absent selection or payload leaves the service
stopped with a status under `/run/fre3nder-web`. S62 neither installs packages
nor downloads a frontend.

`/etc/lighttpd/fre3nder.conf` is frontend-neutral platform configuration:
static files use the selected document root; `/websocket` and the Moonraker
`/printer`, `/api`, `/access`, `/machine`, and `/server` paths proxy to Moonraker
at `127.0.0.1:17126`. `/webcam/` proxies to the local `mjpg_streamer` camera
backend at `127.0.0.1:8080`. The platform-owned Moonraker camera fragment is
seeded by S61. Camera capture, proxying, Moonraker authorization and WebSocket
handling remain platform services when Fluidd is absent. S62 is the only
automatic Lighttpd start path; the RootFS post-build hook removes Buildroot's
competing `S50lighttpd` script.

The opt-out marker stays in user-owned `/home/fre3nder/.fre3nder/web/disabled`.
An external webserver can instead serve the selected package payload and proxy
the same API and camera routes. The package core's frontend selection is
independent of which HTTP server is used.
