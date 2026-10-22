#!/usr/bin/env python3
"""Copy a local development worktree, including pending sources, into build work."""

import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit


PRIVATE_KEY = re.compile(rb"^[ \t]*-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----[ \t]*\r?$", re.MULTILINE)


def git(source, *args):
    return subprocess.check_output(['git', '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=/dev/null',
                                    '-C', str(source), *args])


def checked_source(root, name):
    path = root
    for part in pathlib.PurePosixPath(name).parts:
        path /= part
        if path.is_symlink():
            raise ValueError(f"symlink in local Screen source: {name}")
    if not path.is_file():
        raise ValueError(f"missing regular local Screen source: {name}")
    if PRIVATE_KEY.search(path.read_bytes()):
        raise ValueError(f"private key in local Screen source: {name}")


def clone(source, destination):
    # Only the current committed tree; no local hooks, config or old history.
    subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', 'clone', '--quiet',
                    '--template=', '--depth=1', '--no-local', str(source), str(destination)], check=True)


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
    repository = git(source, 'remote', 'get-url', 'origin').decode().strip()
    if urlsplit(repository).username or urlsplit(repository).password:
        raise ValueError("credential-bearing Screen origin is unsupported")
    tracked = set(git(source, 'ls-files', '-z', '--cached').split(b'\0')) - {b''}
    pending = set(git(source, 'ls-files', '-z', '--others', '--exclude-standard').split(b'\0')) - {b''}
    # New source/patch/theme files remain usable; arbitrary local files are not inputs.
    pending = {name for name in pending if pathlib.Path(os.fsdecode(name)).suffix in
               ('.c', '.cpp', '.h', '.hpp', '.cmake', '.patch')
               or (name.startswith(b'themes/') and name.endswith(b'.json'))}
    for raw_name in tracked | pending:
        name = os.fsdecode(raw_name)
        if name in submodules or not (source / name).exists() and not (source / name).is_symlink():
            continue
        checked_source(source, name)
    for name in submodules:
        for raw_name in git(source / name, 'ls-files', '-z').split(b'\0'):
            if raw_name:
                checked_source(source / name, os.fsdecode(raw_name))
    if destination.exists():
        shutil.rmtree(destination)
    clone(source, destination)
    subprocess.run(['git', '-C', str(destination), 'remote', 'set-url', 'origin',
                    repository], check=True)
    # A clone supplies Git identity; overlay the current tracked and non-ignored
    # source files, so both edits and new files survive later preparation.
    names = sorted(tracked | pending | (set(git(destination, 'ls-files', '-z').split(b'\0')) - {b''}))
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
        clone(source / name, destination / name)
        commit = git(source / name, 'rev-parse', 'HEAD').strip()
        subprocess.run(['git', '-C', str(destination / name), 'checkout', '--quiet', '--detach', commit.decode()], check=True)
        digest.update(name.encode() + b'\0' + commit + b'\0')
    # Register the fresh copies without importing the source's local Git config.
    git(destination, 'submodule', 'init')
    record = {'origin': 'local-worktree', 'worktree_status':
              'dirty' if git(source, 'status', '--porcelain=v1').strip() else 'clean',
              'worktree_sha256': digest.hexdigest()}
    destination.with_suffix('.snapshot.json').write_text(json.dumps(record, sort_keys=True) + '\n')


if __name__ == '__main__':
    snapshot(*map(pathlib.Path, sys.argv[1:]))
