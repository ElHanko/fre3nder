# Fre3nder Management API v1

The Fre3nder Management API is the platform-owned interface for local
administration that must not be implemented independently by the web UI or local
display. API v1 covers system status, explicit Maintenance Web activation and
temporary browser-administration pairing, manual platform OTA and manual
signed application management. Application package semantics continue to use
the existing Package-Core.

## Transport and privilege boundary

`/usr/libexec/fre3nder/managementd` runs as a root-owned local service and listens
only on the Unix domain socket:

```text
/run/fre3nder-management/api.sock
```

No TCP listener is created by the management service. The socket is owned by
`root:fre3nder-management` with mode `0660`. Only the dedicated Maintenance
Lighttpd worker uses that group. The selected application frontend on port 80
runs as `nobody:nobody` and cannot connect to the management socket. The generic
`fre3nder` application user is deliberately not added to the management group.

Local Maintenance-control operations are authorized inside the daemon using Linux
Unix-socket peer credentials and are accepted only from UID 0. Browser pairing
endpoints are accepted only from the configured Lighttpd worker UID and can
create or revoke temporary in-memory browser sessions; they do not themselves
perform platform mutations. This prevents every `.fre3app` process from gaining
platform-management authority merely because applications currently share the
`fre3nder` runtime UID. Fre3nderScreen's selected process receives a narrowly scoped primary
`fre3nder-management` GID only when Package-Core executes the official signed
Screen package from a protected, manager-owned runtime. `SO_PEERCRED` must match
both the generic application UID and this primary GID; ordinary `.fre3app`
processes receive neither this GID nor socket access. This never runs the Screen
as Root. The selected Screen may call System details, Apps, OTA and local
Maintenance-control routes directly through the Unix socket; it does not use
browser cookies, CSRF, or port 8081. Core signature/transaction checks are
unchanged. The generic app UID alone has no privileged access.

The explicit browser OTA routes additionally permit paired browser administrators
through the existing worker/session/CSRF/Origin checks. This exception does not
expand local Maintenance-control or application-user permissions.

The protocol is HTTP/1.x with JSON responses. API v1 paths use the prefix:

```text
/fre3nder/api/v1/
```

Every successful response contains:

```json
{
  "api_version": 1,
  "ok": true,
  "operation": "..."
}
```

Errors set `ok` to `false` and return a stable error object containing `code` and
`message`. Clients must not parse daemon log text or invoke arbitrary commands.

## Current endpoints

### `GET /fre3nder/api/v1/system`

Returns the installed Fre3nder version from `/usr/share/fre3nder/VERSION` and the
current writable-root status.

Example shape:

```json
{
  "api_version": 1,
  "ok": true,
  "operation": "system-status",
  "system": {
    "version": "2026.5.a",
    "root_status": "active"
  }
}
```

### `GET /fre3nder/api/v1/system/details`

Returns `operation: system-details` and a read-only `system` snapshot for the
Maintenance **System** page and future local display clients. The existing
compact `/system` response remains unchanged. Detailed hostname, network and
device information is **not public**: this endpoint accepts UID 0 or the
authorized protected Screen service over the Unix socket, or a Maintenance
worker with a valid paired browser session while Maintenance is enabled. A
cookie from any other local UID grants no access.
GET requires no CSRF token and performs no administrative operation. The selected protected Fre3nderScreen client also has read access via its
special primary GID; the shared application UID alone gains no permission.

The response uses bytes, seconds and unformatted numeric load averages. Missing,
unreadable or unconfirmed observations are JSON `null`; clients display
`Unavailable`. Empty observed lists and absent frontend selections remain distinct
from unavailable observations. One unavailable source does not discard the rest
of the snapshot.

| `system` member | Fields / source |
| --- | --- |
| `platform` | `version`, `hardware_model`, `cpu_model`, `architecture`, `kernel_version`, `hostname`; VERSION, device tree, `/proc/cpuinfo`, uname and `/proc/sys/kernel/` |
| `runtime` | `uptime_seconds`, UTC ISO-8601 `system_time`, `load_average` array in 1/5/15-minute order |
| `memory` | `total_bytes`, `available_bytes`, `used_bytes`, `swap_total_bytes`, `swap_free_bytes`, `swap_used_bytes`; `/proc/meminfo` |
| `storage` | SYS/HOME array: `role`, `mountpoint`, `device`, `filesystem`, `total_bytes`, `used_bytes`, `available_bytes` |
| `boot` | `active_slot`, `active_rootfs`, `root_status` |
| `network` | Ethernet/WLAN `interfaces` array with `name`, `kind`, `state`, `carrier`, `addresses`; `default_ipv4_routes` and unambiguous `default_ipv4_route` |
| `usb` | Array of `port`, `parent`, `manufacturer`, `product`, `vendor_id`, `product_id`, `driver`, `interfaces` (`interface`, `driver`); USB sysfs topology, without serial numbers |
| `services` | Array of `name`, `status`, `recorded_status`, nullable `process_running` |
| `applications` | `installed_count`, `web_frontend`, `display_frontend`, `display_runtime_status` |
| `maintenance` | `enabled`, recorded `web_status`, read-only OTA-Core `ota` status and volatile OTA `execution` receipt |

RAM usage is `MemTotal - MemAvailable`, never `MemTotal - MemFree`: reclaimable
cache is not presented as fully used RAM. Missing `MemAvailable` leaves used RAM
and its meter unavailable. No CPU-utilization sampler or history is added.

Storage matches the actual `/proc/mounts` entries at the existing runtime role
mountpoints (`/run/fre3nder-root/system` and `/home`), using OTA-Core's mount
parser. Missing or ambiguous mounts do not fall back to the containing filesystem.
`statvfs` reports used blocks as `f_blocks - f_bfree` and available space as
`f_bavail`, in bytes; filesystem reservations can therefore make used plus
available smaller than total. No USB block-device names are assumed. Boot slot
and RootFS come from OTA-Core's `discover_active_slot` and the running kernel's
`root=` argument, never from historical selector classifications. An unsupported
or ambiguous root argument leaves both fields unavailable.

Network link state comes from `/sys/class/net`; the existing `ifconfig -a`
supplies addresses without changing configuration. The address list reflects
what that platform tool reports, including aliases; it does not infer addresses
from lease files. Default IPv4 routes come from `/proc/net/route` and contain
`interface`, `gateway`, `metric`. Only a unique lowest-metric route is selected;
equal candidates leave `default_ipv4_route` unavailable. This is the main IPv4
routing table, not a claim about IPv6 or policy-routing decisions. If the route
file cannot be read, the route list is `null`, distinct from an empty table.

Service observations cover Klipper, Moonraker, Management, the application and
Maintenance web servers, camera, time synchronization, SSH and the display
manager. Recorded `active` is only retained as the effective service status when
the PID's `/proc` command line matches the expected platform process. A missing
process yields `not-running`; missing identity evidence yields `unconfirmed`.
These checks do not establish application health. Display runtime status is
explicitly **recorded** manager status: this query never calls application
service hooks or acquires a VT. Frontend selections read Package-Core's existing
Root-managed markers, returning `{status: selected, name: ...}`, `none` or
`unavailable`. Installed count uses only Package-Core `list`, not Apps
overview/detail; no upload directories or temporary output files are created.
OTA inspection uses only Core's existing read-only `status_response`, without
advancing transactions or creating package storage. No logs, history, new daemon
or additional tool installation are needed.

The Maintenance System view loads a snapshot on entry and on **Refresh**, with
no periodic polling. It uses the existing pairing controls in Overview, clears
private data on browser lock, and marks failures locally. RAM and SYS/HOME have
usage meters; USB connections and drivers start collapsed and scroll when long.
Overview stays the compact summary. This API/UI has host and Chromium fixture
coverage; field availability on the target system remains a separate runtime
check, not evidence of a newly performed hardware qualification.

### `GET /fre3nder/api/v1/maintenance`

Returns whether the Maintenance Web feature is explicitly enabled and the
current dedicated Maintenance listener status.

### `POST /fre3nder/api/v1/maintenance/enable`

Persists the explicit Maintenance Web opt-in and asks
`S62fre3nder-maintenance-web` to reconcile the dedicated port-8081 listener.
The selected application frontend on port 80 is unaffected. No request body is
accepted.

### `POST /fre3nder/api/v1/maintenance/disable`

Removes the Maintenance Web opt-in, revokes pending pairing and browser
administration state, and asks `S62fre3nder-maintenance-web` to stop the
dedicated port-8081 listener. The selected application frontend on port 80 is
unaffected. No request body is accepted.

### `POST /fre3nder/api/v1/maintenance/unlock`

Root-only local operation. Requires Maintenance Web to be enabled. Replaces any
previous pending pairing code with a cryptographically generated six-digit code.
The code is valid for ten minutes and at most five failed redemption attempts.
The response returns the code for presentation by the CLI or a future local
display. The code is never persisted.

### `POST /fre3nder/api/v1/maintenance/lock`

Root-only local operation. Revokes the pending pairing code and every browser
admin session. It does not disable the read-only Maintenance Web.

### `GET /fre3nder/api/v1/auth/session`

Browser endpoint projected only while Maintenance is enabled. Reports whether the
request carries a currently valid browser admin session.

### `POST /fre3nder/api/v1/auth/unlock`

Browser endpoint projected only while Maintenance is enabled. Accepts one small
JSON object:

```json
{"code":"483921"}
```

A successful one-time pairing redemption creates a random in-memory browser
session and a separate CSRF token. The session identifier is returned as an
`HttpOnly`, `SameSite=Strict` cookie scoped to `/fre3nder/api/v1/`; the CSRF token
is returned in the authenticated response and held by the Maintenance page in
memory. Sessions expire after 30 minutes without activity and after eight hours
maximum. Browser-admin mutations require the valid session, matching CSRF token
and an HTTP `Origin`/`Host` pair for the dedicated Maintenance origin on port
`8081`.

### `POST /fre3nder/api/v1/auth/lock`

Revokes the current browser session and expires its cookie. The root-only
`maintenance/lock` operation remains the way to revoke all sessions at once.

The current platform HTTP service is plain HTTP. Pairing protects administrative
actions from clients that only discover the Maintenance URL, but it does not
provide transport confidentiality against a party able to observe or modify LAN
traffic. No credential or session token is stored persistently.

## Manual OTA endpoints

All paths below have the prefix `/fre3nder/api/v1/ota/`. The read endpoint
requires either the privileged Screen peer or the Maintenance worker with a
valid paired session. Browser POST requests still require
`X-Fre3nder-CSRF`, matching HTTP port-8081 Origin/Host and active writable
runtime. The protected Screen peer uses its Unix credentials instead;
Maintenance-control authorization is independent of the web.

| Method / suffix | Input |
| --- | --- |
| `GET status` | No input; returns `ota.core`, `ota.execution`, `ota.packages`, `ota.storage` |
| `POST upload` | Binary body, `application/octet-stream`, `Content-Length`, URL-encoded local filename in `X-Fre3nder-Filename` |
| `POST verify` | JSON `{ "package_id": "<id>" }` |
| `POST preflight` | Same package ID |
| `POST backup-plan` | Package ID plus explicit `home: usb\|none`, `sys: usb\|home\|none` |
| `POST backup` | Same explicit selection; Core creates and verifies archives |
| `POST confirm` | Package ID and `transaction_id` returned by Core backup |
| `POST write` | Same package/transaction binding |
| `POST readback` | Same package/transaction binding |
| `POST prepare-activation` | Same package/transaction binding |
| `POST reboot` | Transaction ID only |

IDs are opaque 32-character lowercase hexadecimal strings. JSON requests accept
only the fields shown and remain subject to the existing 256-byte body limit.
Clients cannot supply paths, devices, slots, commands or Core environment values.

Upload accepts a nonempty `.ota` file up to **96 MiB**. Filename validation does
not use the supplied name as a server path. Management creates a random ID and
Root-owned `0600` temporary file below `/ota/packages/`, reads at most 64 KiB per
chunk, and requires exactly the announced length. Complete files are published
atomically with a no-replacement hard link, then the temporary name is removed.
EOF, timeout and write failures remove incomplete uploads. Complete packages
remain available after verification failures; a successful target-boot SYS reset
removes staged OTA packages. The boot-cleaned HOME area removes proxy buffers.

The Maintenance Lighttpd worker uses `/home/.tmp/fre3nder/lighttpd/`, owned by
Root with mode `0730` and group `fre3nder-management`. Port-80 `nobody:nobody`
cannot traverse it. Apps and OTA share this proxy buffer. Before OTA upload,
`statvfs.f_bavail` must cover staging on SYS and the proxy copy on HOME, each
with **32 MiB** headroom. If both paths share a filesystem, their body budgets
are combined. The remaining budget is rechecked while streaming. This reserves
capacity conservatively;
it does not reserve filesystem blocks against unrelated Root writers. Uploads
fail with `507` on insufficient capacity or ENOSPC. Content-Length is required;
Transfer-Encoding and multipart uploads are unsupported.

Accepted Core operations return **HTTP 202** with `operation: ota-accepted` and
an `execution` containing `id`, `operation`, `state: running` and the request
IDs/selection. Upload automatically starts full Core `verify` after publication.
Acceptance is not operation success. Poll `GET status` for the matching execution:

- `uploading` or `running`: still active;
- `succeeded`: `result` is the structured Core response;
- `failed`: `error` uses the management `{code, message}` format;
- `unknown`: completion cannot be established; no automatic retry is permitted.

Exactly one upload/Core execution is accepted at a time. Conflicts return `409`
(`ota-busy`); there is no queue. HTTP handling is concurrent and the background
Core process is independent of the submitting connection. Browser disconnects
do not cancel operations. Core transitions additionally use one nonblocking
lock covering validation, execution and state publication, including CLI calls.
The read-only Core `status` inspection remains available during execution.

Execution metadata is stored only in Root-owned
`/run/fre3nder-management/ota-execution.json`. It contains no session credentials
and is not an installation state machine. On daemon restart, an unfinished
execution becomes `unknown` and blocks new browser operations pending operator
inspection. Core pending/activation/known-good records remain authoritative;
do not edit them to advance phases. A reboot clears volatile execution metadata.

Reload obtains the existing session/CSRF through `auth/session`, then status,
package ID and the Core transaction ID. It starts no operation. A missing
transaction does not establish success: only Core known-good records document
validated update boots. Reboot can disconnect before its result is observed.
Manual inspection of actual runtime and recorded boot validation is independent
of the browser workflow; the UI does not wait for Maintenance to return.

The Maintenance UI composes these individual endpoints into one confirmed update
sequence. Upload automatically proceeds from Verify to Preflight; the primary
update confirmation covers backup planning/execution, confirmation, writes,
readback, activation and reboot. API authorization and Core transitions remain
unchanged. Reload never resumes submissions automatically: explicit continuation
uses the recorded Core phase. The browser retains only correlation data in
per-tab `sessionStorage`, including the transaction and expected package/target
identity and the reboot request outcome; it stores no session or CSRF credentials
there. Before calling `reboot`, the UI prepares its final REBOOT view without
claiming acceptance. HTTP 202 only accepts the asynchronous job: while the
connection remains available, the UI observes that job's Core result. Explicit
rejection retains the error/continuation flow. A confirmed `reboot-requested`
result ends the browser workflow; disconnect, lost invocation status or an
otherwise unconfirmed result ends it with a neutral unclear-status notice.
There is no reconnect, postboot polling or pairing requirement for this final
view. Reload restores the request outcome without submitting another operation.
The page asks for manual printer verification and makes no validated-boot claim;
Core postboot and known-good recording remain unchanged.

## Persistent Maintenance state

Maintenance is disabled by default. The root-managed marker is:

```text
/home/.fre3nder/maintenance/enabled
```

The absent marker means `disabled`; the valid marker contains exactly:

```text
enabled\n
```

Manage this state through the Management API or the public CLI:

```text
fre3nder maintenance status
fre3nder maintenance enable
fre3nder maintenance disable
fre3nder maintenance unlock
fre3nder maintenance lock
```

Do not edit the marker directly to emulate the lifecycle.

## HTTP projection through Lighttpd

Maintenance has its own explicitly enabled browser origin:

```text
http://<printer-host>:8081/
```

The Maintenance UI is served directly at `/`; there is no `/maintenance/`
prefix. The selected application web frontend remains on port `80` and exposes
no Fre3nder Management API route.

While Maintenance is enabled, the dedicated port-8081 Lighttpd worker proxies:

```text
GET  /fre3nder/api/v1/system
GET  /fre3nder/api/v1/system/details  (Root locally or paired browser)
GET  /fre3nder/api/v1/maintenance
GET  /fre3nder/api/v1/auth/session
POST /fre3nder/api/v1/auth/unlock
POST /fre3nder/api/v1/auth/lock
```

The root-only Maintenance mutation paths (`enable`, `disable`, pairing-code
creation and global `lock`) are not routed by either web listener. The explicit
documented OTA routes are projected only on Maintenance; manual Apps routes are also projected only on Maintenance; there are no
standalone backup, SSH or command-execution routes.

Port separation is an origin boundary, not a cookie boundary. Authenticated
browser mutations therefore additionally require the session CSRF token and a
matching `Origin`/`Host` for port `8081`; no CORS permission is granted to the
port-80 application frontend.

The dedicated Maintenance listener also sends a restrictive Content Security
Policy, denies framing, disables MIME sniffing and suppresses referrer data.
These response headers are scoped to the Maintenance listener and do not alter
the selected application frontend on port `80`.

If Maintenance resources or the management socket are unavailable, the
port-8081 listener remains stopped without affecting the selected application
frontend. When Maintenance is disabled, its listener stops and all browser
sessions/pairing state are revoked. The local Unix socket remains available to
local clients.

## Boundary to existing cores

The Management API does not redefine OTA, backup or `.fre3app` behavior.
Existing `/usr/libexec/fre3nder/ota-core`, `backup-core` and `package-core`
interfaces remain internal implementation boundaries. Management OTA operations
adapt OTA-Core; it consumes Backup-Core. Signature, slot, backup and activation
logic remain in those cores.

There is no general command-execution endpoint, no arbitrary path operation and
no client-supplied block-device or slot selection in Management API v1.

## Manual Apps endpoints

While Maintenance is enabled, paired browser administrators can manage trusted
`.fre3app` packages under `/fre3nder/api/v1/apps/`. For browser mutations,
the session cookie, CSRF token and Origin/Host validation remain mandatory.
The protected local Screen peer instead uses its Unix credentials and can
access these routes even with Maintenance Web disabled. Port 80 has no Apps routes. All responses retain API v1's `ok`,
`operation`, and structured error format.

| Method / suffix | Input / response |
| --- | --- |
| `GET status` | Installed metadata including `storage`, web/display selections, staged packages, volatile execution, HOME upload capacity, Core-reported SYS/HOME runtime capacity and informational `repository` update availability |
| `GET detail?name=<app>` | Package-Core status of one installed app (service status may have side effects) |
| `POST upload` | Streaming binary `.fre3app`, `Content-Length`, URL-encoded `X-Fre3nder-Filename`; automatically begins Verify, not installation |
| `POST verify` | `{ "package_id": "<id>" }` |
| `POST install` | `{ "package_id": "<id>", "storage": "sys" }`; optional `storage` accepts only `sys` or `home`, defaults to `sys`; requires a successful staged verification |
| `POST update` | `{ "package_id": "<id>", "name": "<app>" }`; exact app identity, no downgrade option |
| `POST remove` | `{ "name": "<app>" }` |
| `POST display/select` | `{ "name": "<app>" }` |
| `POST display/disable` | `{}` |
| `POST discard` | `{ "package_id": "<id>" }`; deletes only a staged upload |
| `POST acknowledge` | `{}`; operator acknowledgement of unknown execution after rereading installed state |

Core operations and successful upload verification return `202 apps-accepted`
with an execution ID, operation and `running` state. `GET status` reports
`running`, `succeeded`, `failed` or `unknown`. It never automatically resubmits
jobs. An `unknown` outcome blocks additional mutations until the administrator
has inspected the installed state and explicitly acknowledged the uncertainty.
Execution metadata is stored under `/run/fre3nder-management/apps-execution.json`,
not in the package cache.
Install receipts include the verified app name even if the operation fails.
Status snapshots capture the receipt before reading Package-Core state, so a
completion during the read remains `running` in that response and is polled again.
The Maintenance UI confirms successful install/update/remove receipts against
the returned installed state before showing a green success message. A removal
must be absent; an installation or update must match the resulting package's
name, version and release serial. New actions clear previous messages.

App files are staged as private, Root-owned temporary files under
`/home/.tmp/fre3nder/uploads/` (directory `0700`, files `0600`), then published
atomically without overwrite. Filenames
supplied by browsers are never used as filesystem paths. The maximum compressed
package is 256 MiB; HOME upload capacity checks budget proxy buffering, staging
and a future persistent cache copy together, plus 64 MiB headroom. Core checks
uncompressed runtime, transaction and cache space again before installation. The
96 MiB OTA package limit remains unchanged. Persistent verified package copies
remain solely under Package-Core ownership in HOME. Package-Core maintains the
trust decision, release-serial policy, service lifecycle, and frontend selection.
It also owns cross-process exclusion with CLI app mutations and OTA transitions:
it acquires the existing OTA lock before the package lock, without waiting.
A conflicting asynchronous app job reports failure in its execution receipt;
acceptance does not guarantee that the mutation started.

App updates accept no storage argument and preserve Core's installed role.
`GET status` returns `storage.sys.available_bytes` and
`storage.home.available_bytes` from Core (`null` when unavailable), alongside
the existing upload `available_bytes`, maximum and reserve fields.

The early storage bootstrap clears all of `/home/.tmp` only after validating
the real writable HOME mount, before managementd or Lighttpd starts. Parent
directories `/home/.tmp` and `/home/.tmp/fre3nder` are Root-owned `0711`.
Uninstalled app uploads and proxy buffers are intentionally lost at printer
reboot; installed caches and HOME runtimes are separate. Restarting Maintenance
does not clear uploads. OTA's `/ota/packages/`, transaction state and 96 MiB
limit retain their existing lifecycle. Operation errors appear beside the
affected upload, package, app or frontend controls; session/API errors may be global.

### Informational repository updates

`GET /fre3nder/api/v1/apps/status` adds `apps.repository` to the existing
`200 apps-status` response. All previous fields, operations and authorization
requirements retain their meaning. No additional route or service is involved.
Management reads installed metadata from Package-Core and schema 1 of the
optional `fre3nder-app-update` client's
`/home/fre3nder/.local/share/fre3nder-app-update/status.json`.
The input contract is documented in
[`fre3nder-apps/apps/fre3nder-app-update/README.md`](https://github.com/ElHanko/fre3nder-apps/blob/main/apps/fre3nder-app-update/README.md#persistent-output-schema-1).
The status request performs no network request, package download or installation.

| `apps.repository` field | Meaning |
| --- | --- |
| `client_installed` | Whether Package-Core lists `fre3nder-app-update`; retained app data is ignored when it is absent |
| `configuration` | Client's `unconfigured`, `configured` or `invalid`; `unknown` when no usable status is available |
| `check` | Client's `disabled`, `ok` or `error`; `unavailable` when no usable status is available |
| `availability` | `checked`: last reported check succeeded; `cached`: last reported check failed but an earlier successful snapshot exists; `unavailable`: no usable configured repository snapshot |
| `identity` | Repository `{name, key_fingerprint, base_url}`, or `null`; name and fingerprint may be `null` before the first successful check |
| `revision` | Positive index revision of the successful snapshot, or `null` |
| `last_attempt` | Client's last attempt time (UTC ISO 8601), or `null` |
| `last_success` | Client's last successful check time (UTC ISO 8601), or `null`; retained unchanged after a failed check |
| `updates` | List of matching installed apps with a newer positive release serial; empty when no usable repository snapshot exists |
| `error` | `null` or `{code, message}` explaining missing client/status, invalid/unreadable status or a failed repository check |

Example `apps.repository` after a successful check:

```json
{
  "client_installed": true,
  "configuration": "configured",
  "check": "ok",
  "availability": "checked",
  "identity": {
    "name": "Example repository",
    "key_fingerprint": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    "base_url": "https://repository.example.invalid/"
  },
  "revision": 7,
  "last_attempt": "2026-10-20T10:00:00+00:00",
  "last_success": "2026-10-20T10:00:00+00:00",
  "updates": [
    {
      "name": "sample",
      "publisher": {
        "id": "trusted",
        "key_fingerprint": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      },
      "installed": {"version": "1.2.0", "release_serial": 2},
      "offered": {"version": "1.3.0", "release_serial": 3, "channel": "stable"}
    }
  ],
  "error": null
}
```

Management compares only installed Core metadata against offers with the exact
same app name, publisher ID and publisher fingerprint, for the current
`fre3nder-x2000` / `mipsel` target. It selects the highest offered
`release_serial` greater than the installed serial, one entry per app sorted by
name. Version strings are display data; there is no semantic version comparison.
Equal or lower positive serials are not updates. Development (`0`) has no version
ordering: different Development versions are never reported as newer. A positive
release serial may replace installed Development; a Development offer cannot
replace an installed positive serial. `offered.channel` preserves `stable` or
`testing`; this endpoint applies no additional channel preference. Incomplete
installed version/serial/publisher metadata is not used to infer an update.

An absent client yields `client-not-installed`; a missing status file yields
`status-missing`. Unsafe/unreadable paths yield `status-unavailable`, malformed,
oversized or unsupported status yields `status-invalid`. These cases report
`configuration: unknown`, `check: unavailable`, `availability: unavailable`,
null identity/revision/times and no updates, while the existing Apps response
remains available. An unconfigured client reports `unconfigured` / `disabled`
with no error and no updates. Client configuration or check errors use
`repository-check-failed` with the client's error message.

After a network or validation error, `check: error` and
`availability: cached` explicitly qualify any updates derived from the retained
snapshot. An error before any successful check yields `availability: unavailable`.
An empty `updates` list with `cached` or `unavailable` never confirms that apps
are current. Even `checked` describes only the client's last reported check at
`last_success`, not live reachability or signed freshness; old status files are
not automatically aged into a different state. Consult the timestamps.

All repository fields are **informational, unprivileged app data**. The reader
accepts at most 2 MiB, requires a regular file, and opens every parent directory
and the file using directory descriptors and `O_NOFOLLOW` to avoid symlink
traversal and path-replacement races. Invalid status never blocks normal app
management. Management does not independently authenticate this summary.
Repository identity, fingerprint and offers cannot establish publisher trust,
mark staged packages as verified, authorize installation, or replace
Package-Core's signature, identity and release-serial checks. Package-Core
remains authoritative for all manual update/install operations.
