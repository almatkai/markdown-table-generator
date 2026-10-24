# Markdown Table Generator for Tezbar

Generate markdown tables from row/column counts in Tezbar on Windows or macOS.

## Command

- **Generate Markdown Table** — takes `# of Rows` and `# of Columns` (integers > 0) and copies a markdown table to clipboard with header `Column 1…N`, separator `---`, and body `Cell r-c`. Shows success or failure toast for invalid input.

## Compatibility

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
