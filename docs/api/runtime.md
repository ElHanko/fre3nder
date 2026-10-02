# Runtime and integration contracts

Only the contracts explicitly marked below are `PUBLIC / SUPPORTED`.
Implementation: [Package-Core](../../configs/x2000/rootfs-overlay/usr/libexec/fre3nder/package-core)
and productive init scripts. Detailed package semantics remain in
[`.fre3app`](../fre3app.md); they are not redefined here.

## App services and environment

PUBLIC / SUPPORTED: signed package `service` implements `install`, `update`,
`restore`, `start`, `stop`, `status`, `uninstall`. It runs as `fre3nder`, with
the package runtime as working directory, no interactive stdin and ordinarily
no supplementary groups. Nonzero service status signals failure/not-running as
appropriate to the action; it is not a platform-wide error-code enumeration.
Display services receive the hardware groups described by the format contract.

| Platform-supplied value | Meaning |
| --- | --- |
| `FRE3NDER_APP_NAME` | Verified manifest app name |
| `FRE3NDER_APP_RUNTIME_DIR` | Extracted current runtime directory |
| `FRE3NDER_APP_STATE_DIR` | Root-managed persistent package state; not an app-writable metadata API |
| `FRE3NDER_APP_DATA_DIR` | App-owned persistent data directory |
| `FRE3NDER_HOME_DIR` | Fre3nder user home |

These are values provided to services, not permission for users to redirect
platform management paths. The same identifier can also exist as an internal
test override; that use is not promoted to a public configuration knob.

## Display Frontend API v1

PUBLIC / SUPPORTED: `[display] frontend = true`, `api = 1`; display apps do not
use ordinary app autostart. Selection goes through the public display CLI and
S64 supplies its `start`, `stop`, `status` actions with the required paths.

| Platform-supplied value | Contract |
| --- | --- |
| `FRE3NDER_DISPLAY_API` | `1` |
| `FRE3NDER_DISPLAY_FRAMEBUFFER` | Required framebuffer path |
| `FRE3NDER_DISPLAY_INPUT` | Required discovered touch/input path |
| `FRE3NDER_DISPLAY_BACKLIGHT_POWER` | Optional Linux backlight power path; empty if absent |
| `FRE3NDER_DISPLAY_BEEPER` | Optional Linux input beeper path; empty if absent |

Paths/groups grant only the existing framebuffer, input, backlight and beeper
access. Do not assume a particular `eventN`, arbitrary GPIO access or `/dev/mem`.
See [display](../display.md) and the [format contract](../fre3app.md#display-frontend-api-v1).

## Filesystem, version and supported status

PUBLIC / SUPPORTED in the documented scope:

| Role / indicator | Path / meaning |
| --- | --- |
| Userdata HOME | `/home`, current backend `LABEL=FRE3NDERHOME` ext4 |
| System SYS | Current `LABEL=FRE3NDERSYS` ext4, reconstructible OverlayFS upper/work and platform boot metadata |
| Immutable baseline | `/rom`; `/run` and `/tmp` are volatile |
| App runtime | `/opt/fre3nder/apps-v2/<app>/`, reconstructible after SYS reset |
| App-owned data | `/home/fre3nder/.local/share/<app>/` |
| Root-managed signed package cache | `/home/.fre3nder/packages/<app>/`; recovery verifies cached package again |
| Web/display selection | `/home/.fre3nder/frontend/active`, `/home/.fre3nder/display/active`; manage through supported CLI/platform selection behavior |
| Platform version | `/usr/share/fre3nder/VERSION`, [YEAR.RELEASE[.STAGE]](../versioning.md) |
| Healthy writable-root prerequisite | `/run/fre3nder-root/status` contains `active`; absence/other state does not satisfy it |
| Runtime USB file access | `/run/fre3nder/usb/` when a valid runtime volume is available; logical backup rules remain authoritative |

These path roles do not make metadata JSON, manager markers or boot-control
files writable public APIs. Do not directly modify them to emulate a lifecycle.
The `active` prerequisite is supported for documented administrative gates;
arbitrary root/service-status enums have no blanket compatibility promise.

The Screen settings path is
`/home/fre3nder/.local/share/fre3nderscreen/fre3nderscreen.json`. Its initialization
and supported app scope are in [display](../display.md). A complete stable JSON
schema is not established by this repository; arbitrary app-specific keys are
`UNCLEAR` as an integration contract.

## HTTP routing

PUBLIC / SUPPORTED: the selected application frontend and Maintenance Web use
separate Lighttpd listeners and separate browser origins.

Port `80` belongs to the selected signed application frontend. Moonraker routes
(`/websocket`, `/printer`, `/api`, `/access`, `/machine`, `/server`) and
`/webcam/` remain there. It exposes no Fre3nder Management API route and runs as
`nobody:nobody`, without management-socket access.

Port `8081` exists only while Maintenance is explicitly enabled. It serves the
core Maintenance UI at `/` and the documented `/fre3nder/api/v1/...` status and
browser-authentication routes. Browser-admin mutations additionally require a
paired session, session CSRF token and matching port-8081 `Origin`/`Host`.

Neither listener currently supplies TLS. Moonraker continues to own
HTTP/JSON-RPC/WebSocket authorization for its upstream routes; Management API v1
is separately platform-owned.

## Supported provisioning and opt-ins

PUBLIC / SUPPORTED: FAT32-root `wpa_supplicant.conf`, `authorized_keys` and empty
`enable_ssh`, copied to `/run/fre3nder/provisioning/` after the documented
regular-file, size and unique-volume checks. See [networking](../networking.md#usb-provisioning).
These are boot-local administrative inputs; HOME/SYS provisioning is a separate
storage operation.

Maintenance Web is disabled by default and is managed through
`fre3nder maintenance {status|enable|disable|unlock|lock}` or Management API v1. Its
root-managed persistent marker is `/home/.fre3nder/maintenance/enabled`; do not
edit it directly. The existing `/home/fre3nder/.fre3nder/web/disabled` marker
continues to opt out of the selected application web frontend. An explicitly
enabled Maintenance UI is independent of that frontend choice.

PUBLIC / SUPPORTED, narrowly scoped: the regular non-symlink file
`/home/fre3nder/f005-auto-transition.enabled` must contain exactly seven bytes
`enabled`, without newline. It permits one existing Stock→Fre3nder MCU transfer
at startup for the exact supported Stock state. It does not authorize unknown
MCUs, automatically update a Qualified predecessor or qualify a Candidate.
This opt-in can cause firmware writes; follow [F005 switching](../f005-mcu-switching.md).

## Environment status

Only the App-/Display-service variables above are public runtime integration
values. Documented build settings remain within [build](../build.md)'s wrapper
contract. Core path overrides are `INTERNAL / UNSTABLE`; test/device/mount/
command substitution is `IMPLEMENTATION DETAIL`.

Optional camera resolution/FPS, NTP peer, timeout and discovery overrides exist
in code but lack an established supported public configuration contract. Their
support/compatibility remains `UNCLEAR`. Describing a service's current defaults
does not promote the corresponding environment variables.

## Internal boundaries

INTERNAL / UNSTABLE: direct Libexec Core calls/JSON API v1, package metadata,
Factory markers, OTA `pending.json`, persistent activation/known-good records,
F005 Runtime target/release parsing, service-state files and undocumented
socket/PTY coupling. Read-only diagnostics may inspect these; third-party
automation must not assume stable schemas or edit them to advance transitions.

`/run/fre3nder-management/api.sock` is the documented exception: its Management
API v1 contract is PUBLIC / SUPPORTED as described in [management](management.md).

Klippy `/run/fre3nder-klipper/klippy.sock`, Moonraker's local Unix socket and
`/tmp/klipper_host_mcu` are platform/upstream service coupling, not new public
Fre3nder protocols. Boot restore and S89 postboot are internal lifecycle actions.
The USB helper's key/value status and `api_version=1` are internal as well.

IMPLEMENTATION DETAIL: Python functions, bootloader framing, locks, PIDs,
temporary files and fixture injection. Complete App-CLI JSON compatibility,
arbitrary diagnostic status enums and complete source/build-manifest schema
remain `UNCLEAR`; visible implementation does not establish a public promise.
