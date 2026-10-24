"""Full draft-2020-12 schema + pinned fixture/icon/provenance validation.
Requires jsonschema 4.x in the verification Python environment.
"""
import hashlib
import json
from pathlib import Path
import jsonschema

root = Path(__file__).resolve().parent.parent
schema = json.loads((root / 'tests/fixtures/beta/extension-v2.schema.json').read_bytes())
manifest = json.loads((root / 'manifest.json').read_bytes())
jsonschema.Draft202012Validator.check_schema(schema)
jsonschema.Draft202012Validator(schema).validate(manifest)
provenance = json.loads((root / 'provenance.json').read_bytes())
for item in provenance['files']:
    data = (root / item['vendored']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == item['sha256'], item
    assert len(data) == item['bytes'], item
upstream = json.loads((root / 'tests/fixtures/upstream/package.json').read_bytes())
assert upstream['author'] == 'Visual-Studio-Coder'
command = manifest['commands'][0]
for key, value in upstream['commands'][0].items():
    assert command[key] == value, key
assert len(manifest['commands']) == 1
assert manifest['id'] == 'com.tezbar.native.markdown-table-generator'
assert manifest['replaces'] == ['raycast.markdown-table-generator']
assert manifest['runtime'] == command['runtime'] == 'rust'
assert manifest['icon'] == '/extensions/icons/markdown-table-generator.png'
assert 'author' not in manifest and 'Visual-Studio-Coder' in manifest['description']
assert [(v['platform'], v['state']) for v in manifest['verification']] == [('macOS','not-run'),('Windows','not-run')]
icon = (root / 'assets/command-icon.png').read_bytes()
assert len(icon) == 177356
assert hashlib.sha256(icon).hexdigest() == '6b3465b10a40ed075938c17be1aa2a9235dabfb43423a2ff7fd3f4dd24895bc1'
# In a repository checkout also verify the untouched V1 asset; packaged tests
# remain self-contained without the V1 parent directory.
if (root.parent / 'assets/command-icon.png').exists():
    assert (root.parent / 'assets/command-icon.png').read_bytes() == icon
print('Full schema, command metadata, provenance and exact icon validation passed.')
