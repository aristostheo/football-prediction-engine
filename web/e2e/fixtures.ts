import { test as base, expect, type Page, type Request } from "@playwright/test";
import type { Competition, LiveFixture, MarketOddsQuote, Prediction, PredictionRequest } from "../src/api";

export const NOW = "2026-10-18T16:00:00Z";
export const DAY = "2026-10-20";
export const teams: Record<Competition, string[]> = {
  premier_league: ["Nottingham Forest FC", "Arsenal FC", "Wolverhampton Wanderers FC", "Brighton & Hove Albion FC"],
  super_league_greece: ["Olympiakos Piraeus", "PAOK Saloniki", "Panathinaikos", "AEK Athens"],
  la_liga: ["Real Madrid", "FC Barcelona", "Celta Vigo", "Atlético Madrid"],
  bundesliga: ["FC Bayern München", "Borussia Dortmund", "TSG 1899 Hoffenheim", "Bayer Leverkusen"],
  serie_a: ["Juventus", "Inter", "SS Lazio", "AC Milan"],
  ligue_1: ["Paris Saint-Germain", "Olympique de Marseille", "AS Monaco", "Olympique Lyonnais"],
  primeira_liga: ["Sporting CP", "FC Porto", "SL Benfica", "Vitória Guimarães"],
};
export const quote: MarketOddsQuote = {
  home_fair_odds: 6.08958031, draw_fair_odds: 4.04658092, away_fair_odds: 1.69876452,
  bookmaker_count: 2, fetched_at: "2026-10-18T15:50:00Z",
  oldest_quote_at: "2026-10-18T15:45:00Z", newest_quote_at: "2026-10-18T15:48:00Z",
  timestamped_bookmaker_count: 2, bookmakers: ["test-book-a", "test-book-b"], source: "Offline test consensus",
};

export function fixtures(competition: Competition, day = DAY): LiveFixture[] {
  return Array.from({ length: 10 }, (_, index) => ({
    fixture_id: `${competition}-${day}-${index}`,
    competition, kickoff_at: `${day}T${String(14 + index % 8).padStart(2, "0")}:00:00Z`,
    home_team: teams[competition][index % 4], away_team: teams[competition][(index + 1) % 4],
    home_badge_url: "https://media.goal-api.com/badges/test-unavailable.svg",
    status: "SCHEDULED", venue: "Offline test stadium",
  }));
}

function prediction(body: PredictionRequest): Prediction {
  const raw = body.odds_home && body.odds_draw && body.odds_away
    ? [1 / body.odds_home, 1 / body.odds_draw, 1 / body.odds_away] : null;
  const market = raw?.map(value => value / raw.reduce((a, b) => a + b, 0));
  return {
    ...body, kickoff_at: body.kickoff_at ?? null,
    home_win_probability: .196, draw_probability: .23, away_win_probability: .574,
    model_home_win_probability: .196, model_draw_probability: .23, model_away_win_probability: .574,
    market_home_win_probability: market?.[0] ?? null, market_draw_probability: market?.[1] ?? null,
    market_away_win_probability: market?.[2] ?? null,
    model_policy: "elo_poisson_25_75", history_through: "2026-10-17", history_age_days: 3,
    forecasted_at: NOW,
    context: {
      home_elo: 1450, away_elo: 1700, home_form_matches: 5, away_form_matches: 5,
      home_form_points_per_match: 1.2, away_form_points_per_match: 2,
      home_form_goals_for_per_match: 1, away_form_goals_for_per_match: 2,
      home_form_goals_against_per_match: 1.6, away_form_goals_against_per_match: .8,
      home_venue_points_per_match: 1.4, away_venue_points_per_match: 1.8,
      home_form_results: ["L", "W", "D", "L", "W"], away_form_results: ["W", "D", "W", "W", "L"],
      head_to_head_matches: 4, head_to_head_home_wins: 1, head_to_head_draws: 1,
      head_to_head_away_wins: 2, head_to_head_recent: ["2026-03-01 · Nottingham Forest 0–2 Arsenal"],
    },
    components: {
      elo_probabilities: [.196, .23, .574], goal_probabilities: [.196, .23, .574],
      core_model_probabilities: [.196, .23, .574], home_goal_rate: .8, away_goal_rate: 1.7,
      top_scorelines: [{ home_goals: 0, away_goals: 1, probability: .14 }, { home_goals: 1, away_goals: 1, probability: .12 }],
      scoreline_home_goal_rate: .8, scoreline_away_goal_rate: 1.7,
      elo_weight: .25, base_model_weight: 1, league_prior_probabilities: null,
    },
  };
}

type Override = { status?: number; json: unknown } | undefined;
export class MockApi {
  requests: Request[] = [];
  errors: string[] = [];
  runtimeErrors: string[] = [];
  settled = false;
  nextFailures = 0;
  oddsFailures = 0;
  predictionFailures = 0;
  settlementFailures = 0;
  override?: (url: URL, request: Request) => Promise<Override>;

  async install(page: Page) {
    page.on("pageerror", error => this.runtimeErrors.push(error.message));
    await page.clock.setFixedTime(new Date(NOW));
    await page.context().route("**/*", async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== "http://127.0.0.1:4174") {
        // Deliberately fail provider images to exercise local crest/initial fallbacks.
        this.errors.push(`external:${url.hostname}`);
        return route.abort();
      }
      const path = url.pathname;
      if (!/^\/(teams|team-badges|fixtures|odds|predict|scorecard)(\/|$)/.test(path)) {
        if (request.resourceType() === "fetch" || request.resourceType() === "xhr") {
          this.errors.push(`unexpected:${path}`);
          return route.fulfill({ status: 500, json: { detail: `Unmocked API ${path}` } });
        }
        return route.continue();
      }
      this.requests.push(request);
      const custom = await this.override?.(url, request);
      if (custom) return route.fulfill(custom);
      const competition = (url.searchParams.get("competition") ?? "premier_league") as Competition;
      if (path === "/teams") return route.fulfill({ json: teams[competition] });
      if (path === "/team-badges") return route.fulfill({ json: {} });
      if (path === "/fixtures/next") {
        if (this.nextFailures-- > 0) return route.fulfill({ status: 503, json: { detail: "Fixture provider temporarily unavailable" } });
        return route.fulfill({ json: fixtures(competition)[0] });
      }
      if (path === "/fixtures") return route.fulfill({ json: fixtures(competition, url.searchParams.get("date") ?? DAY) });
      if (path === "/odds") {
        if (this.oddsFailures-- > 0) return route.fulfill({ status: 502, json: { detail: "Odds provider temporarily unavailable" } });
        return route.fulfill({ json: quote });
      }
      if (path === "/predict") {
        if (this.predictionFailures-- > 0) return route.fulfill({ status: 400, json: { detail: "Forecast temporarily unavailable" } });
        return route.fulfill({ json: prediction(request.postDataJSON()) });
      }
      if (path === "/scorecard/results") {
        if (this.settlementFailures-- > 0) return route.fulfill({ status: 503, json: { detail: "Results provider temporarily unavailable" } });
        const body = request.postDataJSON();
        return route.fulfill({ json: body.fixtures.map((item: { id: string }) => ({
          id: item.id, result: this.settled ? "H" : null,
          home_goals: this.settled ? 2 : null, away_goals: this.settled ? 0 : null,
          source: this.settled ? "live_provider" : null, check_status: this.settled ? "confirmed" : "pending",
        })) });
      }
      this.errors.push(`unexpected:${path}`);
      return route.fulfill({ status: 500, json: { detail: "Unmocked route" } });
    });
  }
}

export const test = base.extend<{ api: MockApi }>({
  api: [async ({ page }, use) => {
    const api = new MockApi();
    await api.install(page);
    await use(api);
    expect(api.runtimeErrors, "uncaught browser errors").toEqual([]);
    expect(api.errors.filter(error => !error.startsWith("external:media.goal-api.com")), "unmocked requests").toEqual([]);
  }, { auto: true }],
});
export { expect };

export async function openNavigation(page: Page) {
  await expect(page.locator(".tl-topbar")).toBeVisible();
  const menu = page.getByRole("button", { name: "Open navigation", exact: true });
  if (await menu.isVisible()) await menu.click();
}
export async function navigate(page: Page, name: string) {
  await openNavigation(page);
  await page.getByRole("navigation", { name: "Main navigation" })
    .getByRole("button", { name: new RegExp(`^${name}(?:\\s+\\d+)?$`) }).click();
}
export async function ready(page: Page) {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Generate forecast", exact: true })).toBeEnabled();
}
