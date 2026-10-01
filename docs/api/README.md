# Fre3nder API reference

This reference documents existing interfaces for the current supported scope.
`PUBLIC / SUPPORTED` is limited to the described usage, format or integration
contract. It does not imply universal hardware qualification.

Non-public internal Fre3nder interfaces have no compatibility promise unless
explicitly documented as `PUBLIC / SUPPORTED`. A version constant, exported
environment variable, visible file or test fixture does not create that promise.

| Interface family | Status | Owner | Authoritative detail |
| --- | --- | --- | --- |
| Documented `fre3nder app`, `backup create`, `ota` commands | PUBLIC / SUPPORTED | Fre3nder platform | [CLI](cli.md) |
| `.fre3app` v1, publisher trust, service contract, Display API v1 | PUBLIC / SUPPORTED | Platform format; app implements its signed service | [Package contract](../fre3app.md), [runtime](runtime.md) |
| Documented app data/runtime roles, SYS/HOME, VERSION, supported root indicator | PUBLIC / SUPPORTED in the stated scope | Fre3nder platform | [Runtime](runtime.md), [storage](../storage-layout.md), [versioning](../versioning.md) |
| `.ota` container/signature and opaque transaction-ID workflow | PUBLIC / SUPPORTED | Fre3nder platform | [OTA](../ota.md), [updates](../updates.md) |
| Backup CLI, logical targets and archive format | PUBLIC / SUPPORTED | Fre3nder platform | [Backup](../backup.md) |
| HTTP routing, USB provisioning, documented Web/F005 opt-ins | PUBLIC / SUPPORTED | Platform routing/configuration | [Runtime](runtime.md), [networking](../networking.md), [F005 switching](../f005-mcu-switching.md) |
| Documented build/sign/deploy/operator invocations | PUBLIC / SUPPORTED for documented use | Repository tooling; operator controls execution | [Build](../build.md), [installation](../installation.md), [display](../display.md), [recovery](../recovery.md) |
| Proxied Moonraker HTTP/WebSocket and Klipper protocols | Upstream-owned public interfaces; no Fre3nder API ownership | Moonraker/Klipper upstream | [Routing boundary](runtime.md#http-routing), [Moonraker](../moonraker.md) |
| Direct `/usr/libexec/fre3nder/*`, Core JSON API v1, boot/restore/postboot operations | INTERNAL / UNSTABLE | Platform implementation | [OTA](../ota.md), [backup](../backup.md), [runtime](runtime.md#internal-boundaries) |
| Package metadata, pending/activation/known-good records, F005 Runtime target, internal UDS/PTYs | INTERNAL / UNSTABLE | Platform implementation | [Internal boundaries](runtime.md#internal-boundaries) |
| Python functions, bootloader framing, locks/PIDs/temp files, test/device/mount overrides | IMPLEMENTATION DETAIL | Implementation/tests | Not an integration surface |
| Complete App-CLI JSON schema, arbitrary service-status enums, Screen JSON keys, optional camera/timeout/discovery settings, complete build/source-manifest schema | UNCLEAR as a compatibility contract | Respective implementation | [CLI output limits](cli.md#output-and-exit-behavior), [runtime](runtime.md#environment-status) |

No public `--json`, new REST endpoint or new compatibility commitment is introduced
by this documentation. In particular, direct Core JSON v1 remains internal;
Moonraker API ownership does not move to Fre3nder because the platform proxies it.
