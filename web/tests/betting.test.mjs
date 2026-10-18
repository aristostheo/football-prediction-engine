import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import ts from "typescript";

const code = ts.transpileModule(
  readFileSync(new URL("../src/touchline/betting.ts", import.meta.url), "utf8"),
  {
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.ESNext,
    },
  },
).outputText;
const betting = await import(
  `data:text/javascript;base64,${Buffer.from(code).toString("base64")}`
);

test("two-way prices remove margin using full precision and reject incomplete or invalid quotes", () => {
  assert.deepEqual(
    betting.comparePair(["1.8", "2.2"]),
    [0.55, 0.44999999999999996],
  );
  const exact = betting.comparePair(["1.923456", "2.012345"]);
  assert.ok(
    Math.abs(exact[0] - 1 / 1.923456 / (1 / 1.923456 + 1 / 2.012345)) < 1e-14,
  );
  for (const values of [
    ["", "2"],
    ["1", "2"],
    ["Infinity", "2"],
    ["NaN", "2"],
    ["2"],
    ["2", "3", "4"],
  ])
    assert.throws(() => betting.comparePair(values));
});
test("result-derived comparisons do not normalize overlapping double chance outcomes", () => {
  const double = betting.derivedMarket(
    { key: "double_chance" },
    [0.5, 0.3, 0.2],
  );
  assert.deepEqual(double, [0.8, 0.5, 0.7]);
  assert.equal(
    double.reduce((a, b) => a + b),
    2,
  );
  const dnb = betting.derivedMarket({ key: "draw_no_bet" }, [0.5, 0.3, 0.2]);
  assert.ok(Math.abs(dnb[0] - 5 / 7) < 1e-12);
  assert.ok(Math.abs(dnb[1] - 2 / 7) < 1e-12);
  assert.equal(betting.derivedMarket({ key: "btts" }, [0.5, 0.3, 0.2]), null);
  assert.equal(betting.derivedMarket({ key: "double_chance" }, null), null);
});
test("display prices have two decimals without changing probabilities and differences use percentage points", () => {
  assert.equal(betting.price(1.923456), "1.92");
  assert.equal(betting.price(null), "—");
  assert.equal(betting.price(Infinity), "—");
  assert.equal(betting.difference(0.58, 0.55), "+3.0 pp");
  assert.equal(betting.difference(0.55, 0.58), "-3.0 pp");
  assert.equal(betting.difference(0.5, 0.50000001), "0.0 pp");
});
