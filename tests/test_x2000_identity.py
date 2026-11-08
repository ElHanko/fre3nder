#!/usr/bin/env python3
"""OS identity and real interactive shell fixtures; no firmware build or SSH."""

import os
from pathlib import Path
import pwd
import shlex
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/x2000"
PROFILE = CONFIG / "rootfs-overlay/etc/profile.d/fre3nder.sh"
HOOK = (CONFIG / "rootfs-post-build.sh").read_text().split(
    "# Set the OS identity after ", 1
)[1].split("system_app_seeds=", 1)[0]
HOOK = "# Set the OS identity after " + HOOK
BUSYBOX = shutil.which("busybox")


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name)
        for directory in ("etc", "usr/lib", "usr/share/fre3nder"):
            (self.target / directory).mkdir(parents=True)
        self.version_file = self.target / "usr/share/fre3nder/VERSION"

    def assemble_identity(self, version):
        self.version_file.write_text(version + "\n")
        subprocess.run(["sh", "-eu", "-c", 'target=$1\n' + HOOK,
                        "identity-fixture", str(self.target)], check=True,
                       capture_output=True, text=True)

    def assert_identity(self, version):
        release = self.target / "usr/lib/os-release"
        # Parse with a shell, as runtime consumers do, including quoted fields.
        result = subprocess.run([
            "sh", "-eu", "-c",
            '. "$1"; printf "%s\\n" "$NAME" "$ID" "$VERSION" "$VERSION_ID" "$PRETTY_NAME"',
            "release-fixture", str(release),
        ], check=True, capture_output=True, text=True)
        self.assertEqual(result.stdout.splitlines(), [
            "FRE3NDER", "fre3nder", version, version, f"FRE3NDER {version}"])
        self.assertEqual((self.target / "etc/os-release").readlink(),
                         Path("../usr/lib/os-release"))
        self.assertEqual((self.target / "etc/os-release").read_bytes(), release.read_bytes())
        self.assertEqual(release.stat().st_mode & 0o777, 0o644)
        banner = f"Welcome to FRE3NDER {version}\n"
        self.assertEqual((self.target / "etc/issue").read_text(), banner)
        self.assertEqual((self.target / "etc/issue.net").read_text(), banner)
        self.assertEqual((self.target / "etc/issue.net").readlink(), Path("issue"))
        self.assertEqual(self.version_file.read_text(), version + "\n")

    def test_fresh_and_incremental_assembly_follow_canonical_version(self):
        version = (ROOT / "VERSION").read_text().strip()
        self.assemble_identity(version)
        self.assert_identity(version)
        # Simulate target-finalize regenerating Buildroot data in a reused tree.
        for name in ("usr/lib/os-release", "etc/issue"):
            (self.target / name).write_text("Buildroot stale-version\n")
        # A subsequent VERSION change must propagate without a clean RootFS.
        self.assemble_identity("2031.2.3.rc")
        self.assert_identity("2031.2.3.rc")
        self.assemble_identity("2031.2.3.rc")
        self.assert_identity("2031.2.3.rc")

    def test_stale_regular_etc_release_and_symlinked_vendor_release(self):
        (self.target / "etc/os-release").write_text("NAME=Buildroot\n")
        untouched = self.target / "old-release"
        untouched.write_text("old metadata\n")
        (self.target / "usr/lib/os-release").symlink_to(untouched)
        (self.target / "etc/issue.net").write_text("Welcome to Buildroot\n")
        self.assemble_identity("2031.2")
        self.assert_identity("2031.2")
        self.assertEqual(untouched.read_text(), "old metadata\n")

    def test_missing_canonical_version_fails(self):
        result = subprocess.run(["sh", "-eu", "-c", 'target=$1\n' + HOOK,
                                 "identity-fixture", str(self.target)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.target / "usr/lib/os-release").exists())

    def profile_fixture(self, name="FRE3NDER"):
        release = self.target / "etc/os-release"
        release.write_text(f"NAME={name}\n")
        profile = self.target / "profile.sh"
        # Redirect only the data path; execute the shipped profile logic intact.
        profile.write_text(PROFILE.read_text().replace("/etc/os-release", shlex.quote(str(release))))
        return profile

    def test_noninteractive_shell_preserves_prompt_and_environment(self):
        profile = self.profile_fixture()
        subprocess.run(["sh", "-eu", "-c",
                        'PS1=original; NAME=original; . "$1"; '
                        '[ "$PS1" = original ] && [ "$NAME" = original ]',
                        "profile-fixture", str(profile)], check=True,
                       capture_output=True, text=True)

    @unittest.skipUnless(BUSYBOX, "host BusyBox is required for interactive prompt tests")
    def test_interactive_user_prompt_uses_os_name_without_changing_hostname(self):
        if os.geteuid() == 0:
            self.skipTest("requires an ordinary user")
        before = os.uname().nodename
        user = pwd.getpwuid(os.getuid()).pw_name
        for name in ("FRE3NDER", "FixtureOS"):
            with self.subTest(name=name):
                profile = self.profile_fixture(name)
                result = subprocess.run([BUSYBOX, "ash", "-i"],
                                        input=f". {shlex.quote(str(profile))}\nexit\n",
                                        capture_output=True, text=True, check=True)
                self.assertIn(f"{user}@{name}$ ", result.stderr)
        self.assertEqual(os.uname().nodename, before)

    @unittest.skipUnless(BUSYBOX, "host BusyBox is required for interactive prompt tests")
    def test_interactive_root_prompt(self):
        prefix = []
        if os.geteuid() != 0:
            unshare = shutil.which("unshare")
            if not unshare:
                self.skipTest("requires root or a user namespace")
            prefix = [unshare, "--user", "--map-root-user"]
            probe = subprocess.run(prefix + [BUSYBOX, "id", "-u"], capture_output=True)
            if probe.returncode:
                self.skipTest("unprivileged user namespaces are unavailable")
        profile = self.profile_fixture()
        result = subprocess.run(prefix + [BUSYBOX, "ash", "-i"],
                                input=f". {shlex.quote(str(profile))}\nexit\n",
                                capture_output=True, text=True, check=True)
        self.assertIn("root@FRE3NDER# ", result.stderr)

    def test_network_hostname_and_banner_configuration(self):
        fragment = (CONFIG / "buildroot.fragment").read_text().splitlines()
        self.assertIn('BR2_TARGET_GENERIC_HOSTNAME="fre3nder"', fragment)
        self.assertIn('BR2_TARGET_GENERIC_ISSUE="Welcome to FRE3NDER"', fragment)
        self.assertIn("CONFIG_FEATURE_EDITING_FANCY_PROMPT=y",
                      (CONFIG / "busybox.fragment").read_text().splitlines())


if __name__ == "__main__":
    unittest.main()
