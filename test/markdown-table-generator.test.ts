import assert from "node:assert/strict";
import test, { describe, it } from "node:test";

function generateMarkdownTable(numberOfColumns: number, numberOfRows: number): string {
  let table = "";
  for (let i = 0; i < 2; i++) {
    table += "|";
    for (let col = 0; col < numberOfColumns; col++) {
      table += i === 0 ? ` Column ${col + 1} |` : " --- |";
    }
    table += "\n";
  }
  for (let row = 0; row < numberOfRows; row++) {
    table += "|";
    for (let col = 0; col < numberOfColumns; col++) {
      table += ` Cell ${row + 1}-${col + 1} |`;
    }
    table += "\n";
  }
  return table;
}

describe("generateMarkdownTable", () => {
  it("generates 2x2 table", () => {
    const out = generateMarkdownTable(2, 2);
    const expected = "| Column 1 | Column 2 |\n| --- | --- |\n| Cell 1-1 | Cell 1-2 |\n| Cell 2-1 | Cell 2-2 |\n";
    assert.equal(out, expected);
  });
  it("generates 1x1 table", () => {
    const out = generateMarkdownTable(1, 1);
    assert.equal(out, "| Column 1 |\n| --- |\n| Cell 1-1 |\n");
  });
  it("generates 3x1 table", () => {
    const out = generateMarkdownTable(3, 1);
    assert.equal(out, "| Column 1 | Column 2 | Column 3 |\n| --- | --- | --- |\n| Cell 1-1 | Cell 1-2 | Cell 1-3 |\n");
  });
  it("handles larger table row/col counts", () => {
    const out = generateMarkdownTable(4, 3);
    const lines = out.trim().split("\n");
    assert.equal(lines.length, 5); // header + sep + 3 rows
    assert.match(lines[0], /Column 4/);
    assert.match(lines[4], /Cell 3-4/);
  });
  it("validation rejects non-positive integers", () => {
    const isValid = (r: string, c: string) => {
      const nr = parseInt(r, 10);
      const nc = parseInt(c, 10);
      return Number.isInteger(nr) && Number.isInteger(nc) && nr > 0 && nc > 0;
    };
    assert.equal(isValid("2", "2"), true);
    assert.equal(isValid("0", "2"), false);
    assert.equal(isValid("-1", "2"), false);
    assert.equal(isValid("abc", "2"), false);
    // parseInt("1.5") === 1, so upstream treats "1.5" as valid integer
    assert.equal(isValid("1.5", "2"), true);
  });
});

test("package.json declares Windows+macOS and Tezbar metadata", async () => {
  const pkg = await import("../package.json", { with: { type: "json" } });
  const data = (pkg as unknown as { default: Record<string, unknown> }).default ?? (pkg as unknown as Record<string, unknown>);
  assert.deepEqual((data as { platforms: string[] }).platforms, ["macOS", "Windows"]);
  const tezbar = (data as { tezbar: { platforms: string[]; repository: string; upstream: { commit: string; path: string } } }).tezbar;
  assert.deepEqual(tezbar.platforms, ["macos", "windows"]);
  assert.equal(tezbar.repository, "https://github.com/almatkai/markdown-table-generator");
  assert.equal(tezbar.upstream.path, "extensions/markdown-table-generator");
  assert.equal(tezbar.upstream.commit, "6734d85992290066fd31a7f5bee3cca3d3545a1a");
  const commands = (data as { commands: { platforms: string[] }[] }).commands;
  assert.equal(commands.length, 1);
  for (const cmd of commands) {
    assert.deepEqual(cmd.platforms, ["macOS", "Windows"]);
  }
});
