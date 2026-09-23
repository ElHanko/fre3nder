# Phase 3.4/3.5 fre3nder-x2000 build basis

> Historical bring-up record. For the current build commands and artifact
> contracts, use [the build guide](../../docs/build.md) and
> [`configs/x2000/sources.json`](../../configs/x2000/sources.json).

## 2026-09-20 slot-neutral kernel qualification

The investigated reference Ender-3 V3 KE booted the development Kernel with
SHA-256 `9e1902279d8aaac39bf1ef303e1ff9afdf1a58057c61605d639bd497d6062678`.
The image contained no DT `/chosen/bootargs` or p7/p8 root reference. It was
written to inactive p6 from Stock A and passed complete artifact-length
readback. After selecting B, it booted as `6.6.157-fre3nder` with
`root=/dev/mmcblk0p8` in `/proc/cmdline`; `x2000-ab` reported active p8 and
selector `DEVELOP_B`. The existing boot chain therefore supplied the B root
selection. The same image has not been hardware-qualified from p5/A; that
symmetric case is deferred until an A-side Fre3nder transition is needed.

## Historical persistence cleanup boundary

During the 2026-09-11 Host-MCU/ADXL qualification, the persistent
`printer.cfg` already existed, so the new RootFS-default sections were copied
into it for the controlled test. This was expected seed-once behavior, not an
ADXL or deployment failure. The previously observed `S13mcu_update` whiteout,
disabled copy, and one-shot marker were historical bring-up residue, not the
intended persistence design. Their targeted cleanup was evidence about that
specific old state; direct editing of a mounted OverlayFS upper directory is
not a general recovery procedure.

`fre3nder-x2000-v0` is the first independent build basis after the historical
and reproducible `2026.1.a` prototype. It does not change or replace
`x2000-prototype`, its one-shot rollback semantics, or its evidence chain.

The Develop build is an offline build definition. It does not access a printer,
write a partition, change p1, select an A/B side, deploy an artifact, or
authorize any hardware operation. Manual slot selection is a separate
host-side operator operation described below; it is not part of the build or
the Develop RootFS.

## Current scope

The build uses the pinned public Ingenic X2000 SDK mirror at commit
`a98c2e1f22e4263ddd4153a4eca4db4dcfd2777b`, its Linux 6.6.18 tree with
`localversion-rt` set to `-rt23`, vendored Buildroot 2023.08.3, and the pinned
`mips-gcc720-glibc238` toolchain. The container base and Debian package snapshot
are pinned in `configs/x2000/sources.json`.

The effective preemption model intentionally matches the `2026.1.a` build:

```text
CONFIG_PREEMPT=y
# CONFIG_PREEMPT_RT is not set
```

The kernel release is therefore `6.6.18-rt23`, but this build does not enable
the fully preemptible `CONFIG_PREEMPT_RT` model.

The new KE Device Tree retains the already established CPU/RAM, eMMC, UART,
SDIO WLAN, USB-controller, and watchdog basis. Touch/NS2009, camera, ADXL,
Klipper/F005 services, selector logic, and all smoke-only code are excluded.
Its root command line is:

```text
root=/dev/mmcblk0p8 rootwait rootfstype=squashfs ro
```

The KE WLAN patch copies the power/reset/detect sequence that was hardware
validated on the investigated reference system for `2026.1.a`. Only the
smoke-specific init-function name and comments are generalized. The current
Develop kernel and the Production S20 -> S40 -> S50 administrative path are
**HARDWARE VALIDATED on the investigated reference system**. Stock A uses
kernel p5 and RootFS p7; Develop B uses kernel p6 and RootFS p8.

Phase 3.5 adds the pinned upstream Klipper host and the guarded F005 lifecycle
path. Moonraker, a Web or touchscreen UI, Linux Host-MCU/ADXL, and an open
replacement for `mcu_util` remain excluded. The Phase-3.5 host integration was
exercised on the investigated reference system. The pinned upstream Klippy
runtime identified the qualified Mainline F005 over the passive `/dev/ttyS1`
path, loaded its 88-command
dictionary, transferred the complete printer configuration, reported
`Configured MCU 'mcu' (1024 moves)`, and then maintained live MCU, heater, and
clock statistics without retransmitted or invalid UART bytes during the bounded
qualification run. No G-code, motion, homing, probing, or heating was commanded
during that test.

The qualified Fre3nder image was the investigated F005 build
`?-20260820_092609-29ca4e70a84f`, 22,392 bytes, SHA-256
`5b9678731b10a0f8c6159b3cf2432b1a499d6310b9466419d129dc42242e23ac`.

The qualification boundary is explicit: this is a **QUALIFIED ON DEVICE**
Fre3nder-B host/runtime leg, not a complete print qualification. The exact
Stock-F005 identity, Stock MCU gate, dictionary `reset`, writable
`/run/fre3nder-klipper/printer` input PTY, and actual S60 Klippy startup were
qualified on the investigated reference system. The `/proc/<pid>/cmdline`
stale-PID ownership hardening is **OFFLINE CONFIRMED** by local fixtures.
`FIRMWARE_RESTART` released the UART and reached the exact
Creality bootloader identity `mcu0_001_G32-mcu0_004_000`; the preferred
uninterrupted Fre3nder-to-Stock host-reboot handoff remains **REQUIRES
QUALIFICATION**. Autonomous MCU shutdown clearing is **NOT IMPLEMENTED**.

## Phase 3.5 Klipper host integration

The build fetches exactly
`https://github.com/Klipper3d/klipper.git` at commit
`0499b30374315f2a9f49fc12808527fc7d0f5cfa`, applies only
`patches/klipper/0004-x2000-passive-uart-opt-in.patch` to the host tree, removes
Git metadata, records a source version file, and stages the GPL-3.0-only
runtime source at `/usr/share/klipper`. The historical unconditional `0002`
bring-up patch remains unchanged and is not used by the Develop RootFS.

Buildroot provides Python 3 plus `python-cffi`, `python-greenlet`,
`python-jinja2`, `python-markupsafe`, `python-serial`, and the Python zlib
module. `python-can` and `python-msgspec` are not selected. After Buildroot has
prepared its external X2000 toolchain, the build reads `SOURCE_FILES` from the
pinned Klipper `klippy/chelper/__init__.py` and compiles `c_helper.so` with
`buildroot-output-develop/host/bin/mips-linux-gnu-gcc`. The build and RootFS
checks require ELF32 little-endian MIPS32r2, o32, nan2008, and a normal
`libc.so.6` dependency. The target therefore never compiles the helper at
first startup.

Enabling CFFI also activates Buildroot's `host-libffi`. The pinned Buildroot
recipe disables libffi static executable trampolines only for the target, so
the profile applies
`patches/buildroot/0001-libffi-disable-host-static-exec-tramp.patch` to pass
the same option to `host-libffi`. This is a build-host compatibility fix; it
does not change the target libffi configuration.

The hardware-validated F005 printer baseline is installed unchanged except for
the explicit `[mcu]` option `x2000_passive_uart: True` at
`/etc/klipper/printer.cfg`. Without that option, patched Klipper uses the exact
ordinary upstream `connect_uart()` path. With it, configuration fails unless
the transport is `/dev/ttyS1` at 230400 and non-CAN. The opt-in open uses
`O_RDWR|O_NOCTTY`, nonblocking mode, `flock`, `TIOCEXCL` when available, 8N1,
`CREAD|CLOCAL`, and disabled `HUPCL`; it never uses pyserial, changes RTS/DTR,
probes STK500v2, or switches baud.

`/usr/libexec/fre3nder/f005-mcu-state` performs only bootstrap identify over
that same passive path, loads the dynamic dictionary, compares the exact
version and required `MCU`, `CLOCK_FREQ`, and `SERIAL_BAUD` constants with the
immutable `/usr/share/fre3nder/f005-mcu-release.json`, and closes the session.
It returns `stock`, `fre3nder`, or `unknown`; it never sends `get_config`, a
printer configuration, GPIO, heater, or motion commands.

`S60fre3nder-klipper` starts normal Klippy only for the exact `fre3nder` result.
Stock and unknown identities leave Klippy stopped with a visible runtime
status. PID and fallback logging use `/run/fre3nder-klipper`; when the already
established persistence layer is active, the normal log is
`/persist/userdata/fre3nder/logs/klippy.log`.

Klippy's default input PTY path `/tmp/printer` is not usable on the immutable
read-only RootFS because Klipper creates that path as a symlink to a PTY slave.
The service therefore explicitly supplies
`-I /run/fre3nder-klipper/printer`. This path was qualified on-device during
the Phase-3.5 full-config connection. The service records `starting` before the
fork result is accepted and performs a bounded early-process liveness check;
an immediate Klippy exit is recorded as `startup-failed` instead of `active`.

The separate `/usr/libexec/fre3nder/f005-stock-to-fre3nder` helper is
operator-guided and defaults to dry-run. Before identifying or resetting it
requires active persistence, a regular non-symlink executable BYOF utility at
`/persist/system/fre3nder/vendor/creality/mcu_util` with SHA-256
`d984f1a51ff9149a8971f9a3d3d0db13f81772c8122dd24b53b4d160f223cd03`,
and the exact regular target image, size, and SHA-256 from the immutable release
manifest. Dry-run verifies exact Stock identity and the dictionary `reset`
command but sends no reset and starts no updater. Only `--write` sends one
dictionary-derived reset in that already identified session and closes it. It
then reproduces the historically hardware-qualified Stock-to-Mainline vendor
sequence as three separate invocations: `mcu_util -c`, `mcu_util -g`, and
`mcu_util -u -f <firmware>`. Each invocation must return successfully before
the next is started, and the orchestrator adds neither retry nor delay. After
the update, the helper requires the exact Fre3nder identity. Any failed
pre-reset gate stops before reset. The vendor utility and target firmware are
not embedded in the immutable RootFS.

The exact supported Stock-MCU -> Fre3nder-MCU sequence is **QUALIFIED ON
DEVICE**: exact Stock identity, dictionary-derived exact `reset`, successful
`mcu_util -c`, `-g`, and `-u -f` steps, updater return code 0 with `app_run`,
and an independent exact Fre3nder identity check. This qualifies the MCU
transition only; it does not qualify the complete coordinated host roundtrip.

Run the focused offline fixtures with:

```text
scripts/test-x2000-klipper
```

They apply `0004` against the exact pinned commit and test patch semantics,
identity classification, service gating, transition preflight/order, required
Buildroot selections, c-helper staging logic, and exclusion of `mcu_util`.

### USB host test power prerequisite

Perform Linux USB-host tests only while the pad is powered normally through the
printer. Powering the pad only through its internal Micro-USB connection can
start the SoC and DWC2 root hub while leaving the downstream hub/VBUS path
unavailable. The resulting “root hub only” state can misleadingly look like a
kernel, PHY, or Device Tree failure. The Develop USB result is qualified only
under normal printer power; BootROM USB recovery remains a separate interface.

## WLAN source and license boundary

`configs/x2000/ke-wlan.patch` modifies the pinned Linux SDK's
`ingenic_sdio.c`, `sdhci-ingenic.c`, and `sdhci-ingenic.h`; those files are
governed by the kernel tree's GPL-2.0 `COPYING` terms. The combined patch is
therefore marked `GPL-2.0-only`. Its Device Tree hunk applies to the
project-authored KE DTS copied into the ignored SDK workspace. The patch records
the exact source URL and commit.

The Broadcom/Cypress firmware and NVRAM remain local BYOF inputs with documented
provenance and unresolved redistribution status. Required ignored paths and
hashes are:

| Local input | SHA-256 |
| --- | --- |
| `local/phase3/wifi/brcmfmac43430-sdio.bin` | `60dbb5b77b2c232e513322e0ff4350ab5dab5a9fcad0e26e80a2f089e652d720` |
| `local/phase3/wifi/brcmfmac43430-sdio.txt` | `78fee458ab69c0a66ea462f6d6769e15b36f73582693f4dbb5a0e8e8be3cfb0a` |

The build validates both hashes before use. The files may enter the ignored
local build output but must not be committed or redistributed by this project.
The Develop artifact consumes and embeds no WLAN or SSH credentials.

## Build and artifacts

Run exactly:

```text
scripts/build-x2000
```

For an offline kernel/DTB-only rebuild, run:

```text
scripts/build-x2000 --kernel-only
```

This route does not invoke Buildroot or create a RootFS. It first resets and
cleans the pinned SDK kernel tree, copies the project KE DTS, applies the full
`ke-wlan.patch`, and verifies that the entire patch is present before running
the defconfig, fragment, and `olddefconfig` configuration sequence. Do not copy
the project DTS into an already prepared SDK tree: doing so can overwrite the
patch's DTS hunk while leaving its driver hunks applied.

The kernel-only export is private and ignored at
`local/phase3/fre3nder-x2000-kernel-candidate/`. It contains `kernel.uImage`,
`ender3-v3-ke.dtb`, `effective-kernel-config`, and `SHA256SUMS`. Before export,
the build checks the KE DTB for the WLAN regulator and `wlan-reg-on-gpios`, the
OTG and OTG-PHY enabled state, the p8 root argument, and the established GPC9
active-high VBUS-drive and GPD17 active-low VBUS-detect wiring. Treat a test
artifact as usable only after its configuration and DTB comparison checks pass.

The separately preserved hardware-validated kernel evidence remains under
`local/phase3/fre3nder-x2000-usblan-ncm/`. The preserved validated artifacts are:

- `kernel.uImage`: 4862016 bytes, SHA-256
  `86cc81f2babc53257339f432ae598fce9b7dca685ea8b995767156eae6552b8c`;
- `ender3-v3-ke.dtb`: 28171 bytes, SHA-256
  `f910c82032828283bbee2851a29c816a7e2cb9f76f3e9f2a02951f618083ec15`;
- `effective-kernel-config`: 89196 bytes, SHA-256
  `06cc72c90371ff902beaf4f840ebf028bb78a8a9b877f551ba1af62caa3512cd`.

These identities belong to the preserved USB-host/CDC-NCM hardware-validation
evidence on the investigated reference system. That evidence contains no
`build-manifest.json`, so no project commit or project-worktree state is claimed
for this exact kernel. It also does not establish that this exact kernel was the
one running during the later Production RootFS validation. A rebuild produced
by this command is a new candidate until separately qualified.

For a RootFS-only rebuild after an overlay change, run:

```text
scripts/build-x2000 --rootfs-only
```

It reuses the prepared Buildroot output, re-runs its phony target-finalization
step so the current overlay is copied, and emits only the ignored
`local/phase3/fre3nder-x2000-production-candidate/`
SquashFS, Buildroot config, and checksums. It does not build the kernel. This is
the Production variant: it embeds no SSH key or WLAN configuration and contains
only the S20 provisioning, S40 network, and S50 SSH path. Without a valid USB
provisioning medium, SSH and WLAN fallback are intentionally unavailable. Stock
A and external recovery are unaffected.

The separately preserved hardware-validated Production candidate under
`local/phase3/fre3nder-x2000-production-usb-provisioning-normal-validation/` has size
`2838528` bytes and
SHA-256
`5dd51e8fd471c386f8ba550c95bd14a6134f3cb246b3fbf96a0c1c1fd123860b`.
Its p8 read-back was identical. This identifies the validated artifact; a later
rebuild is a new candidate until separately qualified.

### USB-LAN driver status

**HARDWARE VALIDATED on the investigated reference system:** the USB adapter
enumerates as AX88179B (`0b95:1790`) with CDC-NCM control (`02/0d/00`) and CDC
Data (`0a/00/01`) interfaces. The vendor-specific `ax88179_178a` driver
registers but does not bind in that mode. The built-in `cdc_ncm` driver binds
instead, creates the Ethernet interface, detects carrier, and supports DHCP/IP
operation. Kconfig selects its CDC Ethernet dependency; the vendor-specific
driver remains enabled for adapter modes that use it.

The fetch container may access the pinned public sources. The compiler container
runs with `--network none`. Work and output remain ignored under:

```text
local/phase3/fre3nder-x2000-work/
local/phase3/fre3nder-x2000/
local/phase3/fre3nder-x2000-kernel-candidate/
local/phase3/fre3nder-x2000-production-candidate/
```

The output contract is:

```text
kernel.uImage
rootfs.squashfs
ender3-v3-ke.dtb
effective-kernel-config
buildroot.config
SHA256SUMS
build-manifest.json
```

`rootfs.squashfs` is the only RootFS image and uses XZ compression. JFFS2,
UBIFS, ext2, and tar RootFS outputs are disabled.

Names are build-neutral. The manifest records p6/p8 only as current deployment
compatibility; neither the build nor its RootFS writes those partitions.
`project_commit` records the checked-out `HEAD`; `project_worktree_status`
records whether Git reported `clean` or `dirty` inputs. A `dirty` artifact must
not be treated as built exclusively from its recorded `HEAD` commit.

## Boot-local administrative path

`CONFIG_BLK_DEV_INITRD=y` with an empty `CONFIG_INITRAMFS_SOURCE` includes only
the kernel tree's default early cpio list: `/dev`, `/dev/console`, and `/root`.
It contains no `/init`; the system therefore continues to mount p8 as its normal
SquashFS RootFS. The p8 RootFS likewise does not add `/init`. This addresses the
previously observed initial-console warning without creating a RAM-root build.

After devtmpfs is available, the BusyBox `inittab` creates `/dev/pts` before
mounting devpts. This addresses the separately observed PTY mount failure.

The normal Develop artifact contains `wpa_supplicant` with the nl80211 backend,
a long-lived BusyBox `udhcpc`, and Dropbear compiled without server password
authentication. It contains no WLAN credentials, authorized keys, private keys,
persistent Dropbear host keys, selector helper, or eMMC p9/p10 logic.

The pinned Buildroot package definitions provide wpa_supplicant 2.10
(BSD-3-Clause), Dropbear 2022.83 (the licenses recorded by Buildroot), and
BusyBox 1.36.1 (GPL-2.0 plus its recorded bzip2 component license). Exact
versions, package-source role, and license identifiers are recorded in the
build manifest; no package source or binary is committed to this repository.

At boot, after mdev, the production provisioning script scans USB mass-storage
block devices for up to ten seconds. Each candidate is qualified by an explicit
read-only `vfat` mount; it does not depend on BusyBox `blkid` reporting a
filesystem type. A mounted volume is considered only when it contains at least
one of these files in its root:

```text
wpa_supplicant.conf
authorized_keys
enable_ssh
```

The USB filesystem is mounted read-only with `nosuid`, `nodev`, and `noexec`.
Recognized entries must be regular files and must not be symlinks. If more than
one volume contains recognized entries, all are refused rather than selecting
one arbitrarily. Valid inputs are copied with restrictive permissions to
`/run/fre3nder-x2000/provisioning/`, and the USB filesystem is unmounted before
network startup. `wpa_supplicant.conf` and `authorized_keys` are each limited
to 64 KiB; `enable_ssh` is valid only as an empty regular file. Nothing is
written to the USB medium, SquashFS, p1, p9, or p10.

### Development persistence

**HARDWARE VALIDATED for first-boot persistence on the investigated reference
system:** the Development-only `S09fre3nder-x2000-storage` adapter finds exactly
one external USB partition labelled `FRE3NDERDATA`, validates its real
non-symlink `/p9` and `/p10` directories, and mounts it as ext4 with `rw`,
`nosuid`, and `nodev`. It then binds those two Development sources to the stable
internal interface:

```text
/persist/system
/persist/userdata
```

At boot, S09 waits up to 10 seconds for USB mass-storage enumeration, which was
observed to finish after S09 on the reference system. It rescans about once per
second only while no matching volume is present. Multiple matching volumes
still fail closed immediately. This bounded wait belongs only to the
Development storage adapter and is not part of the final `/persist` contract.

The wait was added after a concrete first hardware boot reached S09 before USB
mass-storage enumeration had completed. S09 reported `no-volume`, S10 reported
`missing-persistence`, and S50 used its volatile host key; the USB disk appeared
later in that same boot. Only S09 changed: S10, S50, and the init ordering kept
their existing functional contracts. With the corrected RootFS, hardware
validation reported both the S09 storage adapter and S10 final persistence as
`active`, with `/persist/system` and `/persist/userdata` both mounted from:

```text
FRE3NDERDATA:/p9  -> /persist/system
FRE3NDERDATA:/p10 -> /persist/userdata
```

`S10fre3nder-persistence` has no USB, label, partition, or Development-storage
knowledge. It consumes only those two paths, requires both to be mounted, and
provides the current final directories for SSH identity, operator-staged F005
firmware/vendor inputs, and Klippy logs below `/persist/system/fre3nder/` and
`/persist/userdata/fre3nder/`.
No matching Development volume is non-fatal; multiple matching volumes, mount
failure, or an invalid source layout leave the final persistence layer
unavailable. The Development adapter never references, mounts, or writes the
eMMC p9 or p10 partitions.

The p9 role is nevertheless shared across modes on the investigated reference
system: the Development p9 source supplies `/persist/system`, while Stock A
uses p9 as its writable OverlayFS backing store. Fre3nder owns only its
designated `/fre3nder/` namespace, exposed as `/persist/system/fre3nder/`; it
must not mutate Stock overlay paths such as `/upper/etc/...`. The historical
`S13mcu_update` whiteout and disabled-copy state was bring-up residue, not the
intended persistence design, and does not make direct upper-directory editing
a general recovery procedure.

S50 uses only the final `/persist/system/fre3nder/ssh/` interface for its
optional persistent Ed25519 host key. On the first successful hardware boot
with active persistence, it created
`/persist/system/fre3nder/ssh/dropbear_ed25519_host_key` as a regular file with
mode `0600`, and Dropbear used that path rather than the volatile `/run` path.
On 2026-08-28, a normal Develop-B -> Develop-B reboot reused that same file:
S09 and S10 were again `active`, both stable `/persist` interfaces were mounted,
and Dropbear was verified to start with that exact path and to present its key
over SSH. The system remained on p8 with the valid `DEVELOP_B` selector, and
non-interactive public-key SSH became available again automatically. The
USB-provisioned `authorized_keys` file remains boot-local under `/run` and is
still bind-mounted over `/root/.ssh`; it is not persisted. Without active final
persistence, S50 retains the existing per-boot volatile host-key path.

An eMMC backend is not implemented or authorized. A later backend may provide
the same `/persist/system` and `/persist/userdata` interface without changing
S10 or its consumers.

### Network policy

The boot-time policy is Ethernet-first with WLAN fallback; it never starts both
paths in parallel. “Ethernet available” means exactly one suitable non-wireless
ARPHRD_ETHER interface, carrier detected within five seconds, and a DHCP lease
received within 15 seconds. The `udhcpc` hook writes the selected interface to
the volatile `/run/fre3nder-x2000/network/lease` marker only after it configured
the address, default route, and resolver state. On no carrier or no matching
lease, S40 stops DHCP, deconfigures and brings down Ethernet, then considers the
unchanged boot-local WLAN configuration.

When WLAN is the fallback, the script selects the single exposed wireless
interface, starts `wpa_supplicant`, and waits at most 30 seconds for
association. It then starts BusyBox `udhcpc` as a long-lived foreground client
managed in the background by the init script. Its `deconfig`, `bound`, and
`renew` actions maintain the interface, default route, and volatile resolver
state; its PID file and lease marker are under `/run`.

There is no runtime failover or hotplug monitoring in this development state;
the selection is made once at boot.

S50 starts Dropbear only when both a syntactically bounded public
`authorized_keys` file and the empty `enable_ssh` marker were accepted. It also
refuses startup unless devpts is mounted. The key is copied to volatile runtime
state and exposed through a boot-local bind mount over `/root/.ssh`; no key is
placed in SquashFS. The SSH server uses public-key authentication only. Without
active final persistence, it generates an Ed25519 host key under
`/run/fre3nder-x2000/dropbear/` for the current boot.

**HARDWARE VALIDATED on the investigated reference system:** S20 imported the
USB public key and marker, S40 provided Ethernet-first networking with WLAN
fallback, and S50 started Dropbear. Login with the USB-provisioned public key
succeeded. The earlier failure was caused solely by passing `-s` to the built
Dropbear 2022.83, whose `-s` option is absent when server password and PAM
authentication are compiled out. S50 therefore starts it as
`"$dropbear" -r "$hostkey" -P "$pid_file"`; password authentication remains
compile-time disabled. No embedded user key is part of Production; S50 is the
sole Production SSH init service.

Without active final persistence, the normal-path host key changes after every
reboot. With active Development persistence, its cross-boot reuse is qualified
only for the investigated Development USB-adapter Develop-B -> Develop-B path.
Persistent general configuration remains **PLANNED / NOT IMPLEMENTED**.

## Separate manual A/B operator path

The host-side `scripts/x2000-ab` tool implements the deliberately manual slot
selector independently of BUILD and DEPLOY:

```text
scripts/x2000-ab <printer-host> status
scripts/x2000-ab <printer-host> select-a
scripts/x2000-ab <printer-host> select-b
```

The tool uses only the already qualified exact records:

| Classification | First 512 bytes | SHA-256 |
| --- | --- | --- |
| `STOCK_A` | `ota:kernel\n\n` plus 500 NUL bytes | `ba68d7c969bfee94216c94768ec65545cf36cb352303ab55231c78e78b51ce6b` |
| `DEVELOP_B` | `ota:kernel2\n\n` plus 499 NUL bytes | `29a335bc1f2935f9ee79955da3566d5f70d1b0591421745395fd714c8351bdc4` |

`status` is read-only. It reports the active root selected by the single
`root=` kernel argument, verifies that the `ota` partlabel resolves to partition
1 at `/dev/mmcblk0p1`, checks the established 2048-sector p1 size, reads the
first 512 bytes, and reports their SHA-256 classification as `STOCK_A`,
`DEVELOP_B`, or `UNKNOWN`. An unknown selector or unexpected partition layout
is never repaired.

`select-b` is valid only while the active root is Stock p7 and p1 contains the
exact qualified Stock-A record. `select-a` is valid only while the active root
is Develop p8 and p1 contains the exact qualified Develop-B record. For either
operation the tool creates the target 512-byte record locally, verifies its
known SHA-256, rechecks the active-root and p1 identities and sizes on the
target, writes exactly one 512-byte p1 record, runs `sync`, and verifies the
read-back hash. It performs no automatic retry or reboot and never writes p5,
p6, p7, p8, p9, or p10.

Invoking either `select-*` command requests a persistent p1 hardware write.
Every real invocation therefore still requires separate explicit operator
authorization under `AGENTS.md`; the offline implementation and fixture tests
do not grant that authorization.

### Develop RootFS deployment orchestrator

`scripts/deploy-x2000-rootfs <develop-host> <stock-host>` is a
read-only preflight. It verifies the already-built Production candidate at
`local/phase3/fre3nder-x2000-production-candidate/`: `rootfs.squashfs`,
`SHA256SUMS`, and `buildroot.config`. It checks both manifest entries, the
candidate checksum, and that the RootFS is strictly smaller than the established
p8 capacity. It then verifies that Develop is running p8 and the selector is
one of the two known records, `STOCK_A` or `DEVELOP_B`. It does not build and
performs no printer-side writes, selector changes, or reboots.

`scripts/deploy-x2000-rootfs <develop-host> <stock-host> --write` is
the explicit authorization boundary for one persistent B -> A -> B deployment
sequence. It accepts either known Develop p8 with `STOCK_A` or `DEVELOP_B`, or
an already-running Stock p7 with `STOCK_A`. From Develop, an initial
`DEVELOP_B` is first changed with `x2000-ab select-a` and read-only verified as
p8 plus `STOCK_A`; an initial `STOCK_A` needs no selector change. It then
reboots B and pauses for the operator to finish the Stock-A boot, manually
enable Stock SSH, and press ENTER. An already-running valid Stock A skips only
that first reboot and operator pause. Both paths require the full Stock p7,
exact Stock-A selector, and unmounted, correctly mapped p8 checks before any p8
write. The orchestrator writes only
`rootfs.squashfs` to p8, runs `sync`, and verifies a full RootFS artifact
read-back SHA-256 before invoking `x2000-ab select-b`. It then reboots Stock and
pauses again until the operator confirms the Develop boot with ENTER. Only then
does it require p8 plus the resulting `DEVELOP_B` selector. While still running
Develop p8, it invokes `x2000-ab select-a` and requires the final state to be p8
plus `STOCK_A`. SSH uses BatchMode and the normal host-key policy; it does not
disable host-key checking.

This orchestrates established selector and RootFS operations and does not
broaden their qualification beyond the exact candidate and sequence recorded
below. The default preflight remains read-only. `--write` does not authorize
unrelated partition, kernel, selector, or printer changes.

**HARDWARE VALIDATED on 2026-08-27:** the last deployed RootFS candidate was
2,838,528 bytes with SHA-256
`c34eb06b0a01abd03844a76c1a3da7825a89cdaf7c84670b91b1ca031b073e3f`.
The complete operator-controlled sequence passed:

```text
Develop p8 + STOCK_A
-> Stock A
-> p8 RootFS write
-> complete RootFS artifact read-back PASS
-> select-b
-> Develop p8 + DEVELOP_B
-> select-a
-> final Develop p8 + STOCK_A
-> B -> A -> B deployment PASS
```

The operator pauses after each orchestrated reboot are part of this validated
workflow because Stock SSH must be enabled manually after boot. A safely
aborted run can resume from already-running Stock p7 plus `STOCK_A`; that path
skips the initial reboot, selector write, and operator pause before applying the
same complete Stock-state checks.

The retained Prototype smoke systems and Develop intentionally differ:

```text
Prototype Slot B: early userspace automatically restores B -> A
Develop tool policy: no automatic B -> A; Develop-B -> Develop-B reboot is
                     qualified on the investigated reference system
```

There is no selector daemon, boot-local p1 reset, or automatic Stock fallback
in the Develop RootFS. If B has been selected and Develop becomes unreachable,
the recovery boundary is the already qualified external Ingenic USB /
RAM-U-Boot p1 reset. That qualification covers the bounded p1 selector path; it
does not prove complete Stock-firmware recovery.

Successful offline construction establishes build reproducibility and static
artifact properties; it does not transfer hardware qualification to a different
artifact. The identified Production candidates are hardware-validated within
their separately recorded scopes: Develop-B boot, USB provisioning,
Ethernet-first/WLAN-fallback networking, public-key SSH, the complete RootFS
deployment sequence, Development persistent SSH identity across a normal
Develop-B -> Develop-B reboot, and SSH availability after that reboot. This
qualification remains limited to the investigated Development USB-adapter path.
Runtime/hotplug network failover and final printer-service integration remain
**PLANNED / NOT IMPLEMENTED**. The manual A/B tool remains separately scoped to
its own documented validation and authorization boundary.
