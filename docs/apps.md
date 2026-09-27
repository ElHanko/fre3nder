# Installable applications and web frontends

Status: the signed `.fre3app` package core is implemented in the platform
repository. Fluidd's earlier Legacy-app and web integration was qualified on
the investigated reference system; the `.fre3app` migration has not yet been
built or qualified on hardware. The earlier observations remain in
[managed-app and web qualification](../research/docs/apps-web-qualification.md).

## Package lifecycle

`fre3nder-package-core` verifies Ed25519 signatures and file hashes before
installing a package. The `fre3nder` CLI exposes:

```text
fre3nder app verify <package.fre3app>
fre3nder app install <package.fre3app>
fre3nder app update <package.fre3app> [--allow-downgrade]
fre3nder app remove <app>
fre3nder app list
fre3nder app status <app>
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
