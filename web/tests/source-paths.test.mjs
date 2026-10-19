import assert from "node:assert/strict";
import { readdirSync } from "node:fs";
import { test } from "node:test";

test("source module names resolve unambiguously on case-insensitive systems", () => {
  const root = new URL("../src/", import.meta.url);
  const modules = new Map();
  for (const path of readdirSync(root, { recursive: true })) {
    if (!/\.[cm]?[jt]sx?$/.test(path)) continue;
    const key = path.replace(/\.[cm]?[jt]sx?$/, "").toLowerCase();
    assert.equal(
      modules.has(key),
      false,
      `Module name collision: ${modules.get(key)} and ${path}`,
    );
    modules.set(key, path);
  }
});
