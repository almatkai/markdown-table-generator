# Markdown Table Generator — Rust Native V2

A standalone Rust 1.85 library and compiled Tezbar adapter for **Generate Markdown Table**. Original extension: Visual-Studio-Coder, MIT, pinned Raycast commit `6734d85992290066fd31a7f5bee3cca3d3545a1a`. Native API reference: Tezbar beta `fd300e276356587726566026f072563eb9c34cb1`.

`manifest.json` declares schema 2, ID `com.tezbar.native.markdown-table-generator`, replacement `raycast.markdown-table-generator`, Rust runtime and macOS/Windows support. Original command name, title, subtitle, description and required text arguments are preserved: **rows first, columns second**. Platform verification is `not-run` for both systems; cross-compilation and headless tests do not establish desktop QA.

## Behavior and deliberate adaptations

Inputs use the decimal digit prefix after ECMAScript whitespace and an optional sign, matching `parseInt(arg, 10)` followed by `Number.isInteger` and positivity. Thus `2.9junk` means 2, `3e6` means 3, `001` means 1, and `0x10` is invalid because its decimal prefix is zero. Non-ASCII digits, zero, negatives, empty values, NaN and Infinity are invalid. The original validation message is returned as a native error:

> Please enter an integer value greater than zero for both rows and columns.

The output retains the exact `Column n`, `---`, and `Cell r-c` text, spaces, pipes and trailing LF. Only generated table text is copied; arbitrary payload text is never used. Example `rows=1`, `columns=2`:

```text
| Column 1 | Column 2 |
| --- | --- |
| Cell 1-1 | Cell 1-2 |
```

V2 limits the generated UTF-8 text to **8 MiB (8,388,608 bytes), inclusive**. A checked, logarithmic size calculation runs before allocation or generation. The size includes decimal index widths and line endings, so there are no arbitrary per-dimension caps. For example 4,124 × 136 fits exactly; 4,125 × 136 fails with `Markdown table exceeds the 8 MiB output limit.` Asymmetric dimensions and arithmetic overflow are checked as well. Finite huge integer prefixes fail the resource bound; prefixes that become binary64 Infinity fail original validation. Rounding of finite values larger than the output bound cannot affect generated text; no big-integer dependency is needed. Allocation failure has a separate error.

The original shows its success toast before awaiting clipboard copying. The adapter instead awaits SDK `copy`, requires the beta acknowledgement `{"ok":true}`, and only then returns `Markdown table copied to clipboard!`. Transport errors, error envelopes and malformed acknowledgements return an error. The native host turns adapter errors into `{"ok":false,"message":"…"}`; success is `{"ok":true,"mode":"no-view","message":"Markdown table copied to clipboard!"}`. The beta no-view launcher does not guarantee a visible HUD/toast, so this package promises the native result message rather than an on-screen notification.

There is no view, persistent storage, session state, clipboard read, paste, hide, browser or shell operation. Unknown commands/operations fail before effects. `extension:dispose-session` is an inert supported lifecycle operation for the known command. Missing, malformed or non-text argument objects fail before copying.

## Host integration (requires a Tezbar rebuild)

This is compiled source, not a dynamically loaded external Rust plugin. The JSON manifest or an installed `native-v2.json` marker alone cannot register dispatch.

1. Vendor this entire `v2/` package at the stable host path `src-tauri/native-extensions/markdown-table-generator/`, retaining its source, adapter, Cargo manifest/lock, icon, attribution and fixtures. Add this dependency to the host's `src-tauri/Cargo.toml`:

   ```toml
   tezbar-markdown-table-generator = { path = "native-extensions/markdown-table-generator" }
   ```

2. In `src-tauri/src/native_core/extensions/mod.rs`, compile the production adapter beside the existing `v2_sdk`:

   ```rust
   #[path = "../../../native-extensions/markdown-table-generator/tezbar_adapter.rs"]
   mod v2_markdown_table_generator;
   ```

3. In `extensions/v2_runtime.rs`, add `"markdown-table-generator"` to the allowlist in `slug`; add this arm in `commands`:

   ```rust
   "markdown-table-generator" => super::v2_markdown_table_generator::commands(),
   ```

   Add this arm in the asynchronous `handle` match:

   ```rust
   "markdown-table-generator" => {
       super::v2_markdown_table_generator::handle(ctx, command, operation, payload, state).await
   }
   ```

   Keep the existing canonical-ID conversion and SDK. The adapter reads the beta `payload.argumentValues` object, not `arguments`, using the existing `CoreContext` router.

4. Append `manifest.json` as one object in `src-tauri/src/native_core/extensions/v2_catalog.json`. Root `author` is unsupported by the pinned schema; original author credit is in `description` and this package's notices. Preserve the `not-run` verification records until real desktop QA is recorded.

5. Copy `assets/command-icon.png` byte-for-byte to **`src/renderer/public/extensions/icons/markdown-table-generator.png`**. Its manifest URL is `/extensions/icons/markdown-table-generator.png`. Required size: 177,356 bytes; SHA-256: `6b3465b10a40ed075938c17be1aa2a9235dabfb43423a2ff7fd3f4dd24895bc1`.

6. Rebuild the Rust host and renderer, then use the host's normal Native V2 install/catalog flow for the canonical ID. Dispatch and installation must both exist. Run `scripts/extensions-v2-list.mjs` with the rebuilt CLI if available; static catalog JSON does not prove execution. Test launcher arguments and actual clipboard on macOS and Windows before changing verification states. These host changes are integration requirements, not changes performed by this package.

A beta invocation body is:

```json
{
  "extensionId": "com.tezbar.native.markdown-table-generator",
  "commandName": "generate-markdown-table",
  "argumentValues": { "rows": "2", "columns": "3" }
}
```

## Reproducible verification

Run from this package directory. Production dependencies: **none**. Test dependencies are locked and compatible with Rust 1.85. Node 22.13+ supplies TypeScript type stripping for the oracle; Python's `jsonschema` validates the full pinned draft-2020-12 schema.

```sh
cargo test --locked
cargo fmt --check
cargo clippy --all-targets --locked -- -D warnings
cargo +1.85.0 test --locked
cargo +1.85.0 fmt --check
cargo +1.85.0 clippy --all-targets --locked -- -D warnings
rustup target add x86_64-pc-windows-gnu
cargo check --target x86_64-pc-windows-gnu --all-targets --locked
cargo clippy --target x86_64-pc-windows-gnu --all-targets --locked -- -D warnings
node --experimental-vm-modules scripts/oracle.mjs
python3 -m venv .verification/python
.verification/python/bin/pip install jsonschema==4.25.1
.verification/python/bin/python scripts/verify.py
cargo package --allow-dirty --locked
```

The oracle executes the byte-exact pinned upstream TS command with a mocked `@raycast/api`, then compares the native library using a JSON-lines example. It covers ordinary tables, parsing quirks, Unicode whitespace, signs, fractional/trailing text, explicit radix 10, max-safe integers, overflow and the size boundary. For oversized inputs it intercepts the original pre-generation toast to observe actual validation without entering unbounded loops. The exact-limit and asymmetric bounded outputs are compared with executed original output.

`tests/beta_harness.rs` compiles the **unchanged production adapter** beside byte-exact beta `common.rs` and `v2_sdk.rs`. A tiny test-only Tauri type stub permits their headless APIs to compile; no real GUI, clipboard or Tauri application is initialized. It tests routing, acknowledgement ordering, errors, malformed arguments, lifecycle, one copy per invocation, no UI events and no storage effects. Included upstream SDK/config tests use temporary fixture directories, not an application profile. This is SDK contract coverage, not full-host or OS integration.

The Cargo archive includes all fixtures, tests, scripts and notices. To check archive independence, extract it into a disposable directory, run `cargo test --locked`, the Node oracle, and `scripts/verify.py` there. The package does not require the V1 parent or a local Tezbar checkout. V1 `pnpm test`/`pnpm typecheck` can separately run in a disposable copy using its original `package-lock.json` (`pnpm import`, then `pnpm install --frozen-lockfile`), leaving the V1 checkout and lock unchanged. Recent pnpm versions may require allowing `esbuild` builds in the disposable copy's local `pnpm-workspace.yaml` (`allowBuilds: { esbuild: true }`); this verification setup does not belong in the V1 checkout.

## Licensing and provenance

Combined package SPDX: **MIT AND Apache-2.0**. Original command, metadata and icon are MIT, by Visual-Studio-Coder in Raycast's extension repository; the root upstream MIT notice credits Raycast. Native implementation and adapter are MIT. The unmodified Tezbar beta reference fixtures are Apache-2.0 (Copyright 2026 Almat). See `NOTICE`, `licenses/`, and `provenance.json` for pinned paths, hashes and licenses. Fixtures remain byte-exact and are excluded from rustfmt traversal.
