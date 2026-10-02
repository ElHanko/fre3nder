# Networking and administrative access

The productive behavior is implemented by
[S20 provisioning](../configs/x2000/rootfs-overlay/etc/init.d/S20fre3nder-provision),
[S40 network](../configs/x2000/rootfs-overlay/etc/init.d/S40fre3nder-network) and
[S50 Dropbear](../configs/x2000/rootfs-overlay/etc/init.d/S50dropbear).
It is scoped to the supported reference path; unrelated network-manager,
Bluetooth and runtime failover features are not promised.

## Network selection

S40 brings up loopback at `127.0.0.1/8`. It first tries a suitable non-wireless
Ethernet interface with carrier and a DHCP lease. A successful Ethernet path
leaves WLAN down. The validated external adapter path uses USB CDC-NCM, not the
X2000 integrated MAC. Boot failure of Ethernet falls back to WLAN when a valid
boot-local configuration and exactly one wireless interface are available.
WLAN uses wpa_supplicant with nl80211 and a long-lived BusyBox DHCP client.
There is no automatic runtime/hotplug Ethernet/WLAN failover.

## USB provisioning

Place any needed inputs at the root of a FAT32 provisioning volume:

| Input | Accepted form | Effect |
| --- | --- | --- |
| `wpa_supplicant.conf` | Nonempty regular non-symlink file, at most 64 KiB | Boot-local WLAN configuration; association must still succeed |
| `authorized_keys` | Regular non-symlink file, at most 64 KiB, accepted public-key lines | SSH authorization input, not an SSH-enable switch |
| `enable_ssh` | Empty regular non-symlink file | Explicit SSH enable, effective only with valid nonempty authorized keys |

The authorized-key parser accepts plain `ssh-rsa`, `ssh-ed25519` or
`ecdsa-sha2-nistp256/384/521` key lines, comments and blank lines. Private-key
material and malformed lines are refused. OpenSSH authorized-key options are
not accepted by this parser. Provision only public keys; do not copy private
keys to the medium. Keep WLAN credentials out of Git and documentation.

S20 scans USB block devices for up to ten seconds. Each candidate is mounted as
vfat read-only with `nosuid,nodev,noexec`. A volume counts as a provisioning
candidate if any recognized pathname is present, even when that entry is invalid.
Multiple matching volumes cause all candidates to be refused. Within a unique
volume, valid files may be accepted individually while invalid components are
reported; a partial result does not mean SSH or WLAN prerequisites are complete.

Accepted files are copied with restrictive permissions to
`/run/fre3nder/provisioning/`, then the source is unmounted before network startup.
The inputs are volatile and are cleared/re-evaluated at boot; the service does
not persist credentials or write the provisioning medium, SquashFS or eMMC
partitions. This boot-local path is distinct from the later runtime USB mount
used by [backup](backup.md#runtime-usb-requirements).

## SSH

SSH requires both accepted `authorized_keys` and an empty `enable_ssh` marker.
WLAN configuration alone does not enable it. Dropbear is built without server
password authentication. The current administrative connection is root with
public-key authentication. Prefer non-interactive operator access:

```sh
ssh -o BatchMode=yes root@<printer-host> '<read-only-command>'
```

With active persistent root, the Ed25519 host identity is retained under
`/home/fre3nder/.fre3nder/ssh/`. In degraded operation a volatile host key can be
used instead; do not assume host-identity continuity across that boundary or
silently accept an unexpected key. S50 also requires devpts and valid runtime/key
paths. Inspect its status rather than treating service exit zero as readiness.

USB provisioning is an administrative trust input, not an authentication-free
network recovery service. Healthy writable-runtime development and platform
writes have different authorization boundaries in [AGENTS.md](../AGENTS.md).

## Web, Moonraker and camera access

The selected signed application frontend uses Lighttpd on port `80`. Moonraker
and `/webcam/` remain routed there as specified in
[runtime integration](api/runtime.md#http-routing). This frontend has no
Fre3nder Management API route and no access to the management Unix socket.

Maintenance is a separate core Lighttpd listener on port `8081`, disabled by
default and started only after explicit local opt-in. Its UI is:

```text
http://<printer-host>:8081/
```

Temporary browser administration uses pairing, an in-memory session, a CSRF
token and port-8081 origin validation. Current HTTP access does not supply TLS.
The `/home/fre3nder/.fre3nder/web/disabled` opt-out affects only the selected
application frontend; Maintenance has its own independent enable state.

For failures, start with [troubleshooting](troubleshooting.md) and current service
logs/status. The status files are diagnostic implementation state unless a
specific supported indicator is identified in the API reference.
