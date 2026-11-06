#!/usr/bin/env python3
"""Verify closed ZIP inventory, extract and test the actual binary offline."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
import zipfile
from protocol_test import run_suite


def smoke(path):
    with tempfile.TemporaryDirectory() as temp, zipfile.ZipFile(path) as archive:
        root = Path(temp) / 'package'
        root.mkdir()
        names = archive.namelist()
        assert len(names) == len(set(names)), 'Duplicate ZIP paths'
        assert len(names) == len({name.casefold() for name in names}), 'Case-folded duplicate ZIP paths'
        for item in archive.infolist():
            name = PurePosixPath(item.filename)
            assert not name.is_absolute() and '..' not in name.parts and '.' not in name.parts
            assert '\\' not in item.filename and ':' not in item.filename
            assert not item.is_dir() and not stat.S_ISLNK(item.external_attr >> 16)
        manifest = json.loads(archive.read('extension.json'))
        assert set(names) == set(manifest['files']) | {'extension.json'}, 'ZIP inventory mismatch'
        for name, digest in manifest['files'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest, 'Tampered member: ' + name
        artifact = json.loads(path.with_suffix('.artifact.json').read_text())
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact['sha256']
        assert manifest['files'][artifact['executable']] == artifact['executableSha256']
        assert path.with_suffix(path.suffix + '.sha256').read_text() == artifact['sha256'] + '  ' + path.name + '\n'
        executable_sidecar = path.with_suffix('.executable.sha256')
        assert executable_sidecar.read_text() == artifact['executableSha256'] + '  ' + artifact['executable'] + '\n'
        archive.extractall(root)
        binary = root / artifact['executable']
        assert binary.suffix == ('.exe' if os.name == 'nt' else ''), 'Run smoke on the matching native target'
        assert archive.getinfo(artifact['executable']).external_attr >> 16 & 0o111
        binary.chmod(0o755)
        run_suite(binary, manifest, root)
        print('Extracted ZIP inventory + archive/executable sidecars + real binary smoke passed:', path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    smoke(parser.parse_args().archive)
