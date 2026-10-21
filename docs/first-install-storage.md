# First installation: prepare the external USB stick

Fre3nder's first-installation storage preparation runs **on a Linux build/admin
host with the USB stick plugged into that host**, not on the printer. It does
not deploy a Kernel/RootFS, change the printer's eMMC, or flash the F005 MCU.
The only supported storage target in this first version is an entire USB disk.

## Partition layout

| Partition | Size | Filesystem | Label | Purpose |
| --- | --- | --- | --- | --- |
| 1 | 300 MiB | ext4 | `FRE3NDERSYS` | Root OverlayFS persistence (`upper`/`work`) |
| 2 | 6 GiB | ext4 | `FRE3NDERHOME` | Persistent `/home` and application data |
| 3 | Remaining space (at least 128 MiB) | FAT32 | `X2000DEV` | Boot-local provisioning |

The previous development stick used a different layout: a 256 MiB FAT volume,
300 MiB SYS, and the remaining approximately 6.7 GiB for HOME. The new layout
uses a fixed 6 GiB HOME size. The tool needs a USB disk of at least 6,574 MiB,
uses an MBR partition table and leaves a 1 MiB alignment offset. It changes
**all** partitions and filesystems on that USB disk.

The current `fre3nder-root` init script finds SYS and HOME by their exact
filesystem labels, not their partition numbers. The existing
`S20fre3nder-provision` scans FAT volumes independently of their partition
position. On first boot it can read optional `wpa_supplicant.conf`,
`authorized_keys` and an empty `enable_ssh` file from the **root of the FAT
partition**, using its existing validity checks. The FAT partition is not
an automatically mounted general-purpose data volume when it shares a disk
with Fre3nder persistence (`S90fre3nder-usb` deliberately excludes that disk).
Wi-Fi credentials placed there are in plaintext and should be protected.

## Run from the Linux host

Identify the **whole USB disk**, not an individual partition:

```sh
lsblk -d -o NAME,TRAN,SIZE,MODEL,SERIAL
lsblk -o NAME,TYPE,FSTYPE,LABEL,SIZE,MOUNTPOINTS
```

Review its identity and unmount all of its partitions. The script rejects
non-USB disks, mounted filesystems, mapped descendants, small disks and
non-512-byte logical sectors. It never guesses the device or unmounts it.

From the Fre3nder repository, inspect the plan without writing:

```sh
scripts/prepare-first-install-storage --device /dev/sdX
```

If the disk shown is correct, **explicitly authorize its erasure**:

```sh
sudo scripts/prepare-first-install-storage --device /dev/sdX --write
```

The command asks you to type `ERASE /dev/sdX` using the *actual* whole-disk
path. It checks the disk again before overwriting its partition table. It uses
`lsblk`, `sfdisk`, `partprobe`, `udevadm`, `mkfs.ext4`, `mkfs.vfat`, `blkid`
(from Debian packages such as `util-linux`, `parted`, `e2fsprogs`,
`dosfstools` and `udev`). After formatting, it checks the filesystem types
and labels and reports `USB_STORAGE_PREPARE=PASS` only if all match.

**Destructive operation:** every existing partition and all data on the
selected USB disk are overwritten. Back up anything needed before using
`--write`. If provisioning fails partway through, the stick may be only
partially prepared. Do not proceed to printer installation until it passes.

For Wi-Fi/SSH provisioning, mount the newly created FAT partition on the host
and place the required files in its root, then unmount safely and move the USB
stick to the printer. The script does **not** create Wi-Fi credentials for you.

This is only the **storage-preparation** step. Confirm that the prepared
USB stick is connected to the Stock printer before deploying. For the qualified
Stock A reference state, use the existing A/B deployment with `--from-stock`:

```sh
scripts/deploy-x2000 <printer-host> --from-stock
# Only after separately authorizing installation on this printer:
scripts/deploy-x2000 <printer-host> --from-stock --write
```

The first command is read-only; the second writes and activates the inactive
Kernel/RootFS pair and reboots the printer. The source and USB persistence must
pass the remote gates before any partition write. Stock p5/p7 are retained.
No F005 MCU firmware is flashed by the host deployment itself.
