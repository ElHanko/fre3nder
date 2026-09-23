# Managed apps and web reference qualification

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
[Moonraker authorization configuration](../../docs/apps.md#optional-built-in-webserver)
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
