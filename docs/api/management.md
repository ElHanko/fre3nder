# Fre3nder Management API v1

The Fre3nder Management API is the platform-owned interface for local
administration that must not be implemented independently by the web UI or local
display. API v1 covers system status, explicit Maintenance Web activation and
temporary browser-administration pairing and manual platform OTA. Application
operations continue to use their existing public CLI paths.

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
`fre3nder` runtime UID. A later Fre3nderScreen integration must grant its
selected process an explicit narrow capability while continuing to use this same
API contract.

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
requires the Maintenance worker and a valid paired session. Every POST also
requires `X-Fre3nder-CSRF`, matching HTTP port-8081 Origin/Host and active
writable runtime. Root-only Maintenance-control authorization is unchanged.

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
removes staged packages and proxy buffers.

Lighttpd uses `/ota/packages/.lighttpd-upload/`, owned by Root with mode `0730`
and group `fre3nder-management`. Port-80 `nobody:nobody` cannot traverse it.
Before upload, `statvfs.f_bavail` must cover two complete bodies (staging and
proxy copy) plus **32 MiB** for ordinary SYS writes. The remaining double-body
budget is rechecked while streaming. This reserves capacity conservatively;
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
GET  /fre3nder/api/v1/maintenance
GET  /fre3nder/api/v1/auth/session
POST /fre3nder/api/v1/auth/unlock
POST /fre3nder/api/v1/auth/lock
```

The root-only Maintenance mutation paths (`enable`, `disable`, pairing-code
creation and global `lock`) are not routed by either web listener. The explicit
documented OTA routes are projected only on Maintenance; there are no general app,
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
