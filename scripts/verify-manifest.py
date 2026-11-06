#!/usr/bin/env python3
"""Validate source/packaged schemas, complete command metadata and provenance."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
import jsonschema

ROOT = Path(__file__).resolve().parents[1]


def verify(manifest):
    schema = json.loads((ROOT / 'tests/fixtures/extension-v3.schema.json').read_bytes())
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(manifest)
    original = json.loads((ROOT / 'package.json').read_bytes())
    assert manifest['id'] == 'com.tezbar.native.' + original['name']
    assert manifest['replaces'] == ['raycast.' + original['name']]
    assert manifest['name'] == original['title'] and manifest['platforms'] == original['platforms']
    assert manifest['preferences'] == original.get('preferences', []) == []
    assert len(manifest['commands']) == len(original['commands']) == 1
    for native, source in zip(manifest['commands'], original['commands']):
        for key, value in source.items():
            assert native[key] == value, key
        assert native['runtime'] == 'rust' and native['concurrency'] == 'serialize' and native['refreshMs'] is None
    assert manifest['capabilities'] == ['clipboard.write'] and manifest['migrationPaths'] == {}
    assert all(v['state'] == 'not-run' for v in manifest['verification'])
    assert manifest['version'] == '0.1.0'
    assert (ROOT / 'resources/assets/command-icon.png').read_bytes() == (ROOT / 'assets/command-icon.png').read_bytes()
    provenance = json.loads((ROOT / 'native/provenance.json').read_bytes())
    assert hashlib.sha256((ROOT / 'v2/src/lib.rs').read_bytes()).hexdigest() == provenance['engine']['sha256']
    assert hashlib.sha256((ROOT / 'tests/fixtures/extension-v3.schema.json').read_bytes()).hexdigest() == provenance['schema']['sha256']


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    verify(json.loads((ROOT / 'extension.json').read_bytes()))
    if args.archive:
        with zipfile.ZipFile(args.archive) as archive:
            verify(json.loads(archive.read('extension.json')))
    print('Schema 3, exact original command metadata, identity, icon and provenance passed.')
