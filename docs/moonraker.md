# Moonraker system fre3app

Moonraker is an **image-seeded, mandatory system fre3app**. The source pin and
pure-Python wheel lock live in `fre3nder-apps/apps/moonraker/`. That repository's
`apps/moonraker/scripts/prepare-moonraker` prepares an explicit package source under `local/moonraker/package/` from a pinned source checkout and locked
wheels offline; its package builder signs the payload with the official
Fre3nder app signing key. Fre3nder supplies the native Python dependencies
and libraries through Buildroot.

## Packaging and image seed

The regular X2000 RootFS build requires a signed `moonraker.fre3app` in
`local/production/system-apps/` (or `FRE3NDER_SYSTEM_APP_PACKAGES_DIR`). A
release RootFS requires `release_serial >= 1`. A development RootFS also accepts
a signed `release_serial = 0` test package. The host wrapper verifies the seed
against the immutable official public key before RootFS assembly.

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
   under the unprivileged `fre3nder` user. The app service owns the PID and
   start/stop/status logic and waits for its API socket before reporting success;
   S61 records that result without a second readiness check.

Moonraker sets `autostart = false` because only S61 owns its platform-dependent
boot order. During a **manual update**, Package-Core restarts a previously
running service after switching its runtime; no double-start from S65.

Moonraker's persistent config/logs/database/G-code remain at
`/home/fre3nder/printer_data`, independent of any app update, SYS reset or OTA.
The app service provides no on-device pip/Git updater. Moonraker's own upstream
`update_manager` must not modify the read-only signed application runtime.

## Qualification and compatibility

The operator reports successful deployment of the migrated Kernel and RootFS
on the X2000 reference system: Klipper and Moonraker report `active`, and
Package-Core confirms Moonraker as a running official system app. This is
evidence for that source/dependency/platform combination. Future recipe
updates must remain compatible with the Python and native dependencies
supplied by the platform.
