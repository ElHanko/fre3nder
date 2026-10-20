# Moonraker system fre3app

Moonraker is an **image-seeded, mandatory system fre3app**, not a Python/Git
checkout embedded at `/opt/fre3nder/moonraker`. Sources and the nine pinned
pure-Python wheels are prepared in `fre3nder-apps/apps/moonraker/`, then signed
with the **existing official** Fre3nder app signing key.

## Packaging and image seed

The regular X2000 RootFS build requires a signed `moonraker.fre3app` in
`local/production/system-apps/` (or `FRE3NDER_SYSTEM_APP_PACKAGES_DIR`). A
release RootFS requires `release_serial >= 1`. A development RootFS may carry a
signed `release_serial = 0` test package. The host builder verifies the seed
against the immutable official public key before entering Docker.

RootFS post-build copies the whole verified seed into
`/usr/share/fre3nder/system-apps/`. The old RootFS Moonraker checkout/venv are
removed, even from reused target trees. The generic `S58fre3nder-system-apps`
reconciler installs or upgrades the signed package after recovery.

## Boot and service

1. S58 restores already-installed app packages from the signed persistent cache.
2. S58 system-apps reconciles the Moonraker seed without starting it.
3. S59/S60 start the Klipper MCU and API socket.
4. S61 prepares `/home/fre3nder/printer_data` and `/run/fre3nder-moonraker`.
5. S61 asks `package-core service-start moonraker` to start the verified runtime
   under the unprivileged `fre3nder` user; readiness requires the UDS socket.

Moonraker sets `autostart = false` because only S61 owns its platform-dependent
boot order. During a **manual update**, Package-Core restarts a previously
running service after switching its runtime; no double-start from S65.

Moonraker's persistent config/logs/database/G-code remain at
`/home/fre3nder/printer_data`, independent of any app update, SYS reset or OTA.
The app service provides no on-device pip/Git updater. Moonraker's own upstream
`update_manager` must not modify the read-only signed application runtime.

## Qualification gate

The host signed package and unit tests do not prove that Moonraker's native
Python imports or API work on X2000. Qualify imports, startup, Klipper API,
manual update/rollback, SYS-reset recovery, OTA update and OTA rollback before
deploying this migration to a production printer. Native Python libraries are
still supplied by the Buildroot platform; compatibility needs a documented
contract before declaring arbitrary independent Moonraker releases supported.
