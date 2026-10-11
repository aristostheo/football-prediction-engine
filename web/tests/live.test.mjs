import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import ts from "typescript";
const load = async (path) => {
  const code = ts.transpileModule(
    readFileSync(new URL(path, import.meta.url), "utf8"),
    {
      compilerOptions: {
        target: ts.ScriptTarget.ES2022,
        module: ts.ModuleKind.ESNext,
      },
    },
  ).outputText;
  return import(
    `data:text/javascript;base64,${Buffer.from(code).toString("base64")}`
  );
};
const live = await load("../src/touchline/live.ts");
const journal = await load("../src/scorecard.ts");
const storage = new Map();
globalThis.window = {
  localStorage: {
    getItem: (key) => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value),
  },
};
const next = new Date(Date.now() + 86400000).toISOString();
const base = {
  competition: "premier_league",
  kickoff_date: next.slice(0, 10),
  kickoff_at: next,
  home_team: "Arsenal FC",
  away_team: "Chelsea FC",
  forecasted_at: new Date().toISOString(),
  history_through: "2026-10-04",
  model_policy: "elo_poisson_25_75",
  model_home_win_probability: 0.5,
  model_draw_probability: 0.3,
  model_away_win_probability: 0.2,
  market_home_win_probability: null,
  market_draw_probability: null,
  market_away_win_probability: null,
  components: {
    top_scorelines: [{ home_goals: 2, away_goals: 1, probability: 0.12 }],
    scoreline_home_goal_rate: 1.8,
    scoreline_away_goal_rate: 0.9,
  },
};

test("odds remove margin and reject incomplete/invalid input", () => {
  const p = live.normalizeOdds(["2", "4", "4"]);
  assert.deepEqual(p, [0.5, 0.25, 0.25]);
  for (const values of [
    ["1", "3", "4"],
    ["2", "", "4"],
    ["2", "NaN", "4"],
    ["Infinity", "3", "4"],
  ])
    assert.throws(() => live.normalizeOdds(values));
});
test("goal map matches backend Poisson normalization without changing 1X2", () => {
  const original = JSON.stringify(base),
    matrix = live.scoreMatrix(base);
  let total = 0;
  for (let h = 0; h <= 12; h++)
    for (let a = 0; a <= 12; a++) total += matrix.probability(h, a);
  assert.ok(Math.abs(total - 1) < 1e-12);
  assert.ok(matrix.probability(2, 1) > 0);
  assert.equal(JSON.stringify(base), original);
  assert.equal(live.scoreMatrix({ ...base, components: {} }), null);
});
test("future cancelled/postponed/finished fixtures cannot be predicted", () => {
  assert.equal(
    live.isUpcoming({ kickoff_at: next, status: "SCHEDULED" }),
    true,
  );
  for (const status of [
    "POSTPONED",
    "PST",
    "CANCELLED",
    "CANC",
    "FINISHED",
    "FT",
  ])
    assert.equal(live.isUpcoming({ kickoff_at: next, status }), false);
  assert.equal(live.isUpcoming({ kickoff_at: "2020-01-01T12:00:00Z" }), false);
});
test("crests are exact and league scoped", () => {
  assert.equal(
    live.localBadge("premier_league", "Arsenal FC"),
    "/mockup/arsenal.png",
  );
  assert.equal(live.localBadge("serie_a", "Arsenal FC"), undefined);
  assert.equal(
    live.localBadge("premier_league", "Arsenal FC Women"),
    undefined,
  );
});
test("journal keeps confirmed results through unavailable checks and accepts corrections", () => {
  const settled = {
    id: "one",
    result: "A",
    home_goals: 0,
    away_goals: 1,
    source: "live_provider",
  };
  const absent = {
    ...settled,
    result: null,
    home_goals: null,
    away_goals: null,
    source: null,
  };
  assert.deepEqual(
    live.mergeSettlements({ one: settled }, { one: absent }).one,
    settled,
  );
  assert.deepEqual(
    live.mergeSettlements(
      { one: settled },
      { one: { ...settled, home_goals: null, away_goals: null } },
    ).one,
    settled,
  );
  const correction = {
    ...settled,
    result: "D",
    home_goals: 1,
    away_goals: 1,
    source: "bundled_history",
  };
  assert.deepEqual(
    live.mergeSettlements({ one: settled }, { one: correction }).one,
    correction,
  );
});
test("journal retains original prediction when result differs and stores exact score", () => {
  storage.clear();
  const [record] = journal.saveForecast(base);
  assert.deepEqual(record.model_probabilities, [0.5, 0.3, 0.2]);
  assert.deepEqual(
    record.predicted_scoreline,
    base.components.top_scorelines[0],
  );
  const before = record.forecasted_at;
  const [compared] = journal.attachMarketComparison(base, [0.6, 0.25, 0.15]);
  assert.equal(compared.forecasted_at, before);
  assert.deepEqual(compared.model_probabilities, [0.5, 0.3, 0.2]);
  const results = { [record.id]: "A" },
    metrics = journal.calculateMetrics(
      [compared],
      results,
      (r) => r.model_probabilities,
    );
  assert.equal(metrics.accuracy, 0);
  assert.ok(Math.abs(metrics.logLoss + Math.log(0.2)) < 1e-12);
  assert.deepEqual(
    journal.loadForecasts()[0].model_probabilities,
    [0.5, 0.3, 0.2],
  );
  journal.removeForecast(record.id);
  assert.equal(journal.loadForecasts().length, 0);
});
test("hypothetical and late forecasts never enter the journal", () => {
  storage.clear();
  journal.saveForecast({ ...base, kickoff_at: null });
  journal.saveForecast({ ...base, kickoff_at: "2020-01-01T12:00:00Z" });
  assert.equal(journal.loadForecasts().length, 0);
});
test("older saved forecasts without scoreline migrate without invented scores", () => {
  storage.clear();
  journal.saveForecast(base);
  const key = "match-forecast.prospective-scorecard.v1";
  const older = JSON.parse(storage.get(key));
  delete older[0].predicted_scoreline;
  storage.set(key, JSON.stringify(older));
  assert.equal(journal.loadForecasts().length, 1);
  assert.equal(journal.loadForecasts()[0].predicted_scoreline, undefined);
});

test("disabled storage retains session forecasts", () => {
  storage.clear();
  const original = window.localStorage.setItem;
  window.localStorage.setItem = () => {
    throw Error("blocked");
  };
  try {
    const first = journal.saveForecast(base, []);
    const other = { ...base, home_team: "Liverpool FC" };
    const both = journal.saveForecast(other, first);
    assert.equal(both.length, 2);
    const removed = journal.removeForecast(first[0].id, both);
    assert.equal(removed.length, 1);
  } finally {
    window.localStorage.setItem = original;
  }
});
test("invalid cached market data is discarded without losing the model forecast", () => {
  storage.clear();
  journal.saveForecast(base);
  const key = "match-forecast.prospective-scorecard.v1";
  const records = JSON.parse(storage.get(key));
  records[0].market_probabilities = "invalid";
  storage.set(key, JSON.stringify(records));
  const [saved] = journal.loadForecasts();
  assert.deepEqual(saved.model_probabilities, [0.5, 0.3, 0.2]);
  assert.equal(saved.market_probabilities, null);
});
