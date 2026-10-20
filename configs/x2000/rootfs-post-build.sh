#!/bin/sh
set -eu

target=$1
ota_public_key=${FRE3NDER_OTA_PUBLIC_KEY:?FRE3NDER_OTA_PUBLIC_KEY is required}
factory_seed=${FRE3NDER_FACTORY_FRE3NDERSCREEN_APP:?FRE3NDER_FACTORY_FRE3NDERSCREEN_APP is required}
linux_firmware_license="$BUILD_DIR/linux-firmware-20250211/LICENCE.cypress"
system_app_seeds=${FRE3NDER_SYSTEM_APP_PACKAGES_DIR:-}
system_target="$target/usr/share/fre3nder/system-apps"
# Always discard stale seeds from reused Buildroot target directories.
rm -rf -- "$system_target"
install -d -m 0755 "$system_target"
if [ -n "$system_app_seeds" ]; then
    [ -d "$system_app_seeds" ] && [ ! -L "$system_app_seeds" ] || {
        echo 'System-app seed directory is invalid' >&2; exit 1;
    }
    for seed in "$system_app_seeds"/*.fre3app; do
        [ -e "$seed" ] || continue
        [ -f "$seed" ] && [ ! -L "$seed" ] || {
            echo 'System-app seed must be a regular non-symlink file' >&2; exit 1;
        }
        case "${seed##*/}" in
          *[!a-z0-9_.-]*|.*|*.fre3app.fre3app)
              echo 'Invalid system-app seed filename' >&2; exit 1 ;;
        esac
        install -m 0644 "$seed" "$system_target/${seed##*/}"
    done
fi

[ -f "$factory_seed" ] && [ ! -L "$factory_seed" ] || {
	echo 'Fre3nderScreen factory app must be a regular non-symlink file' >&2
	exit 1
}
install -D -m 0644 "$factory_seed" \
	"$target/usr/share/fre3nder/factory-apps/fre3nderscreen.fre3app"

[ -f "$linux_firmware_license" ]
install -D -m 0644 "$linux_firmware_license" \
	"$target/usr/share/licenses/linux-firmware/LICENCE.cypress"

# The immutable RootFS must never retain the old Moonraker runtime.
rm -rf -- "$target/opt/fre3nder/moonraker" "$target/opt/fre3nder/moonraker-env"
[ -f "$system_target/moonraker.fre3app" ] &&
    [ ! -L "$system_target/moonraker.fre3app" ] || {
    echo 'Required signed Moonraker system-app seed is missing' >&2
    exit 1
}

# Development Buildroot output may be reused. Remove obsolete embedded display
# paths so stale target trees cannot retain a legacy RootFS component.
rm -rf -- \
	"$target/etc/init.d/S64fre3nder-guppyscreen" \
	"$target/opt/fre3nder/guppyscreen" \
	"$target/usr/share/fre3nder/defaults/guppyconfig.json" \
	"$target/usr/share/guppyscreen" \
	"$target/usr/share/licenses/guppyscreen" \
	"$target/opt/fre3nder/fre3nderscreen" \
	"$target/usr/share/fre3nderscreen" \
	"$target/usr/share/licenses/fre3nderscreen" \
	"$target/usr/share/fre3nder/defaults/fre3nderscreen.json" \
	"$target/etc/init.d/S64fre3nderscreen"

for obsolete in \
	"$target/etc/init.d/S64fre3nder-guppyscreen" \
	"$target/opt/fre3nder/guppyscreen" \
	"$target/usr/share/fre3nder/defaults/guppyconfig.json" \
	"$target/usr/share/guppyscreen" \
	"$target/usr/share/licenses/guppyscreen"
do
	[ ! -e "$obsolete" ]
done

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
# Local root access is an operator opt-in, never an immutable image default.
rm -f "$target/etc/fre3nder/console.enabled"

mdev_conf="$target/etc/mdev.conf"
touch "$mdev_conf"

disk_rule='-sd[a-z] 0:0 0660 */usr/libexec/fre3nder/usb hotplug'
partition_rule='-sd[a-z][0-9][0-9]* 0:0 0660 */usr/libexec/fre3nder/usb hotplug'
mdev_tmp="$mdev_conf.fre3nder"

awk -v disk="$disk_rule" -v partition="$partition_rule" '
    # Replace the first-match Buildroot input rule in place, also on reruns.
    $1 == "input/event[0-9]+" {
        $0 = "input/event[0-9]+ 0:1001 660"
    }

    $0 == disk || $0 == partition {
        next
    }

    !inserted && /^\$MODALIAS=/ {
        print disk
        print partition
        inserted = 1
    }

    {
        print
    }

    END {
        if (!inserted) {
            print disk
            print partition
        }
    }
' "$mdev_conf" > "$mdev_tmp"

mv "$mdev_tmp" "$mdev_conf"
grep -Fxq 'input/event[0-9]+ 0:1001 660' "$mdev_conf" || {
	echo 'Fre3nder: expected mdev input permissions rule missing' >&2
	exit 1
}

# Remove competing/stale init paths that must not survive incremental assembly.
rm -f "$target/etc/init.d/S50lighttpd"

chmod 0755 \
	"$target/usr/bin/fre3nder" \
	"$target/usr/libexec/fre3nder/managementd" \
	"$target/usr/libexec/fre3nder/package-core" \
	"$target/usr/libexec/fre3nder/console" \
	"$target/usr/libexec/fre3nder/ota-core" \
	"$target/usr/libexec/fre3nder/usb" \
	"$target/etc/init.d/fre3nder-root" \
	"$target/etc/init.d/S20fre3nder-provision" \
	"$target/etc/init.d/S30fre3nder-user" \
	"$target/etc/init.d/S40fre3nder-network" \
	"$target/etc/init.d/S50dropbear" \
	"$target/etc/init.d/S57fre3nder-management" \
	"$target/etc/init.d/S58fre3nder-app-restore" \
	"$target/etc/init.d/S58fre3nder-system-apps" \
	"$target/etc/init.d/S59fre3nder-klipper-mcu" \
	"$target/etc/init.d/S60fre3nder-klipper" \
	"$target/etc/init.d/S61fre3nder-moonraker" \
	"$target/etc/init.d/S62fre3nder-maintenance-web" \
	"$target/etc/init.d/S62fre3nder-web" \
	"$target/etc/init.d/S63fre3nder-camera" \
	"$target/etc/init.d/S63fre3nder-factory-app" \
	"$target/etc/init.d/S64fre3nder-display" \
	"$target/etc/init.d/S65fre3nder-app-runtime" \
	"$target/usr/libexec/fre3nder/f005-mcu-state" \
	"$target/usr/libexec/fre3nder/f005-stock-to-fre3nder" \
	"$target/usr/libexec/fre3nder/udhcpc"
