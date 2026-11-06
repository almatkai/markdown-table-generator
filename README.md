# Markdown Table Generator for Tezbar

**Native Rust 0.1.0 for Tezbar:** [release](https://github.com/almatkai/markdown-table-generator/releases/tag/v0.1.0), [macOS Apple Silicon ZIP](https://github.com/almatkai/markdown-table-generator/releases/download/v0.1.0/markdown-table-generator-aarch64-apple-darwin.zip), [Windows x64 ZIP](https://github.com/almatkai/markdown-table-generator/releases/download/v0.1.0/markdown-table-generator-x86_64-pc-windows-msvc.zip), [trusted install reference](https://github.com/almatkai/markdown-table-generator/releases/download/v0.1.0/extension-release.json).

Requires a Tezbar build with schema-3 process extensions and the import CLI. Download the trusted JSON and your platform ZIP, then import:

```sh
tezbar --extensions-v3-import extension-release.json markdown-table-generator-<target>.zip
```

Both native platform builds, extracted-package protocol checks and actual Tezbar CLI installs into isolated profiles passed. [Validation and exact hashes](https://github.com/almatkai/markdown-table-generator/releases/download/v0.1.0/validation.json) record the tested source. Actual desktop effects remain unverified; Store discovery still needs a Tezbar catalog update.

The accepted baseline does not show no-view hotkey messages. Clipboard copying is verified offline; hotkey feedback still needs an accepted host update.

Generate markdown tables from row/column counts in Tezbar on Windows or macOS.

## Installable standalone Rust package

The root [extension.json](extension.json) describes the schema 3, protocol 1 process
package `com.tezbar.native.markdown-table-generator`. The preserved Raycast
TypeScript implementation remains in `src/` with its original `package.json`.
The native executable reuses the unchanged, bounded [v2 Rust engine](v2/src/lib.rs)
and uses the independent SDK pinned to git revision
`aaec571673ab64a85a136cf6bd054ef660c4d93c`. It has no Tezbar/Tauri, Node, Bun or
JavaScript subprocess runtime dependency; historical beta fixtures are test-only.

| Original command | Native behavior | Platforms |
|---|---|---|
| `generate-markdown-table` | Takes required text arguments `rows`, then `columns`; generates and copies the original table text with real line breaks and trailing LF. | macOS arm64, Windows x64 |

There are no preferences, form values, saved data or caches to migrate. The only
capability is `clipboard.write`. The original icon, command metadata, argument
order and validation text are retained. Parsing matches JavaScript's decimal
`parseInt` prefix (for example `2.9junk` means 2). The mature engine's checked
8 MiB output bound remains; larger tables explicitly fail before allocation.

Clipboard success is reported **after** the host acknowledges `{ "ok": true }`.
Permission failures, transport errors and malformed acknowledgements never report
Copy success. Expected input/resource/clipboard failures are protocol successes
containing `{ "ok": false, "mode": "no-view", "message": "…" }`, allowing the
host's immediate `session.dispose` to complete. Invalid commands/actions still
reject. This no-view command has no action bindings; arbitrary action text is
never copied. SDK `serve()` owns initialization, serialization, cancellation,
transactional state and lifecycle cleanup. No duplicate notifications or effects
are emitted.

The accepted host baseline `d77f03b12a93d72cd2a56a73faa1a04fae94a2cd` displays
no-view messages from launcher invocation. Its hotkey handler ignores no-view
results, so hotkey feedback is a **host gap**, particularly when required arguments
are absent. This package does not depend on the separate in-progress host feedback
fixes. Real desktop clipboard/launcher QA remains unverified on both platforms;
headless protocol tests do not establish desktop acceptance. Source verification
records deliberately stay `not-run`.

Build and verify locally (Rust 1.85; two build jobs; all build output stays here):

```sh
export CARGO_BUILD_JOBS=2
export CARGO_TARGET_DIR="$PWD/.build/target"
cargo +1.85.0 test --workspace --locked -j2
cargo +1.85.0 fmt --all -- --check
cargo +1.85.0 clippy --workspace --all-targets --locked -j2 -- -D warnings
(cd v2 && node --experimental-vm-modules scripts/oracle.mjs)
python3 -m venv .build/python
.build/python/bin/pip install jsonschema==4.25.1
.build/python/bin/python v2/scripts/verify.py
.build/python/bin/python scripts/verify-manifest.py
cargo +1.85.0 build --release --locked --target aarch64-apple-darwin -j2
python3 scripts/vendor-licenses.py --check
python3 scripts/package.py --target aarch64-apple-darwin \
  --binary .build/target/aarch64-apple-darwin/release/tezbar-markdown-table-generator
python3 scripts/smoke-package.py dist/markdown-table-generator-aarch64-apple-darwin.zip
.build/python/bin/python scripts/verify-manifest.py \
  --archive dist/markdown-table-generator-aarch64-apple-darwin.zip
```

The package script also accepts `x86_64-pc-windows-msvc`, on a native Windows
build host with the corresponding `.exe`. Native Windows builds, package checks
and isolated CLI imports have passed. Desktop verification remains separate. Local Cargo
resolver configuration selects MSRV-compatible dependencies, and `Cargo.lock` is
committed. No workflow builds are added. After dependency changes regenerate
notices with `python3 scripts/vendor-licenses.py`; packaging checks them against
the locked normal/build dependency closure for **both** targets, including SDK
NOTICE and alternative license texts.

Each ZIP contains only root `extension.json`, `bin/tezbar-markdown-table-generator`
(or `.exe`), `resources/`, `licenses/`, `LICENSE` and `NOTICE`. Its manifest has an
exact SHA256 inventory of all members except itself. Archive SHA256, executable
SHA256 and artifact metadata sidecars are written next to the ZIP. Smoke extracts
the archive and runs its actual executable with a recording narrow host; it tests
exact multiline copying, acknowledged and failed writes, forged actions, strict
capability grants, failed-open immediate disposal, cancellation/late replies, and
shutdown while stdin stays open. It never touches the user's clipboard.

Installation requires a separately reviewed trusted release manifest whose
`artifacts` pins the real archive and executable hashes and HTTPS release URLs.
Source and ZIP manifests leave `artifacts: {}` to avoid inventing published
artifacts or embedding a circular ZIP hash. After review and publication, use
Tezbar's catalog install or `tezbar --extensions-v3-import /absolute/trusted-release-manifest.json /absolute/package.zip`,
then restart Tezbar. Version `0.1.0` is published with both native platform ZIPs
and the trusted release reference after independent review and isolated installs.
The host catalog is not updated by this repository. Real desktop clipboard/UI
verification remains pending, distinct from the completed native package checks.

Licensing: original sources/assets remain MIT; SDK and copied host schema are
Apache-2.0. Original license files are preserved, with readable MIT/Apache texts
and original Raycast copyright in `licenses/`, plus exact dependency documents
and their hash index. See [NOTICE](NOTICE), [dependency notices](licenses/THIRD_PARTY.md)
and [native provenance](native/provenance.json). Historical v2 integration guidance
below describes its earlier compiled-host adapter; this process package is the
standalone installation path.

## Raycast command

- **Generate Markdown Table** — takes `# of Rows` and `# of Columns` (integers > 0) and copies a markdown table to clipboard with header `Column 1…N`, separator `---`, and body `Cell r-c`. Shows success or failure toast for invalid input.

## Raycast compatibility (historical JavaScript port)

- Windows: built and exercised in Tezbar on Windows 11.
- macOS: uses only cross-platform `@raycast/api` and pure JS helpers and retains the upstream macOS-compatible design.
- Linux: not currently declared.

## Local verification

```powershell
pnpm install
pnpm typecheck
pnpm test
pnpm build
```

## Credits

Adapted for Tezbar from Raycast's MIT-licensed `markdown-table-generator` extension at upstream commit `6734d85992290066fd31a7f5bee3cca3d3545a1a`. Original author `Visual-Studio-Coder` remains credited in `package.json`.

## Native V2

See [the standalone Rust Native V2 port and host integration instructions](v2/README.md).
