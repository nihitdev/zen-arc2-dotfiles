#!/usr/bin/env python3
"""Install only manifest-listed theme files. Never export or replace a profile."""
import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]


def payload():
    entries = json.loads((ROOT / 'manifest.json').read_text())['files']
    result = []
    seen = set()
    for entry in entries:
        name = entry['path']
        parts = PurePosixPath(name).parts
        if (not parts or parts[0] != 'chrome' or '..' in parts or '\\' in name
                or ':' in name or name in seen or str(PurePosixPath(name)) != name):
            raise ValueError(f'Unsafe or duplicate manifest path: {name}')
        seen.add(name)
        src = ROOT / name
        safe_target(ROOT, name)
        if not src.is_file() or hashlib.sha256(src.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError(f'Missing or changed payload: {name}. Run scripts/validate.py.')
        result.append((name, src.read_bytes()))
    if not {'chrome/userChrome.css', 'chrome/userContent.css', 'chrome/CONFIG.css'} <= seen:
        raise ValueError('Incomplete manifest.')
    return result


def safe_target(profile, name):
    current = profile
    for part in PurePosixPath(name).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f'Refusing to follow a symlink: {current}')
        if current.exists() and current != profile / name and not current.is_dir():
            raise ValueError(f'Parent is not a directory: {current}')
    if current.exists() and not current.is_file():
        raise ValueError(f'Destination is not a regular file: {current}')
    return current


def discover(ini_paths):
    found = {}
    for ini in ini_paths:
        if not ini.is_file():
            continue
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(ini, encoding='utf-8-sig')
        for section in parser.sections():
            if not section.startswith('Profile') or not parser.has_option(section, 'Path'):
                continue
            path = Path(parser.get(section, 'Path'))
            if parser.get(section, 'IsRelative', fallback='1') == '1':
                path = ini.parent / path
            path = path.expanduser().resolve()
            if path.is_dir():
                found[path] = parser.get(section, 'Name', fallback=path.name)
    return list(found.items())


def ask(prompt):
    try:
        return input(prompt).strip().lower()
    except EOFError:
        raise ValueError('Interactive input is required; no files were changed.') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, help='Explicit existing profile root (about:profiles)')
    parser.add_argument('--profiles-ini', type=Path, help='Use only this profiles.ini (portable installs/tests)')
    args = parser.parse_args()
    if hasattr(os, 'geteuid') and os.geteuid() == 0:
        raise ValueError('Run as your normal user, not root/sudo.')
    files = payload()  # Validate everything before touching the profile.
    if args.profile:
        profile = args.profile.expanduser().resolve()
        if not profile.is_dir():
            raise ValueError(f'Profile directory does not exist: {profile}')
    else:
        home = Path.home()
        roots = [Path(os.environ.get('XDG_CONFIG_HOME', home / '.config')) / 'zen',
                 home / '.config/zen', home / '.zen',
                 home / '.var/app/app.zen_browser.zen/config/zen',
                 home / '.var/app/app.zen_browser.zen/.zen',
                 home / '.var/app/io.github.zen_browser.zen/config/zen']
        profiles = discover([args.profiles_ini] if args.profiles_ini else [r / 'profiles.ini' for r in roots])
        if not profiles:
            raise ValueError('No Zen profiles found. Launch Zen once or use --profile PATH.')
        for i, (path, name) in enumerate(profiles, 1):
            print(f'{i}. {name}\n   {path}')
        choice = ask('Select profile number: ') if len(profiles) > 1 else '1'
        if not choice.isdigit() or not 1 <= int(choice) <= len(profiles):
            raise ValueError('Invalid profile selection; no files were changed.')
        profile = profiles[int(choice) - 1][0]
    print(f'Target: {profile}')
    # Linux lock is removed on clean shutdown. Do not remove locks automatically.
    if os.path.lexists(profile / 'lock'):
        raise ValueError('Profile has a Zen lock. Close Zen completely and retry. Do not remove an active lock.')
    if ask('Close Zen completely before installing. Is Zen closed? [y/N] ') not in ('y', 'yes'):
        print('Cancelled; no files were changed.')
        return
    prefs = (ROOT / 'theme-prefs.js').read_bytes()
    expected = json.loads((ROOT / 'manifest.json').read_text())['preferences_sha256']
    if hashlib.sha256(prefs).hexdigest() != expected:
        raise ValueError('Theme preference checksum mismatch.')
    if not prefs.endswith(b'\n'):
        raise ValueError('Invalid theme-prefs.js.')
    target_prefs = safe_target(profile, 'user.js')
    old_prefs = target_prefs.read_bytes() if target_prefs.exists() else b''
    block = b'\n// BEGIN zen-arc2-dotfiles\n' + prefs + b'// END zen-arc2-dotfiles\n'
    new_prefs = old_prefs if old_prefs.endswith(block) else old_prefs + block
    files.append(('user.js', new_prefs))
    changed, overwritten = [], []
    for name, data in files:
        dest = safe_target(profile, name)
        if dest.exists() and dest.read_bytes() == data:
            continue
        changed.append((name, data))
        if dest.exists():
            overwritten.append(name)
    if not changed:
        print('Success: the complete theme is already installed; no changes needed.')
        return
    if overwritten:
        print('Existing files to update (backups will be saved):\n' + '\n'.join(overwritten))
        if ask('Overwrite these customization files? [y/N] ') not in ('y', 'yes'):
            print('Cancelled; no files were changed.')
            return
    backup = None
    if overwritten:
        # A fresh directory under the profile; do not follow user-controlled backup symlinks.
        backup = profile / ('.zen-arc2-backup-' + uuid.uuid4().hex)
        backup.mkdir(mode=0o700)
        for name in overwritten:
            dest = backup / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(profile / name, dest)
        print(f'Backup: {backup}')
    for name, data in changed:
        dest = safe_target(profile, name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.zen-arc2-', dir=dest.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
            os.replace(temporary, dest)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    print(f'Success: installed {len(changed)} files into {profile}. Restart Zen.')
    print('Existing user.js content was preserved; theme preferences were appended.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, configparser.Error) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        print('If a write failed after backup creation, restore the files from the printed backup directory.', file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print('\nCancelled.', file=sys.stderr)
        sys.exit(130)
