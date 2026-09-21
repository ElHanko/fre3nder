#!/bin/sh
set -eu

target=$1
ota_public_key=${FRE3NDER_OTA_PUBLIC_KEY:?FRE3NDER_OTA_PUBLIC_KEY is required}
linux_firmware_license="$BUILD_DIR/linux-firmware-20250211/LICENCE.cypress"

[ -f "$linux_firmware_license" ]
install -D -m 0644 "$linux_firmware_license" \
	"$target/usr/share/licenses/linux-firmware/LICENCE.cypress"

moonraker_root="$target/opt/fre3nder/moonraker"
moonraker_transport_git="$moonraker_root/.fre3nder-git"
moonraker_git="$moonraker_root/.git"
[ -d "$moonraker_transport_git" ]
rm -rf -- "$moonraker_git"
mv "$moonraker_transport_git" "$moonraker_git"
[ -d "$moonraker_git" ]
[ ! -e "$moonraker_transport_git" ]

rm -rf -- "$target/persist"
rm -f -- \
	"$target/etc/init.d/S09fre3nder-storage" \
	"$target/etc/init.d/S10fre3nder-persistence"
install -d -m 0755 "$target/home" "$target/rom" "$target/mnt/fre3nder-root"
install -D -m 0644 "$ota_public_key" "$target/ota/keys/public.pem"
install -d -m 0755 "$target/ota/packages"
install -d -m 0700 "$target/root/.ssh"
ln -snf ../run/fre3nder/resolv.conf "$target/etc/resolv.conf"
rm -f "$target/etc/wpa_supplicant.conf"
# Buildroot installs this competing autostart; S62 is the sole web start path.
rm -f "$target/etc/init.d/S50lighttpd"

chmod 0755 \
	"$target/usr/bin/fre3nder" \
	"$target/etc/init.d/fre3nder-root" \
	"$target/etc/init.d/S20fre3nder-provision" \
	"$target/etc/init.d/S40fre3nder-network" \
	"$target/etc/init.d/S50dropbear" \
	"$target/etc/init.d/S59fre3nder-klipper-mcu" \
	"$target/etc/init.d/S60fre3nder-klipper" \
	"$target/etc/init.d/S61fre3nder-moonraker" \
	"$target/etc/init.d/S62fre3nder-web" \
	"$target/etc/init.d/S63fre3nder-camera" \
	"$target/etc/init.d/S64fre3nder-guppyscreen" \
	"$target/usr/libexec/fre3nder/f005-mcu-state" \
	"$target/usr/libexec/fre3nder/f005-stock-to-fre3nder" \
	"$target/usr/libexec/fre3nder-udhcpc"
