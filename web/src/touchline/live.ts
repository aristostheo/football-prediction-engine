import type { Competition, LiveFixture, MarketOddsQuote, Prediction, Settlement } from "../api";

export function oddsForCalculation(prices: string[], quote?: MarketOddsQuote): string[] {
  return quote
    ? [quote.home_fair_odds, quote.draw_fair_odds, quote.away_fair_odds].map(String)
    : prices;
}

export function marketQuoteNote(quote: MarketOddsQuote): string {
  const stamp = (value: string) => new Date(value).toLocaleString([], {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
  const age = quote.oldest_quote_at
    ? `oldest reported quote ${stamp(quote.oldest_quote_at)} (${quote.timestamped_bookmaker_count ?? 0}/${quote.bookmaker_count} timestamps)`
    : "quote update times unavailable";
  return `Market consensus from ${quote.bookmaker_count} bookmakers · margin removed · fetched ${stamp(quote.fetched_at)} · ${age}`;
}

export function mergeSettlements(
  previous: Record<string, Settlement>,
  incoming: Record<string, Settlement>,
): Record<string, Settlement> {
  const merged = { ...previous };
  for (const [id, item] of Object.entries(incoming)) {
    const old = previous[id];
    if (old?.result && !item.result) continue;
    merged[id] =
      old?.result === item.result && old?.result && item.home_goals == null
        ? { ...item, home_goals: old.home_goals, away_goals: old.away_goals }
        : item;
  }
  return merged;
}

export const leagues: {
  id: Competition;
  name: string;
  country: string;
  code: string;
  color: string;
}[] = [
  {
    id: "premier_league",
    name: "Premier League",
    country: "England",
    code: "PL",
    color: "#674695",
  },
  {
    id: "la_liga",
    name: "La Liga",
    country: "Spain",
    code: "LL",
    color: "#eb5947",
  },
  {
    id: "bundesliga",
    name: "Bundesliga",
    country: "Germany",
    code: "BL",
    color: "#cf3a45",
  },
  {
    id: "serie_a",
    name: "Serie A",
    country: "Italy",
    code: "SA",
    color: "#3071b4",
  },
  {
    id: "ligue_1",
    name: "Ligue 1",
    country: "France",
    code: "L1",
    color: "#38644c",
  },
  {
    id: "primeira_liga",
    name: "Primeira Liga",
    country: "Portugal",
    code: "LP",
    color: "#a98737",
  },
  {
    id: "super_league_greece",
    name: "Super League",
    country: "Greece",
    code: "SL",
    color: "#3e709c",
  },
];
export const leagueName = (id: Competition) =>
  leagues.find((l) => l.id === id)!.name;
export const pct = (value: number) => `${(value * 100).toFixed(1)}%`;
export const teamShort = (name: string) => name.replace(/\s+(FC|CF|AFC)$/i, "");
export function localDate(value: Date | string = new Date()): string {
  const d = typeof value === "string" ? new Date(value) : value;
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
export function dateAfter(value: string, days: number): string {
  const d = new Date(`${value}T12:00:00`);
  d.setDate(d.getDate() + days);
  return localDate(d);
}
export const dateLabel = (value: string, short = false) =>
  new Date(`${value}T12:00:00`).toLocaleDateString([], {
    weekday: short ? "short" : "long",
    day: "numeric",
    month: short ? "short" : "long",
  });
export const timeLabel = (value: string) =>
  new Date(value).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
export const message = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "The request failed. Please try again.";
const unavailable = new Set([
  "PST",
  "POSTPONED",
  "CANC",
  "CANCELLED",
  "CANCELED",
  "SUSP",
  "SUSPENDED",
  "ABD",
  "ABANDONED",
  "FINISHED",
  "FT",
  "AET",
  "PEN",
  "PENALTIES",
]);
export const isUpcoming = (fixture: LiveFixture) =>
  Date.parse(fixture.kickoff_at) > Date.now() &&
  !unavailable.has((fixture.status ?? "").toUpperCase());
export function normalizeOdds(prices: string[]): [number, number, number] {
  const odds = prices.map(Number);
  if (odds.length !== 3 || odds.some((n) => !Number.isFinite(n) || n <= 1))
    throw new Error("Enter three decimal odds greater than 1.");
  const raw = odds.map((n) => 1 / n),
    total = raw.reduce((a, b) => a + b, 0);
  return raw.map((n) => n / total) as [number, number, number];
}
export const modelProbabilities = (p: Prediction): [number, number, number] => [
  p.model_home_win_probability,
  p.model_draw_probability,
  p.model_away_win_probability,
];

// Exact, league-scoped mappings only. Other clubs use their provider badge or
// an initials fallback; similar club names must never share a guessed crest.
const staticBadges: Partial<Record<Competition, Record<string, string>>> = {
  premier_league: {
    "Arsenal FC": "arsenal",
    "Chelsea FC": "chelsea",
    "Manchester City FC": "man-city",
    "Liverpool FC": "liverpool",
    "Brighton & Hove Albion FC": "brighton",
    "Tottenham Hotspur FC": "tottenham",
  },
  la_liga: {
    "Real Madrid CF": "real-madrid",
    "FC Barcelona": "barcelona",
    "Club Atlético de Madrid": "atletico",
    "Real Betis Balompié": "betis",
  },
  bundesliga: {
    "FC Bayern München": "bayern",
    "Borussia Dortmund": "dortmund",
    "RB Leipzig": "leipzig",
    "Eintracht Frankfurt": "frankfurt",
  },
  serie_a: {
    "FC Internazionale Milano": "inter",
    "AC Milan": "milan",
    "Juventus FC": "juventus",
    "SSC Napoli": "napoli",
  },
  ligue_1: {
    "Paris Saint-Germain FC": "psg",
    "Olympique de Marseille": "marseille",
    "AS Monaco FC": "monaco",
    "Lille OSC": "lille",
  },
  primeira_liga: {
    "Sport Lisboa e Benfica": "benfica",
    "Sporting Clube de Portugal": "sporting",
    "FC Porto": "porto",
    "Sporting Clube de Braga": "braga",
  },
  super_league_greece: {
    "Olympiakos Piraeus": "olympiacos",
    Panathinaikos: "panathinaikos",
    "PAOK Saloniki": "paok",
    "AEK Athen": "aek",
  },
};
export const localBadge = (league: Competition, name: string) => {
  const id = staticBadges[league]?.[name];
  return id ? `/mockup/${id}.png` : undefined;
};
export function scoreMatrix(prediction: Prediction) {
  const h =
    prediction.components.scoreline_home_goal_rate ??
    prediction.components.home_goal_rate;
  const a =
    prediction.components.scoreline_away_goal_rate ??
    prediction.components.away_goal_rate;
  if (h == null || a == null || h <= 0 || a <= 0) return null;
  const poisson = (rate: number) => {
    const p = [Math.exp(-Math.min(rate, 8))];
    for (let i = 1; i <= 12; i++) p.push((p[i - 1] * Math.min(rate, 8)) / i);
    return p;
  };
  const home = poisson(h),
    away = poisson(a),
    total = home.reduce((x, y) => x + y, 0) * away.reduce((x, y) => x + y, 0);
  return {
    homeRate: h,
    awayRate: a,
    probability: (hg: number, ag: number) => (home[hg] * away[ag]) / total,
  };
}
