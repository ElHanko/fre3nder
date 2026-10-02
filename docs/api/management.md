# Fre3nder Management API v1

The Fre3nder Management API is the platform-owned interface for local
administration that must not be implemented independently by the web UI or local
display. The initial v1 slice covers system status and explicit Maintenance Web
activation. OTA and application operations continue to use their existing public
CLI paths until corresponding management operations are added deliberately.

## Transport and privilege boundary

`/usr/libexec/fre3nder/managementd` runs as a root-owned local service and listens
only on the Unix domain socket:

```text
/run/fre3nder-management/api.sock
```

No TCP listener is created by the management service. The socket is owned by `root:fre3nder-management` with mode `0660`.
Lighttpd uses that dedicated group for the read-only HTTP projection. The
generic `fre3nder` application user is deliberately not added to the group in
this first slice.

Mutating operations are authorized inside the daemon using Linux Unix-socket
peer credentials and are accepted only from UID 0. This prevents every
`.fre3app` process from gaining platform-management authority merely because
applications currently share the `fre3nder` runtime UID. A later
Fre3nderScreen integration must grant its selected process an explicit narrow
capability while continuing to use this same API contract.

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
current S62 web-service status.

### `POST /fre3nder/api/v1/maintenance/enable`

Persists the explicit Maintenance Web opt-in and asks S62 to reconcile the web
service. No request body is accepted.

### `POST /fre3nder/api/v1/maintenance/disable`

Removes the Maintenance Web opt-in and asks S62 to reconcile the web service. If
no selected web frontend needs Lighttpd, S62 stops it. If a selected frontend is
still active, Lighttpd remains running for that frontend. No request body is
accepted.

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
```

Do not edit the marker directly to emulate the lifecycle.

## HTTP projection through Lighttpd

When Maintenance is enabled, S62 exposes the static core UI at:

```text
/maintenance/
```

and proxies only these read-only Management API paths to the Unix socket:

```text
GET /fre3nder/api/v1/system
GET /fre3nder/api/v1/maintenance
```

The mutation paths are not routed by Lighttpd. Enabling or disabling Maintenance
therefore remains a local administrative action in this first slice. The two
projected GET endpoints do not use Moonraker authorization; while Maintenance is
enabled, they are LAN-visible read-only platform status on the same port as the
Maintenance UI.

If Maintenance is enabled but its static resources or local management socket are
unavailable, S62 does not suppress an otherwise valid selected application
frontend. It omits the Maintenance routes; with no valid frontend remaining, it
keeps Lighttpd stopped and records the Maintenance failure reason.

When Maintenance is disabled, neither the core Maintenance files nor the
Fre3nder Management API are routed over HTTP. The local Unix socket remains
available for local clients such as the CLI and future Fre3nderScreen
integration.

## Boundary to existing cores

The Management API does not redefine OTA, backup or `.fre3app` behavior.
Existing `/usr/libexec/fre3nder/ota-core`, `backup-core` and `package-core`
interfaces remain internal implementation boundaries. Future management
operations must adapt those existing cores instead of reimplementing package,
signature, slot, backup or activation logic.

There is no general command-execution endpoint, no arbitrary path operation and
no client-supplied block-device or slot selection in Management API v1.
