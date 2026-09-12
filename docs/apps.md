# Installable applications

Status: **OFFLINE IMPLEMENTED / PARTIALLY HARDWARE QUALIFIED**.

Fre3nder supplies a small application dispatcher, `/usr/bin/fre3nder`, and
optional Lighttpd web infrastructure in the RootFS build inputs. The official
app catalog is the repository directory `apps/`:

```text
apps/
    fluidd/
        service
```

App definitions, app payloads, archives, app configuration, and the developer
template are not copied into the RootFS. Moonraker remains the separately
defined [platform baseline](moonraker-bringup-current-state.md); it is not
converted into an installable app by this interface.

## Interface and storage

```sh
fre3nder install fluidd
fre3nder uninstall fluidd
fre3nder status fluidd
fre3nder restore fluidd
```

The CLI accepts exactly an action and an app name. Names match
`[a-z][a-z0-9_-]{0,63}`. Invalid calls fail with a diagnostic and nonzero exit
code. A handler receives exactly one action; the dispatcher replaces itself
with that process and preserves its exit code. No other lifecycle or version
model is imposed on apps.

For every action, the handler is selected using the source/cache rules below
and installed as `/opt/fre3nder/apps/<name>/service`. A handler must be regular
and executable, start with `#!/bin/sh`, and contain no NUL bytes. Invalid cached
handlers are never executed: a published source or explicit local override
reconstructs them. Symlink ancestors are refused. An invalid leaf object can
be replaced as part of the owned cache directory without following it.
Definitions are trusted administrator-executed code, not sandboxed plugins.

This also means `status` can reconstruct a missing, invalid or incompatible
cached definition and thus require network access and write permission. With a
local source override it refreshes the handler on every call, too.
It does not bootstrap the app payload. If the
definition cannot be obtained, the dispatcher reports the source error and
does not invent app-specific status. Directly invoking a repository handler
with `status` is useful for offline diagnostics, including a missing or invalid
runtime handler.

| Role | Fluidd path | Persistence |
| --- | --- | --- |
| Generic CLI | `/usr/bin/fre3nder` | RootFS baseline |
| Generic source binding | `/usr/share/fre3nder/APP_REF` | Generated RootFS build provenance |
| Loaded app definition | `/opt/fre3nder/apps/fluidd/service` | Reconstructible system OverlayFS |
| Handler provenance | `/opt/fre3nder/apps/fluidd/APP_REF` | Commit of the cached executable; absent for local overrides |
| Web payload | `/opt/fre3nder/web/fluidd` | Reconstructible system OverlayFS |
| Desired state | `/home/fre3nder/.fre3nder/services/fluidd/installed` | Upgrade-persistent userdata |
| Owned Moonraker fragment | `/home/fre3nder/printer_data/config/fre3nder/fluidd.conf` | Upgrade-persistent userdata |
| Selected frontend | `/home/fre3nder/.fre3nder/frontend/active` | Upgrade-persistent frontend name |
| Built-in webserver disabled | `/home/fre3nder/.fre3nder/web/disabled` | Upgrade-persistent opt-out |

The desired-state marker is an empty regular file. Its existence means Fluidd
should be installed. It records no version, URL, digest, or update history.
Payload and handler survive normal reboots, but may disappear after a
system-overlay reset. `/home` retains the intent and configuration needed for
explicit reconstruction. Run lifecycle commands sequentially, without a
simultaneous Moonraker payload update.

## App-definition source revision

`VERSION` and release tags follow [the existing version contract](versioning.md).
An untagged build can retain the same `VERSION`, so a version-derived tag is
not a sufficient source identity for that build.

The RootFS build writes the already captured `project_commit` into
`/usr/share/fre3nder/APP_REF` only when `project_worktree_status` is `clean`.
The loader accepts exactly a full 40-character lowercase hexadecimal commit
and requests:

```text
https://raw.githubusercontent.com/ElHanko/fre3nder/<commit>/apps/<name>/service
```

This is an exact build-source compatibility boundary, not a new release or
app-version system. There is no `main`, `latest`, or tag fallback. The commit
and app must be published in that official repository; an unavailable source
fails. An existing valid handler is reused only when its adjacent runtime
`APP_REF` matches the platform commit. Missing, invalid or different provenance
causes reconstruction from exactly the platform commit. Runtime `APP_REF`
contains only that 40-character commit and a newline; it is executable-code
provenance, not a desired app version or registry.

The loader stages a complete cache directory containing `service` and `APP_REF`
before activation. It renames the old directory aside, activates the new pair,
and restores the old directory if activation fails. A failed download leaves
the cache unchanged and fails the call; it never executes the incompatible
old handler as a fallback. There is no mixed new-handler/old-provenance write.
The cache directory is owned by the loader and contains only these cache files.
This is not a power-loss-atomic directory exchange: interruption between the
directory renames can leave the runtime path absent, requiring reconstruction,
but cannot publish a mixed pair. Run lifecycle calls sequentially.

App-definition updates are consequently tied to platform-source changes and
explicit administrator development, separate from app payload updates.

Dirty builds write `unpublished` instead: their executable app definitions
cannot be reconstructed from HEAD alone. Such builds can execute an already
installed local handler or use an explicitly selected local source checkout:

```sh
FRE3NDER_APP_SOURCE_DIR=<project-root> fre3nder install fluidd
```

That override always reads and stages `<project-root>/apps/fluidd/service`
without network access, taking priority over an existing cache even when its
provenance matches. It removes runtime `APP_REF` so the local code is never
misrepresented as a published commit. A subsequent non-overridden call on a
published platform will reconstruct the matching official definition.
It is intended for fixtures and administrator-controlled development, including
the present uncommitted implementation; it explicitly gives the selected local
checkout authority over executable app code. It does not claim that a dirty
tree matches a published commit. With platform `APP_REF=unpublished`, a valid
cached handler can be reused without remote access or invented provenance;
without a valid cache or local override the call fails. Missing or malformed
platform refs fail without a local override. No compatibility promise is made for
manually mixing a definition from a different platform revision.

The standard host-side workflow for a dirty development build is:

```sh
scripts/install-development-app <printer-host> fluidd
```

The helper validates the repository app definition, runs the required
`prepare-x2000-development` safety preparation, transfers only that definition
through SSH/stdin, verifies its SHA256 on the target, and invokes
`fre3nder install <app>` with `/tmp/fre3nder-app-source` as the explicit local
source. This default form installs the app without restarting running services.

The explicit apply form is:

```sh
scripts/install-development-app --apply <printer-host> <app>
```

After a successful install, it restarts Moonraker and then the web server. It
does not restart Klipper. Both forms are development workflows; they do not
replace the separately required automatic app restore after boot or an overlay
reset.

In summary, a clean build whose `APP_REF` names a published commit uses:

```sh
fre3nder install <app>
```

A dirty build carrying `APP_REF=unpublished` uses:

```sh
scripts/install-development-app <printer-host> <app>
```

## Fluidd lifecycle

### Install

1. The dispatcher ensures the local handler.
2. The handler checks for the exact line `[include fre3nder/*.conf]` in the
   active `moonraker.conf`, without editing that file.
3. An existing valid payload is adopted unchanged, even if a newer release
   exists. There is no request to GitHub in that case.
4. Otherwise the handler queries the official stable Fluidd release and selects
   its sole uploaded `fluidd.zip` asset. The release must be neither draft nor
   prerelease, and its repository and download URL must identify
   `fluidd-core/fluidd`.
5. It streams the archive into a temporary directory alongside the target,
   checks the published size and, when supplied, the SHA256 digest. No digest
   supplied by upstream means HTTPS transport, size checks, ZIP CRC checks and
   payload validation are used, with an explicit diagnostic. A malformed or
   mismatching supplied digest fails.
6. Extraction occurs entirely in staging. Absolute paths, traversal, ambiguous
   ZIP paths, symlinks and special files are rejected. Reading every extracted
   file also checks ZIP integrity. The complete extracted tree must contain
   only normal files/directories, a nonempty `index.html`, and valid
   `release_info.json` identifying `fluidd-core/fluidd`. Moonraker additionally
   needs a nonempty upstream `version`; any declared `asset_name` must be
   `fluidd.zip`.
7. Only the validated directory is activated. An invalid prior target is moved
   aside and restored if activation fails. Staging is cleaned on normal success
   or failure. This is a staged rename with error rollback, not a guarantee of
   an uninterrupted exchange across power loss; explicit restore can retry.
8. The owned `fluidd.conf` is ensured. If no frontend is selected, install
   writes `fluidd` to the persistent `frontend/active` file; an existing valid
   selection is retained. The empty desired marker is created last.
   A failed attempt never creates a new desired marker. An existing
   desired marker remains during failed reconstruction.

A valid previous payload is never discarded because a download or validation
fails. If a later configuration/marker write fails, an already validated new
payload may remain; rerunning install adopts it. No half-extracted payload is
written into the active directory.

### Restore

The dispatcher first ensures a source-compatible handler, even after an overlay
reset. Within the Fluidd handler, an absent desired marker is a no-op; even an
existing payload is left alone. With a regular marker present, restore checks
the include, ensures its own configuration, and retains a valid payload.
Missing/invalid payloads use the same official stable bootstrap as install.
It restores intent, not a previous or desired Fluidd version. If bootstrap
fails, the retained marker allows a later retry.
Restore does not select a frontend: the existing `/home` selection survives
an overlay reset, and a missing selection remains an explicit user choice.

### Uninstall and status

Uninstall removes only `fluidd.conf`, the Fluidd payload, the active selection
if it is exactly `fluidd`, then the desired marker. Other valid frontend names
remain unchanged. It is idempotent. The cached handler is retained, subject to
the same provenance checks on subsequent calls. It does not modify
the main Moonraker configuration, databases, update metadata, other apps,
other printer data, or platform components. Unsafe symlink paths are refused;
they are not followed for deletion.

Status is read-only within the handler and emits:

```text
desired=installed|absent
app_handler=present|missing|invalid
payload=present|missing|invalid
moonraker_config=present|missing
moonraker_include=present|missing
```

`desired=installed` requires a regular marker. Invalid config objects count as
missing in status; modifying actions refuse them. `moonraker_config=present`
reports the owned fragment's regular-file presence, not whether a running
Moonraker has loaded it. Exit zero means status was reported successfully;
callers inspect the fields to learn the installation state.

## Moonraker configuration and update ownership

**Bestehende moonraker.conf werden nicht automatisch geändert.**

Bestehende Installationen müssen `[include fre3nder/*.conf]` einmal manuell in
ihre `moonraker.conf` aufnehmen. By default this file is:

```text
/home/fre3nder/printer_data/config/moonraker.conf
```

The required exact entry is:

```ini
[include fre3nder/*.conf]
```

New installations receive the include through the existing RootFS default.
The current S61 preparation already creates the fragment directory and an
app-neutral `00-base.conf`. Neither S61 nor the Fluidd handler migrates existing
user configuration. An absent include aborts install/desired restore with the
file path, required line, and explanation.

This ownership boundary was observed on the reference system: an older
persistent `moonraker.conf` containing only loopback in `trusted_clients` was
retained across the platform change and caused LAN proxy requests to receive
HTTP 401. After the operator removed that obsolete user configuration, S61
seeded the current RootFS default, including the private-network authorization
ranges and `fre3nder/*.conf` include, and the same LAN request succeeded. This
is expected behavior; RootFS defaults do not automatically migrate an existing
user-owned configuration.

Fluidd owns only this fragment:

```ini
[update_manager fluidd]
type: web
channel: stable
repo: fluidd-core/fluidd
path: /opt/fre3nder/web/fluidd
```

Changing the fragment requires Moonraker to reload configuration. The handler
prints the existing `/etc/init.d/S61fre3nder-moonraker restart` command when it
adds, changes or removes the fragment. It does not automatically restart the
service; run that command when the change should become active. No alternate
process manager or restart API is introduced.

Fre3nder owns definitions, initial bootstrap, desired state, configuration
integration and explicit restore. After bootstrap, Moonraker owns normal
Fluidd payload updates through its `web` deployer. No Fluidd release or digest
is pinned in Fre3nder, and no Fluidd ZIP is redistributed here. Applications
may have different lifecycle and update owners; the dispatcher imposes no
universal desired version or rollback mechanism.

Kernel, RootFS, Fre3nder Klipper, MCU firmware, A/B state and system packages
remain outside this app updater. This separation supports
REQ-2026.2-002/003/004/006/007; their requirement statuses are unchanged by
these offline fixtures.

## Development and validation

The repository-only [service template](../examples/services/service-template)
shows the four-action contract. There is no runtime template or generator.

Run `tests/test-fre3nder-apps` for temporary-directory fixtures. The dispatcher
uses `FRE3NDER_APPS_DIR`, `FRE3NDER_APP_SOURCE_DIR` and
`FRE3NDER_APP_REF_FILE` for isolated tests. The Fluidd handler additionally
uses `FRE3NDER_HOME_DIR`, `FRE3NDER_PRINTER_DATA_DIR`,
`FRE3NDER_MOONRAKER_CONFIG`, `FRE3NDER_WEB_DIR`, and `FRE3NDER_PYTHON`.
Absolute paths with safe ancestors are required.

`FRE3NDER_FLUIDD_FIXTURE_DIR` reads local `release.json` and `fluidd.zip`
fixtures instead of the network. These fixtures still exercise release
identity, size/digest and staging validation. They are generated by tests,
not copies of third-party artifacts. Fixture overrides are explicitly trusted
development inputs and should be unset for normal use.

Python 3, zlib, SSL support and CA certificates are existing platform inputs;
the build's effective-config checks already require them. App and service
fixtures do not build any target artifacts. Tests on the host do not qualify
target execution or hardware behavior.

## Optional built-in webserver

Lighttpd is generic platform infrastructure. It serves the selected frontend
over IPv4 LAN HTTP on port 80 and forwards the following path families to
Moonraker at exactly `127.0.0.1:17126`:

```text
/websocket                       exact path
/printer, /api, /access,
/machine, /server                exact prefix or prefix followed by /
```

The rule is `^/(websocket$|(printer|api|access|machine|server)(/|$))`.
It includes uploads/downloads under `/server/files`, authentication under
`/access`, and OctoPrint-compatible API paths when that Moonraker component is
configured. It does not enable additional Moonraker components or expose its
debug endpoints. Other paths remain static frontend requests. Lighttpd
`proxy.header = ( "upgrade" => "enable" )` enables WebSocket proxying through
`mod_proxy`; no separate WebSocket backend/module is used. Request and response
streaming avoids buffering complete G-code transfers in the proxy.

The baseline stays loopback-only. `mod_setenv` discards client-provided
`X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto` and `X-Scheme`; `mod_proxy`
supplies forwarding information from the actual connection. This preserves
Moonraker/Tornado's existing client-address/authentication boundary instead of
presenting every LAN client as trusted loopback. Users still configure
Moonraker authentication/trusted clients as appropriate; no auth framework or
automatic configuration migration is introduced.

`S62fre3nder-web` is the sole automatic start path and supports
`start|stop|restart`. The post-build hook removes Buildroot's `S50lighttpd`.
The package's sample `lighttpd.conf` is not used: S62 generates
`/run/fre3nder-web/lighttpd.conf`, containing the selected document root and an
include of `/etc/lighttpd/fre3nder.conf`.

Start requires the active persistent root and safe userdata paths. It does not
wait for S61/Moonraker: static delivery works independently, and proxy requests
may fail until Moonraker becomes available. There is no retry daemon or boot
download. With no selected frontend, an invalid name, a missing payload, or
an invalid/symlink index, the webservice stays stopped with a status such as
`no-frontend`, `frontend-invalid`, `payload-unavailable` or `state-invalid`.
Generic frontend validity means a safe directory with a regular, nonempty
`index.html`; it does not impose Fluidd release metadata on other frontends.

The service validates configuration with Lighttpd's `-tt` before starting it
in the foreground with `-D`. It records PID, status and diagnostics only under
`/run/fre3nder-web`. `active` means the expected process survived its initial
startup check, not a qualified end-to-end HTTP test. Stop/restart check the
daemon's expected arguments before sending a signal and bound the stop wait.
A stale PID is never used to kill an unrelated process. There is no automatic
service supervision after startup.

Lighttpd binds port 80 before dropping to the existing Buildroot
`nobody:nobody` account. It needs readable/traversable static payloads, not
write ownership of `/opt` or `/home`. Directory listing and symlink following
are disabled. The webserver never installs, updates or restores applications.

### Active frontend and an external webserver

`/home/fre3nder/.fre3nder/frontend/active` contains a single name matching
`[a-z][a-z0-9_-]{0,63}`, optionally followed by one newline. It is never a
filesystem path. S62 derives only `/opt/fre3nder/web/<name>` from it. The name
survives an overlay reset; the generated runtime configuration does not.

Fluidd install selects itself only if the file is absent. It retains both
`fluidd` and any other valid selected name without rewriting the file. Invalid
or symlink selection objects fail install/uninstall before changes. Uninstall
clears the selection only if it is `fluidd`, with no automatic replacement.
Selection changes print `/etc/init.d/S62fre3nder-web restart`; they do not
restart or enable the service automatically. A running server uses its prior
document root until explicitly restarted.

**`fre3nder install fluidd` setzt den eingebauten Lighttpd nicht voraus.**

Installation requires neither an enabled/running S62 nor a free port 80.
An external nginx, Caddy, Apache or other server may serve
`/opt/fre3nder/web/fluidd` and proxy the listed routes to `127.0.0.1:17126`.
The selected frontend is independent of whether Fre3nder's webserver is used.

To persistently disable the built-in service:

```sh
mkdir -p /home/fre3nder/.fre3nder/web
touch /home/fre3nder/.fre3nder/web/disabled
/etc/init.d/S62fre3nder-web stop
```

To enable it again:

```sh
rm /home/fre3nder/.fre3nder/web/disabled
/etc/init.d/S62fre3nder-web start
```

A regular disabled marker prevents a new start and reports `disabled`.
Symlinks and non-regular marker objects prevent startup with `state-invalid`.
The marker survives an overlay reset. Creating it does not stop an already
running process: use the documented stop command. Restart stops an existing
instance and then respects the marker, so a frontend-change hint cannot
implicitly re-enable the disabled service.

### Package and reference-X2000 validation

The local pinned Buildroot `2025.02.17`, commit
`d0820dd09916edcefc44e525355afbea30d5bee4`, defines Lighttpd `1.4.81`
(BSD-3-Clause). Only `BR2_PACKAGE_LIGHTTPD=y` and
`BR2_PACKAGE_LIGHTTPD_PCRE=y` are requested. PCRE selects PCRE2 for the routing
expression; the package also selects xxhash and libxcrypt on glibc. Optional
TLS, Lua, databases, compression and WebDAV features remain disabled.

The hash-checked upstream `1.4.81` source and Buildroot Meson definition were
inspected without building. `mod_proxy` is an unconditional dynamic module
with Buildroot's `-Dbuild_static=false`; `mod_setenv`, `mod_indexfile` and
`mod_staticfile` are built into the executable. There is no Buildroot
`LIGHTTPD_PROXY` switch and no separate `mod_setenv.so` to require. Upstream
also compiles other standard modules, including CGI/FastCGI facilities; this
configuration does not activate them. No extra package patch is introduced
solely to remove unused upstream module code.

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
authorization configuration described above was active. A real `/websocket`
request returned HTTP 101 and carried Moonraker JSON-RPC notifications,
including `notify_proc_stat_update`. When Moonraker was restarted, Lighttpd
temporarily reported the unavailable backend and automatically re-enabled it
after Moonraker returned.

## References and remaining qualification

The bootstrap contract uses the official
[Fluidd release API](https://api.github.com/repos/fluidd-core/fluidd/releases/latest).
The inspected response on 2026-09-05 advertised an uploaded `fluidd.zip` with
a `sha256:` digest; the implementation deliberately does not retain that
release version or checksum as desired state. Fluidd payloads are downloaded
directly from upstream and remain subject to upstream licensing. No third-party
payload/source is imported by this change; the handler and fixtures are
independently written Fre3nder material under the repository's licensing policy.

The configuration and payload-metadata checks were compared with the pinned
Moonraker `985c1d0bbeb90bc057d34a232c9dc3b05e0c6c8d` (GPL-3.0-only):
[web configuration](https://github.com/Arksine/moonraker/blob/985c1d0bbeb90bc057d34a232c9dc3b05e0c6c8d/docs/configuration.md#web-type-front-end-configuration)
and [NetDeploy validation](https://github.com/Arksine/moonraker/blob/985c1d0bbeb90bc057d34a232c9dc3b05e0c6c8d/moonraker/components/update_manager/net_deploy.py).

Lighttpd package provenance: pinned Buildroot
[package definition](https://gitlab.com/buildroot.org/buildroot/-/blob/d0820dd09916edcefc44e525355afbea30d5bee4/package/lighttpd/lighttpd.mk)
and [upstream 1.4.81 source](https://download.lighttpd.net/lighttpd/releases-1.4.x/lighttpd-1.4.81.tar.xz),
SHA256 `d7d42c3fd2fd94b63c915aa7d18f4da3cac5937ddba33e909f81cf50842a5840`
from Buildroot's package hash file. `src/meson.build` defines builtin/dynamic
modules; `src/mod_proxy.c` implements the verified `upgrade` option and
forwarding headers. No upstream code was imported into this repository.
See also [mod_proxy](https://redmine.lighttpd.net/projects/lighttpd/wiki/mod_proxy)
and [mod_setenv](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_setenv).

Routing was checked against the pinned Moonraker
[application](https://github.com/Arksine/moonraker/blob/985c1d0bbeb90bc057d34a232c9dc3b05e0c6c8d/moonraker/components/application.py),
`websockets.py`, `authorization.py`, `octoprint_compat.py`, and file-manager
endpoints. Fluidd's [manual hosting](https://docs.fluidd.xyz/installation/manual)
and [connection check](https://docs.fluidd.xyz/configuration/multiple_printers)
describe static hosting and `/server/info`. The inspected
[v1.37.4 router](https://github.com/fluidd-core/fluidd/blob/v1.37.4/src/router/index.ts)
uses Vue Router's default hash mode; no history-path fallback is introduced.
This is reference evidence, not a Fluidd version pin.

Still open: Fluidd reboot persistence, system-overlay reset and restore,
Moonraker-driven Fluidd update, uninstall and the built-in-webserver disable
marker on real hardware, an external-webserver scenario, and printer control
through the UI. HTTPS/TLS and alternative frontend implementations are outside
this step. The demonstrated initial Fluidd bootstrap, active selection, static
LAN delivery, HTTP/WebSocket proxying, loopback-only Moonraker binding, and LAN
authorization are qualified only on the investigated reference system.
