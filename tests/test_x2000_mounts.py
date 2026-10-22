"""Host-only Docker argument fixtures: no containers, builds or signing keys."""

import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
INPUT_TOOL = ROOT / 'scripts/x2000-build-input-sha256'
inputs = runpy.run_path(str(INPUT_TOOL))


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL)


def make_project(base):
    project = base / 'project'
    selected = inputs['SNAPSHOT_INPUTS']
    for name in git(ROOT, 'ls-files', '-z').decode().split('\0'):
        if name and any(name == p or name.startswith(p + '/') for p in selected):
            target = project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
    (project / '.gitignore').write_text('/local/\n')
    # Real firmware identity checks, with harmless synthetic bytes.
    firmware = project / 'local/production/artifacts/x2000/f005/klipper-f005-mainline.bin'
    firmware.parent.mkdir(parents=True)
    firmware.write_bytes(b'firmware fixture')
    release_path = project / 'configs/x2000/f005-mcu-release.json'
    release = json.loads(release_path.read_text())
    release['fre3nder_release']['firmware'].update(size=firmware.stat().st_size,
        sha256=hashlib.sha256(firmware.read_bytes()).hexdigest())
    release_path.write_text(json.dumps(release))
    # The mount contract does not need cryptographic fixtures.
    core = project / 'configs/x2000/rootfs-overlay/usr/libexec/fre3nder/package-core'
    core.write_text('import json\n'
                    'def verify_package(path): return json.loads(path.read_text())\n'
                    'def image_system_apps():\n'
                    '    return [(p, verify_package(p)) for p in SYSTEM_APP_DIR.glob("*.fre3app")]\n')
    for relative, value in {
        'keys/apps/private.pem': 'APP_SECRET_SENTINEL',
        'keys/ota/private.pem': 'OTA_SECRET_SENTINEL',
        'keys/apps/fre3nder-official.pem': 'public app fixture',
        'keys/ota/public.pem': 'public OTA fixture',
        'factory-apps/fre3nderscreen.fre3app': json.dumps(dict(name='fre3nderscreen',
            publisher='fre3nder-official', display_frontend=True, display_api=1,
            autostart=False, release_serial=1)),
        'system-apps/moonraker.fre3app': json.dumps(dict(name='moonraker', version='fixture', autostart=False, release_serial=1)),
        'system-apps/unrelated-secret.txt': 'SYSTEM_INPUT_SECRET',
    }.items():
        path = project / 'local/production' / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
    git(project, 'init', '-q')
    git(project, 'add', '.')
    git(project, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
        'commit', '-qm', 'fixture')
    # Both ignored secrets and non-ignored local files must stay outside Docker.
    (project / '.env').write_text('UNTRACKED_ROOT_SECRET')
    (project / 'configs/x2000/untracked-secret.txt').write_text('UNTRACKED_CONFIG_SECRET')
    (project / 'build/x2000/untracked-secret.env').write_text('UNTRACKED_CONTEXT_SECRET')
    return project


FAKE_DOCKER = '''import hashlib, json, os, pathlib, sys
args = sys.argv[1:]
record = {"args": args, "mounts": []}
for i, arg in enumerate(args):
    if arg != "-v": continue
    host, target, *mode = args[i + 1].split(":")
    path = pathlib.Path(host)
    item = {"host": host, "target": target, "mode": mode}
    if target == "/project":
        item["files"] = sorted(p.relative_to(path).as_posix() for p in path.rglob("*") if p.is_file())
        assert not any(p.is_symlink() for p in path.rglob("*"))
        item["provenance"] = json.loads((path / ".fre3nder-project.json").read_text())
        assert all("SECRET" not in p.read_text(errors="ignore") for p in path.rglob("*") if p.is_file())
    if target == "/system-app-seeds":
        assert all(p.is_file() and not p.is_symlink() and p.suffix == ".fre3app" for p in path.iterdir())
        item["files"] = sorted(p.name for p in path.iterdir())
    record["mounts"].append(item)
if args[0] == "build":
    context = pathlib.Path(args[-1])
    record["context"] = sorted(p.name for p in context.iterdir())
if args[-1] == "build-fre3nderscreen-app":
    output = next(pathlib.Path(m["host"]) for m in record["mounts"] if m["target"] == "/artifacts") / "fre3nderscreen/app"
    (output / "bin").mkdir(parents=True, exist_ok=True)
    (output / "bin/fre3nderscreen").write_text("fixture binary")
    (output / "artifact-manifest.json").write_text("{}")
    (output / "SHA256SUMS").write_text("".join(hashlib.sha256((output / n).read_bytes()).hexdigest() + "  " + n + "\\n" for n in ("artifact-manifest.json", "bin/fre3nderscreen")))
with open(os.environ["MOUNT_TEST_LOG"], "a") as log: log.write(json.dumps(record) + "\\n")
'''


def docker_environment(base):
    tools = base / 'bin'
    tools.mkdir()
    docker = tools / 'docker'
    docker.write_text(f'#!{sys.executable}\n' + FAKE_DOCKER)
    docker.chmod(0o755)
    openssl = tools / 'openssl'
    openssl.write_text('#!/bin/sh\nprintf "ED25519 Public-Key:\\n"\n')
    openssl.chmod(0o755)
    environment = {k: v for k, v in os.environ.items() if not k.startswith('FRE3NDER_')}
    return dict(environment, X2000_BUILD_DOCKER=str(docker), PATH=str(tools) + os.pathsep + os.environ['PATH'],
                MOUNT_TEST_LOG=str(base / 'docker.log'), PYTHONDONTWRITEBYTECODE='1')


def check_mounts(test, project, calls):
    production = project / 'local/production'
    external_files = {
        '/ota-public-key': production / 'keys/ota/public.pem',
        '/app-public-key': production / 'keys/apps/fre3nder-official.pem',
        '/factory-fre3nderscreen-app': production / 'factory-apps/fre3nderscreen.fre3app',
        '/f005-firmware': production / 'artifacts/x2000/f005/klipper-f005-mainline.bin',
        '/f005-candidate/klipper-f005-mainline.bin': production / 'candidate/klipper-f005-mainline.bin',
        '/f005-candidate/build-manifest.json': production / 'candidate/build-manifest.json',
    }
    for call in calls:
        for option in ('--privileged', '--cap-add', '--device', '--security-opt'):
            test.assertNotIn(option, call['args'])
        for mount in call['mounts']:
            host = Path(mount['host'])
            test.assertNotEqual(host.resolve(), project.resolve())
            test.assertNotIn('docker.sock', mount['host'])
            if mount['target'] == '/project':
                test.assertEqual(mount['mode'], ['ro'])
                for name in ('VERSION', 'build/x2000/entrypoint.sh', 'scripts/source-value',
                             'configs/x2000/buildroot.defconfig', 'configs/x2000/kernel-fre3nder.defconfig',
                             'configs/x2000/buildroot-external/external.mk',
                             'configs/klipper-f005/printer-f005-mainline.cfg',
                             'patches/buildroot/0001-mips-add-ingenic-xburst2-target.patch'):
                    test.assertIn(name, mount['files'])
                test.assertNotIn('.git/config', mount['files'])
                test.assertFalse(any(name.startswith('local/') or 'untracked-secret' in name for name in mount['files']))
                test.assertEqual(mount['provenance']['project_commit'], git(project, 'rev-parse', 'HEAD').decode().strip())
            elif mount['target'] == '/work':
                test.assertEqual(host, project / 'local/production/work/x2000')
                test.assertEqual(mount['mode'], [])
            elif mount['target'] == '/artifacts':
                test.assertEqual(host, project / 'local/production/artifacts/x2000')
                test.assertEqual(mount['mode'], [])
            else:
                test.assertEqual(mount['mode'], ['ro'])
                if mount['target'] == '/system-app-seeds':
                    test.assertNotEqual(host, production / 'system-apps')
                    test.assertTrue(all(Path(name).suffix == '.fre3app' for name in mount['files']))
                else:
                    test.assertIn(mount['target'], external_files)
                    test.assertEqual(host, external_files[mount['target']])
                    test.assertTrue(host.is_file())
        if call['args'][0] == 'build':
            test.assertNotIn('untracked-secret.env', call['context'])


class MountTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.project = make_project(self.base)
        self.env = docker_environment(self.base)

    def calls(self):
        log = Path(self.env['MOUNT_TEST_LOG'])
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def run_script(self, name, *args, **env):
        return subprocess.run([str(self.project / 'scripts' / name), *args],
                              env=dict(self.env, **env), capture_output=True, text=True)

    def test_kernel_and_toolchain_mounts_preserve_targets(self):
        for script, args, targets in (
            ('build-x2000-kernel', ['--develop'], ['fetch-kernel', 'build-kernel-only']),
            ('build-x2000-buildroot', ['--toolchain'], ['fetch-buildroot', 'prepare-buildroot-toolchain']),
        ):
            with self.subTest(script=script):
                Path(self.env['MOUNT_TEST_LOG']).unlink(missing_ok=True)
                result = self.run_script(script, *args)
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = self.calls()
                check_mounts(self, self.project, calls)
                self.assertEqual([c['args'][-1] for c in calls if c['args'][0] == 'run'], targets)
                self.assertIn('--network', calls[-1]['args'])
                self.assertIn('none', calls[-1]['args'])

    def test_rootfs_mounts_only_selected_external_files(self):
        result = self.run_script('build-x2000-buildroot', '--assemble')
        self.assertEqual(result.returncode, 0, result.stderr)
        check_mounts(self, self.project, self.calls())
        seeds = next(m for m in self.calls()[-1]['mounts'] if m['target'] == '/system-app-seeds')
        self.assertEqual(seeds['files'], ['moonraker.fre3app'])

    def test_screen_mounts_and_artifact_path(self):
        result = self.run_script('build-x2000-fre3nderscreen')
        self.assertEqual(result.returncode, 0, result.stderr)
        check_mounts(self, self.project, self.calls())
        self.assertTrue((self.project / 'local/production/artifacts/x2000/fre3nderscreen/app/bin/fre3nderscreen').is_file())

    def test_candidate_firmware_keeps_provenance_without_mounting_its_directory(self):
        validator = runpy.run_path(str(self.project / 'build/x2000/f005_firmware.py'))
        firmware = self.project / 'local/production/candidate/klipper-f005-mainline.bin'
        firmware.parent.mkdir()
        firmware.write_bytes(b'candidate fixture')
        (firmware.parent / 'unrelated-secret.txt').write_text('EXTERNAL_INPUT_SECRET')
        sources = json.loads((self.project / 'configs/x2000/sources.json').read_text())
        record = {'schema': 1, 'classification': 'candidate', 'qualified_release_match': False,
                  'upstream': {'commit': sources['userspace']['klipper']['commit']},
                  'project_commit': git(self.project, 'rev-parse', 'HEAD').decode().strip(),
                  'runtime_version': 'fixture-candidate',
                  'inputs': {name: hashlib.sha256((self.project / name).read_bytes()).hexdigest()
                             for name in validator['CANDIDATE_INPUTS']},
                  'artifacts': {firmware.name: {'size': firmware.stat().st_size,
                      'sha256': hashlib.sha256(firmware.read_bytes()).hexdigest()}}}
        (firmware.parent / 'build-manifest.json').write_text(json.dumps(record))
        result = self.run_script('build-x2000-buildroot', '--assemble', '--develop',
                                 FRE3NDER_F005_FIRMWARE=str(firmware), FRE3NDER_F005_FIRMWARE_MODE='candidate')
        self.assertEqual(result.returncode, 0, result.stderr)
        check_mounts(self, self.project, self.calls())
        candidate = [m for m in self.calls()[-1]['mounts'] if m['target'].startswith('/f005-candidate/')]
        self.assertEqual({Path(m['host']).name for m in candidate}, {firmware.name, 'build-manifest.json'})
        destination = self.base / 'candidate-project'
        inputs['snapshot'](self.project, destination)
        self.assertEqual(validator['validate'](destination, firmware, 'candidate', 'development')['runtime_version'],
                         'fixture-candidate')

    def test_selected_submodule_copies_only_versioned_contents(self):
        module = self.base / 'module'
        module.mkdir()
        (module / 'fixture.h').write_text('/* module fixture */\n')
        git(module, 'init', '-q')
        git(module, 'add', '.')
        git(module, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')
        name = 'configs/x2000/fixture-module'
        git(self.project, '-c', 'protocol.file.allow=always', 'submodule', 'add', str(module), name)
        (self.project / name / 'untracked-secret.txt').write_text('MODULE_SECRET')
        destination = self.base / 'module-project'
        inputs['snapshot'](self.project, destination)
        self.assertEqual((destination / name / 'fixture.h').read_bytes(), (module / 'fixture.h').read_bytes())
        self.assertEqual({p.name for p in (destination / name).iterdir()}, {'fixture.h'})

    def test_local_screen_repository_is_not_mounted(self):
        source = self.base / 'screen-source'
        source.mkdir()
        (source / 'main.cpp').write_text('tracked source\n')
        (source / '.gitignore').write_text('ignored-secret.txt\n')
        git(source, 'init', '-q')
        git(source, 'add', '.')
        git(source, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')
        git(source, 'remote', 'add', 'origin', 'https://example.invalid/screen.git')
        (source / 'new.cpp').write_text('pending source\n')
        (source / '.env').write_text('LOCAL_SCREEN_SECRET')
        (source / 'ignored-secret.txt').write_text('IGNORED_SCREEN_SECRET')
        result = self.run_script('build-x2000-fre3nderscreen', '--develop', FRE3NDER_FRE3NDERSCREEN_SOURCE=str(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        check_mounts(self, self.project, self.calls())
        self.assertFalse(any(m['host'] == str(source) for c in self.calls() for m in c['mounts']))
        copied = self.project / 'local/production/work/x2000/fre3nderscreen-source'
        self.assertEqual((copied / 'new.cpp').read_text(), 'pending source\n')
        self.assertFalse((copied / '.env').exists())
        self.assertFalse((copied / 'ignored-secret.txt').exists())
        self.assertTrue((source / '.env').exists())

    def test_missing_or_symlinked_input_aborts_before_docker(self):
        path = self.project / 'configs/x2000/sources.json'
        data = path.read_bytes()
        path.unlink()
        result = self.run_script('build-x2000-kernel')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('sources.json', result.stderr)
        self.assertEqual(self.calls(), [])
        path.symlink_to(self.project / 'local/production/keys/apps/private.pem')
        result = self.run_script('build-x2000-kernel')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('symlink', result.stderr)
        self.assertEqual(self.calls(), [])
        path.unlink()
        path.write_bytes(data)

    def test_work_mount_cannot_resolve_to_project(self):
        for name in ('work', 'artifacts'):
            with self.subTest(name=name):
                parent = self.project / 'local/production' / name
                parent.mkdir(exist_ok=True)
                mount = parent / 'x2000'
                if mount.exists():
                    shutil.rmtree(mount)
                mount.symlink_to(self.project, target_is_directory=True)
                result = self.run_script('build-x2000-kernel')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('real directory', result.stderr)
                self.assertEqual(self.calls(), [])
                mount.unlink()

    def test_snapshot_preserves_dirty_tracked_inputs_and_provenance(self):
        changed = self.project / 'configs/x2000/buildroot.fragment'
        changed.write_text(changed.read_text() + '\n# tracked fixture edit\n')
        destination = self.base / 'snapshot'
        inputs['snapshot'](self.project, destination)
        self.assertEqual((destination / changed.relative_to(self.project)).read_bytes(), changed.read_bytes())
        self.assertFalse((destination / '.git').exists())
        self.assertEqual(inputs['project_provenance'](destination)['project_worktree_status'], 'dirty')

    def test_tracked_private_key_header_is_rejected(self):
        path = self.project / 'configs/x2000/fixture.pem'
        path.write_bytes(b'-----BEGIN ' + b'PRIVATE KEY-----\nfixture only\n')
        git(self.project, 'add', str(path))
        result = self.run_script('build-x2000-kernel')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('private key in project input', result.stderr)
        self.assertEqual(self.calls(), [])


if __name__ == '__main__':
    unittest.main()
