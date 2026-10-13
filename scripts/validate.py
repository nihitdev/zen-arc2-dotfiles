#!/usr/bin/env python3
"""Check manifest integrity, CSS imports/assets, and the publication file allowlist."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
URL = re.compile(r'''url\(\s*(?:"([^"]*)"|'([^']*)'|([^\s)]+))\s*\)''', re.I)
IMPORT = re.compile(r'''@import\s+(?:"([^"]*)"|'([^']*)')''', re.I)


def audit(staged=False):
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    errors = []
    paths = {entry['path'] for entry in manifest['files']}
    actual = {p.relative_to(ROOT).as_posix() for p in (ROOT / 'chrome').rglob('*') if p.is_file()}
    if paths != actual:
        errors.append(f'Manifest file mismatch: {sorted(paths ^ actual)}')
    for entry in manifest['files']:
        p = ROOT / entry['path']
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != entry['sha256']:
            errors.append(f'Missing or changed payload: {entry["path"]}')
    if hashlib.sha256((ROOT / 'theme-prefs.js').read_bytes()).hexdigest() != manifest['preferences_sha256']:
        errors.append('Theme preference checksum mismatch')
    references = 0
    for css in (ROOT / 'chrome').rglob('*.css'):
        text = re.sub(r'/\*.*?\*/', '', css.read_text(), flags=re.S)
        for match in list(URL.finditer(text)) + list(IMPORT.finditer(text)):
            value = next(group for group in match.groups() if group is not None)
            url = urlsplit(value)
            if url.scheme in ('data', 'chrome', 'resource', 'about') or value.startswith('#'):
                continue
            if url.scheme or value.startswith('//'):
                errors.append(f'External dependency: {css.relative_to(ROOT)}: {value[:150]}')
                continue
            target = (css.parent / unquote(url.path)).resolve()
            if not target.is_relative_to((ROOT / 'chrome').resolve()):
                errors.append(f'Asset escapes theme: {value}')
            elif not target.is_file():
                errors.append(f'Missing asset: {css.relative_to(ROOT)} -> {value}')
            elif target.relative_to(ROOT).as_posix() not in paths:
                errors.append(f'Asset is not in manifest: {value}')
            references += 1
    if staged:
        names = subprocess.check_output(['git', 'diff', '--cached', '--name-only', '-z'], cwd=ROOT).decode().split('\0')
        allowed = paths | {'manifest.json', 'theme-prefs.js', 'packaging-changes.json',
                           'README.md', 'LICENSE', '.gitignore', '.gitattributes',
                           'install.sh', 'install.ps1', 'SECURITY-AND-LICENSING.md'}
        for name in filter(None, names):
            if name not in allowed and not name.startswith(('licenses/', 'scripts/', 'tests/')):
                errors.append(f'Unexpected staged file: {name}')
            data = subprocess.check_output(['git', 'show', ':' + name], cwd=ROOT)
            if Path(name).suffix in ('.ttf', '.gif'):
                continue
            if re.search(rb'gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]+|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|/home/[a-zA-Z0-9_.-]+/', data):
                errors.append(f'Potential private data in: {name}')
        # Detect excluded dependencies even when an ignored local copy happens to exist.
        tracked = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0'))
        if not paths <= tracked:
            errors.append('Untracked theme dependencies: ' + ', '.join(sorted(paths - tracked)))
    if errors:
        raise ValueError('\n'.join(errors))
    print(f'PASS: {len(paths)} payload files; {references} local CSS references resolve with exact filename case.')
    print('PASS: no active external CSS assets; built-in browser URLs and embedded data URLs are retained.')
    if staged:
        print('PASS: staged allowlist and private-path/token checks. This is a focused scan, not a universal secret detector.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staged', action='store_true')
    args = parser.parse_args()
    try:
        audit(args.staged)
    except (OSError, ValueError, KeyError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        sys.exit(1)
