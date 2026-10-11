#!/usr/bin/env python3
"""Copy a local development worktree, including pending sources, into build work."""

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys


def git(source, *args):
    return subprocess.check_output(['git', '-C', str(source), *args])


def snapshot(source, destination):
    source = source.resolve()
    if pathlib.Path(git(source, 'rev-parse', '--show-toplevel').decode().strip()) != source:
        raise ValueError('local source must be the repository root')
    submodules = []
    for line in git(source, 'submodule', 'status').decode().splitlines():
        if line[0] != ' ':
            raise ValueError('local submodules must be initialized at their recorded commits')
        _, name, *_ = line.split()
        sub = source / name
        if git(sub, 'status', '--porcelain=v1').strip():
            raise ValueError('local submodule changes are unsupported; put changes in source patches')
        submodules.append(name)
    if destination.exists():
        shutil.rmtree(destination)
    subprocess.run(['git', 'clone', '--quiet', '--no-local', str(source), str(destination)], check=True)
    subprocess.run(['git', '-C', str(destination), 'remote', 'set-url', 'origin',
                    git(source, 'remote', 'get-url', 'origin').decode().strip()], check=True)
    # A clone supplies Git identity; overlay the current tracked and non-ignored
    # source files, so both edits and new files survive later preparation.
    names = sorted((set(git(source, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').split(b'\0'))
                    | set(git(destination, 'ls-files', '-z').split(b'\0'))) - {b''})
    digest = hashlib.sha256()
    for raw_name in names:
        name = raw_name.decode()
        if name in submodules:
            continue
        original, copied = source / name, destination / name
        if copied.is_symlink() or copied.is_file():
            copied.unlink()
        digest.update(raw_name + b'\0')
        if not original.exists() and not original.is_symlink():
            digest.update(b'deleted\0')
            continue
        copied.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, copied, follow_symlinks=False)
        digest.update(str(original.lstat().st_mode & 0o777).encode() + b'\0')
        digest.update(original.readlink().as_posix().encode() if original.is_symlink() else original.read_bytes())
    for name in submodules:
        subprocess.run(['git', 'clone', '--quiet', '--no-local', str(source / name),
                        str(destination / name)], check=True)
        commit = git(source / name, 'rev-parse', 'HEAD').strip()
        subprocess.run(['git', '-C', str(destination / name), 'checkout', '--quiet', '--detach', commit.decode()], check=True)
        digest.update(name.encode() + b'\0' + commit + b'\0')
    record = {'origin': 'local-worktree', 'worktree_status':
              'dirty' if git(source, 'status', '--porcelain=v1').strip() else 'clean',
              'worktree_sha256': digest.hexdigest()}
    destination.with_suffix('.snapshot.json').write_text(json.dumps(record, sort_keys=True) + '\n')


if __name__ == '__main__':
    snapshot(*map(pathlib.Path, sys.argv[1:]))
