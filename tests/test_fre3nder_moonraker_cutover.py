#!/usr/bin/env python3
"""Static guards for the image-seeded Moonraker cutover (no device required)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "configs/x2000/rootfs-overlay/usr/libexec/fre3nder/package-core"
S61 = ROOT / "configs/x2000/rootfs-overlay/etc/init.d/S61fre3nder-moonraker"
ENTRY = ROOT / "build/x2000/entrypoint.sh"
POST = ROOT / "configs/x2000/rootfs-post-build.sh"


class MoonrakerCutoverTests(unittest.TestCase):
    def test_image_uses_seed_not_checkout(self):
        entry = ENTRY.read_text()
        self.assertIn('extra_overlay="$klipper_overlay"', entry)
        self.assertNotIn('extra_overlay="$klipper_overlay $moonraker_overlay"', entry)
        self.assertIn('moonraker.fre3app', entry)
        self.assertIn('rootfs_components', entry)
        post = POST.read_text()
        self.assertIn('moonraker.fre3app', post)
        self.assertIn('rm -rf -- "$target/opt/fre3nder/moonraker"', post)
        self.assertNotIn('moonraker_transport_git', post)

    def test_s61_only_starts_app(self):
        s = S61.read_text()
        self.assertIn('service-start moonraker', s)
        self.assertIn('service-status moonraker', s)
        self.assertIn('service-stop moonraker', s)
        self.assertIn('prepare_printer_data()', s)
        self.assertNotIn('start-stop-daemon', s)
        self.assertNotIn('moonraker-env', s)

    def test_core_supports_ordered_service_and_warm_update(self):
        core = CORE.read_text()
        self.assertIn('def service_command(', core)
        self.assertIn('service-start', core)
        self.assertIn('service-status', core)
        self.assertIn('verified["autostart"] or was_running', core)


if __name__ == "__main__":
    unittest.main()
