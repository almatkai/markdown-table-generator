#!/usr/bin/env python3
"""Build the root-layout ZIP with a closed SHA inventory. Never uploads."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {'aarch64-apple-darwin': False, 'x86_64-pc-windows-msvc': True}
SDK_REV = 'aaec571673ab64a85a136cf6bd054ef660c4d93c'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_sdk():
    text = (ROOT / 'Cargo.toml').read_text()
    match = re.search(r'^tezbar-extension-sdk\s*=\s*\{([^}\n]*)\}', text, re.M)
    fields = match.group(1) if match else ''
    assert f'rev = "{SDK_REV}"' in fields and not re.search(r'\b(path|branch|tag)\s*=', fields), 'SDK must use the approved immutable revision'
    assert 'git = "https://github.com/almatkai/tezbar-extension-sdk-rust.git"' in fields
    lock = (ROOT / 'Cargo.lock').read_text()
    entry = re.search(r'\[\[package\]\]\nname = "tezbar-extension-sdk"(.*?)(?=\[\[package\]\]|\Z)', lock, re.S)
    assert entry and f'#{SDK_REV}"' in entry.group(1), 'Cargo.lock SDK pin mismatch'


def check_architecture(binary, target):
    data = binary.read_bytes()
    if target == 'aarch64-apple-darwin':
        assert data[:4] == b'\xcf\xfa\xed\xfe' and struct.unpack_from('<I', data, 4)[0] == 0x100000c, 'Expected arm64 Mach-O'
    else:
        assert data[:2] == b'MZ', 'Expected Windows PE executable'
        offset = struct.unpack_from('<I', data, 0x3c)[0]
        assert data[offset:offset + 4] == b'PE\0\0' and struct.unpack_from('<H', data, offset + 4)[0] == 0x8664, 'Expected Windows x64 PE'


def build(target, binary, output):
    check_sdk()
    check_architecture(binary, target)
    subprocess.run(['python3', str(ROOT / 'scripts/vendor-licenses.py'), '--check'], cwd=ROOT, check=True)
    manifest = json.loads((ROOT / 'extension.json').read_text())
    slug = manifest['slug']
    executable = f'bin/tezbar-{slug}' + ('.exe' if TARGETS[target] else '')
    info = json.loads(subprocess.check_output([str(binary.resolve()), '--protocol-info'], timeout=10))
    assert info['id'] == manifest['id'] and info['version'] == manifest['version'] and info['protocol'] == 1, 'Binary identity mismatch'
    platform = 'Windows' if TARGETS[target] else 'macOS'
    expected = [c['name'] for c in manifest['commands'] if c['runtime'] == 'rust' and platform in c['platforms']]
    assert set(info['commands']) == set(expected), 'Binary/manifest platform coverage mismatch'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        (stage / 'bin').mkdir()
        shutil.copy2(binary, stage / executable)
        for name in ['resources', 'licenses']:
            # Reject source symlinks before copying rather than dereferencing them.
            assert not (ROOT / name).is_symlink()
            assert all(not p.is_symlink() for p in (ROOT / name).rglob('*')), 'Symlinks cannot be packaged'
            shutil.copytree(ROOT / name, stage / name)
        for name in ['LICENSE', 'NOTICE']:
            assert not (ROOT / name).is_symlink()
            shutil.copy2(ROOT / name, stage / name)
        files = {path.relative_to(stage).as_posix(): digest(path)
                 for path in sorted(stage.rglob('*')) if path.is_file()}
        manifest['files'] = files
        # Parent supplies real published archive URL/digests to the trusted catalog.
        manifest['artifacts'] = {}
        (stage / 'extension.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        archive = output / f'{slug}-{target}.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zipped:
            for path in sorted(stage.rglob('*')):
                if path.is_file():
                    name = path.relative_to(stage).as_posix()
                    entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                    entry.create_system = 3
                    mode = 0o755 if name == executable else 0o644
                    entry.external_attr = (stat.S_IFREG | mode) << 16
                    entry.compress_type = zipfile.ZIP_DEFLATED
                    zipped.writestr(entry, path.read_bytes())
        with zipfile.ZipFile(archive) as zipped:
            packaged = json.loads(zipped.read('extension.json'))
            assert set(zipped.namelist()) == set(files) | {'extension.json'}
            for name, sha in packaged['files'].items():
                assert hashlib.sha256(zipped.read(name)).hexdigest() == sha
        artifact = {'target': target, 'sha256': digest(archive), 'executable': executable,
                    'executableSha256': files[executable]}
        (output / f'{slug}-{target}.artifact.json').write_text(json.dumps(artifact, indent=2) + '\n')
        (output / f'{archive.name}.sha256').write_text(f"{artifact['sha256']}  {archive.name}\n")
        (output / f'{slug}-{target}.executable.sha256').write_text(f"{artifact['executableSha256']}  {executable}\n")
        print(archive)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', required=True, choices=TARGETS)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    build(args.target, args.binary, args.output)
