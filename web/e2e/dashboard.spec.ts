import { test, expect, quote, fixtures, teams, ready, navigate, openNavigation } from "./fixtures";
import type { Page } from "@playwright/test";
import type { Competition } from "../src/api";

const hero = (page: Page) => page.getByRole("region", { name: "Selected match forecast" });
const saved = (page: Page) => page.evaluate(() => JSON.parse(localStorage.getItem("match-forecast.prospective-scorecard.v1") ?? "[]"));
async function marketTab(page: Page) {
  await page.getByRole("tab", { name: "Market comparison", exact: true }).click();
}
async function noPageOverflow(page: Page) {
  const sizes = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    document: document.documentElement.scrollWidth,
  }));
  expect(sizes.document, "horizontal overflow must stay inside scrollable panels").toBeLessThanOrEqual(sizes.viewport + 1);
}
function gate() {
  let release!: () => void;
  const wait = new Promise<void>(resolve => { release = resolve; });
  return { wait, release };
}

test("discovers a crowded matchday, switches all seven leagues and browses a date", async ({ page, api }) => {
  await ready(page);
  await expect(page.locator(".tl-fixture")).toHaveCount(10);
  const labels: [Competition, string][] = [
    ["la_liga", "La Liga"], ["bundesliga", "Bundesliga"], ["serie_a", "Serie A"],
    ["ligue_1", "Ligue 1"], ["primeira_liga", "Primeira Liga"],
    ["super_league_greece", "Super League"], ["premier_league", "Premier League"],
  ];
  for (const [competition, label] of labels) {
    await openNavigation(page);
    await page.locator(".tl-league-list").getByRole("button", { name: new RegExp(label) }).click();
    await expect(hero(page)).toContainText(teams[competition][0].replace(/ FC$/, ""));
    await expect(page.getByRole("button", { name: "Generate forecast", exact: true })).toBeEnabled();
  }
  await page.locator(".tl-date-button").click();
  await page.getByLabel("Choose a matchday").fill("2026-10-23");
  await expect(page.locator(".tl-fixture")).toHaveCount(10);
  await expect(hero(page)).toContainText("Oct 23");
  expect(api.requests.some(r => r.url().includes("date=2026-10-23"))).toBe(true);
  await noPageOverflow(page);
});

test("loads rounded odds, forecasts with full precision and preserves comparison provenance", async ({ page, api }) => {
  await ready(page);
  await marketTab(page);
  await page.getByRole("button", { name: "Load live market odds" }).click();
  const fields = page.locator(".tl-odds-inputs input");
  for (const [index, value] of ["6.09", "4.05", "1.70"].entries()) await expect(fields.nth(index)).toHaveValue(value);
  await page.getByRole("button", { name: "Generate forecast", exact: true }).click();
  await expect(page.locator(".tl-jumbo-probability")).toContainText("57.4");
  const request = api.requests.find(r => new URL(r.url()).pathname === "/predict")!.postDataJSON();
  expect(request.odds_home).toBe(quote.home_fair_odds);
  const before = (await saved(page))[0];
  expect(before.market_source).toBe("live");
  expect(before.market_snapshot.fetched_at).toBe(quote.fetched_at);
  await page.getByRole("button", { name: "Update comparison" }).click();
  const after = (await saved(page))[0];
  expect(after.model_probabilities).toEqual(before.model_probabilities);
  expect(after.forecasted_at).toBe(before.forecasted_at);
  expect(after.market_snapshot).toEqual(before.market_snapshot);
  await fields.nth(0).fill("5.50");
  await page.getByRole("button", { name: "Update comparison" }).click();
  const manual = (await saved(page))[0];
  expect(manual.market_source).toBe("manual");
  expect(manual.market_snapshot).toBeUndefined();
  expect(manual.model_probabilities).toEqual(before.model_probabilities);
  await page.reload();
  await navigate(page, "Forecast journal");
  await expect(page.getByRole("row").filter({ hasText: "Nottingham Forest" })).toContainText("57.4%");
});

test("fixture, forecast and odds failures recover on an explicit retry", async ({ page, api }) => {
  api.nextFailures = 1;
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("Fixture provider temporarily unavailable");
  await page.getByRole("button", { name: "Retry fixture search" }).click();
  await expect(page.getByRole("button", { name: "Generate forecast", exact: true })).toBeEnabled();
  api.predictionFailures = 1;
  await page.getByRole("button", { name: "Generate forecast", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Forecast temporarily unavailable");
  await page.getByRole("button", { name: "Generate forecast", exact: true }).click();
  await expect(page.locator(".tl-jumbo-probability")).toContainText("57.4");
  await marketTab(page);
  api.oddsFailures = 1;
  await page.getByRole("button", { name: "Load live market odds" }).click();
  await expect(page.getByRole("alert")).toContainText("Odds provider temporarily unavailable");
  await page.getByRole("button", { name: "Load live market odds" }).click();
  await expect(page.locator(".tl-odds-inputs input").first()).toHaveValue("6.09");
});

test("a late league response cannot replace the selected league", async ({ page, api }) => {
  const pending = gate();
  api.override = async url => {
    if (url.pathname === "/fixtures/next" && url.searchParams.get("competition") === "premier_league") {
      await pending.wait;
      return { json: fixtures("premier_league")[0] };
    }
  };
  await page.goto("/");
  try {
    await expect(page.getByRole("status")).toContainText("Finding your next match");
    await openNavigation(page);
    await page.locator(".tl-league-list").getByRole("button", { name: /La Liga/ }).click();
    await expect(hero(page)).toContainText("Real Madrid");
    const received = page.waitForResponse(response => response.url().includes("/fixtures/next?") && response.url().includes("premier_league"));
    pending.release();
    await received;
    await expect(hero(page)).toContainText("Real Madrid");
    await expect(hero(page)).not.toContainText("Nottingham Forest");
  } finally { pending.release(); }
});

test("late date, forecast and odds responses cannot overwrite a newer selection", async ({ page, api }) => {
  await ready(page);
  const pending = gate();
  api.override = async url => {
    if (url.pathname === "/fixtures" && url.searchParams.get("date") === "2026-10-23") {
      await pending.wait;
      return { json: fixtures("premier_league", "2026-10-23") };
    }
  };
  await page.locator(".tl-date-button").click();
  try {
    await page.getByLabel("Choose a matchday").fill("2026-10-23");
    await page.getByLabel("Choose a matchday").fill("2026-10-24");
    await expect(hero(page)).toContainText("Oct 24");
    const response = page.waitForResponse(r => r.url().includes("date=2026-10-23"));
    pending.release();
    await response;
    await expect(hero(page)).toContainText("Oct 24");
  } finally { pending.release(); }
  const odds = gate(), forecast = gate();
  api.override = async url => {
    if (url.pathname === "/odds") { await odds.wait; return { json: quote }; }
    if (url.pathname === "/predict") { await forecast.wait; return { status: 400, json: { detail: "Stale forecast failure" } }; }
  };
  await marketTab(page);
  try {
    await page.getByRole("button", { name: "Load live market odds" }).click();
    await page.getByRole("button", { name: "Generate forecast", exact: true }).click();
    await page.locator(".tl-fixture").nth(1).click();
    const oddsResponse = page.waitForResponse(r => new URL(r.url()).pathname === "/odds");
    const forecastResponse = page.waitForResponse(r => new URL(r.url()).pathname === "/predict");
    odds.release(); forecast.release();
    await Promise.all([oddsResponse, forecastResponse]);
    await expect(page.getByRole("button", { name: "Generate forecast", exact: true })).toBeEnabled();
    await expect(page.getByRole("alert")).toHaveCount(0);
    await marketTab(page);
    await expect(page.locator(".tl-odds-inputs input").first()).toHaveValue("");
    expect(await saved(page)).toHaveLength(0);
  } finally { odds.release(); forecast.release(); }
});

test("journal settles a model disagreement, retains it through failures and exports original probabilities", async ({ page, api }) => {
  await ready(page);
  await page.getByRole("button", { name: "Generate forecast", exact: true }).click();
  await expect(page.locator(".tl-jumbo-probability")).toContainText("57.4");
  const original = (await saved(page))[0];
  await page.clock.setFixedTime(new Date("2026-10-22T16:00:00Z"));
  api.settled = true;
  await navigate(page, "Forecast journal");
  const row = page.getByRole("row").filter({ hasText: "Nottingham Forest" });
  await expect(row).toContainText("2–0");
  await expect(row).toContainText("57.4%");
  await expect(row).toContainText("Top pick missed");
  api.settlementFailures = 1;
  await page.getByRole("button", { name: "Check results", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Previously checked results remain visible");
  await expect(row).toContainText("2–0");
  api.settled = false;
  await page.getByRole("button", { name: "Check results", exact: true }).click();
  await expect(row).toContainText("2–0");
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV", exact: true }).click();
  const download = await downloadPromise;
  const stream = await download.createReadStream();
  const chunks = [];
  for await (const chunk of stream!) chunks.push(chunk);
  const csv = Buffer.concat(chunks).toString("utf8");
  expect(csv).toContain('"0.196","0.23","0.574"');
  expect(csv).toContain('"Market snapshot fetched at"');
  expect((await saved(page))[0].model_probabilities).toEqual(original.model_probabilities);
  await page.reload();
  await navigate(page, "Forecast journal");
  await expect(row).toContainText("2–0");
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: /Delete forecast Nottingham Forest/ }).click();
  await expect(page.locator(".tl-scorecard-table tbody tr")).toHaveCount(0);
});

test("explorer validates registered clubs and keeps hypothetical forecasts out of the journal", async ({ page, api }) => {
  await ready(page);
  await page.getByRole("button", { name: "Explore a matchup" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("Home team", { exact: true }).fill("Incorrect FC");
  await dialog.getByRole("button", { name: "Explore matchup", exact: true }).click();
  await expect(dialog.getByRole("alert")).toBeVisible();
  expect(api.requests.filter(r => new URL(r.url()).pathname === "/predict")).toHaveLength(0);
  await dialog.getByLabel("Home team", { exact: true }).fill(teams.premier_league[2]);
  await dialog.getByLabel("Away team", { exact: true }).fill(teams.premier_league[3]);
  await dialog.getByRole("button", { name: "Explore matchup", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(hero(page)).toContainText("Wolverhampton");
  await page.getByRole("button", { name: "Generate forecast", exact: true }).click();
  await expect(page.locator(".tl-jumbo-probability")).toContainText("57.4");
  const request = api.requests.find(r => new URL(r.url()).pathname === "/predict")!.postDataJSON();
  expect(request.kickoff_at).toBeUndefined();
  expect(await saved(page)).toHaveLength(0);
});

test("favourites and theme survive reload and filter the loaded matchday", async ({ page }) => {
  await ready(page);
  await page.getByRole("button", { name: "Follow Nottingham Forest FC", exact: true }).click();
  await page.getByRole("button", { name: "Following", exact: true }).click();
  await expect(page.locator(".tl-fixture")).toHaveCount(5);
  await page.getByRole("button", { name: "Switch to night theme" }).click();
  await expect(page.locator(".tl-app")).toHaveClass(/tl-night/);
  await page.reload();
  await expect(page.getByRole("button", { name: "Unfollow Nottingham Forest FC", exact: true })).toBeVisible();
  await expect(page.locator(".tl-app")).toHaveClass(/tl-night/);
  await navigate(page, "My teams");
  await page.getByRole("textbox", { name: "Search clubs" }).fill("Nottingham");
  await expect(page.getByRole("button", { name: "Unfollow Nottingham Forest FC", exact: true })).toBeVisible();
});

test("crowded fixtures, long names, odds, explorer and journal stay contained on narrow screens", async ({ page }, testInfo) => {
  await ready(page);
  const widths = testInfo.project.name.includes("mobile") ? [320, 768, 390] : [1280, 1440];
  for (const width of widths) {
    await page.setViewportSize({ width, height: 900 });
    await page.locator(".tl-fixture").nth(2).click();
    await expect(hero(page)).toContainText("Wolverhampton");
    await noPageOverflow(page);
  }
  await page.getByRole("button", { name: "Generate forecast", exact: true }).click();
  await expect(page.locator(".tl-jumbo-probability")).toContainText("57.4");
  await marketTab(page);
  await page.getByRole("button", { name: "Load live market odds" }).click();
  await expect(page.locator(".tl-odds-inputs input").first()).toHaveValue("6.09");
  await noPageOverflow(page);
  await testInfo.attach("market-layout", { body: await page.screenshot({ fullPage: true }), contentType: "image/png" });
  await page.getByRole("button", { name: "Explore a matchup" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  const box = await page.getByRole("dialog").boundingBox();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(page.viewportSize()!.width + 1);
  await page.getByRole("button", { name: "Close matchup explorer" }).click();
  await navigate(page, "Forecast journal");
  await noPageOverflow(page);
  await testInfo.attach("journal-layout", { body: await page.screenshot({ fullPage: true }), contentType: "image/png" });
});
