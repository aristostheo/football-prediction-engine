export type Competition =
  | "premier_league"
  | "super_league_greece"
  | "la_liga"
  | "bundesliga"
  | "serie_a"
  | "ligue_1"
  | "primeira_liga";

export interface PredictionRequest {
  competition: Competition;
  kickoff_date: string;
  kickoff_at?: string;
  home_team: string;
  away_team: string;
  odds_home?: number;
  odds_draw?: number;
  odds_away?: number;
}

export interface Prediction extends Omit<PredictionRequest, "kickoff_at"> {
  kickoff_at: string | null;
  home_win_probability: number;
  draw_probability: number;
  away_win_probability: number;
  model_policy: string;
  history_through: string;
  history_age_days: number;
  forecasted_at: string;
  model_home_win_probability: number;
  model_draw_probability: number;
  model_away_win_probability: number;
  market_home_win_probability: number | null;
  market_draw_probability: number | null;
  market_away_win_probability: number | null;
  context: {
    home_elo: number;
    away_elo: number;
    home_form_matches: number;
    away_form_matches: number;
    home_form_points_per_match: number;
    away_form_points_per_match: number;
    home_form_goals_for_per_match: number;
    away_form_goals_for_per_match: number;
    home_form_goals_against_per_match: number;
    away_form_goals_against_per_match: number;
    home_venue_points_per_match: number;
    away_venue_points_per_match: number;
    head_to_head_matches: number;
    head_to_head_home_wins: number;
    head_to_head_draws: number;
    head_to_head_away_wins: number;
    head_to_head_recent: string[];
    home_form_results?: string[];
    away_form_results?: string[];
  };
  components: {
    elo_probabilities: [number, number, number];
    goal_probabilities: [number, number, number] | null;
    core_model_probabilities: [number, number, number];
    home_goal_rate: number | null;
    away_goal_rate: number | null;
    top_scorelines: Array<{
      home_goals: number;
      away_goals: number;
      probability: number;
    }>;
    elo_weight: number;
    base_model_weight: number;
    league_prior_probabilities: [number, number, number] | null;
    scoreline_home_goal_rate?: number | null;
    scoreline_away_goal_rate?: number | null;
  };
  betting?: BettingForecast;
}

export interface BettingOutcome {
  key: string;
  label: string;
  probability: number;
  win_probability: number;
  push_probability: number;
  fair_odds: number | null;
}
export interface BettingMarket {
  key: string;
  title: string;
  group: "result" | "goals" | "teams" | "scores";
  source: "result_forecast" | "goal_model";
  outcomes: BettingOutcome[];
  line: number | null;
  team: "home" | "away" | null;
}
export interface BettingForecast {
  markets: BettingMarket[];
  goal_status: "experimental" | "unavailable";
  goal_note: string;
  captured_mass: number | null;
  goal_result_probabilities: [number, number, number] | null;
  period: "regulation";
}

export interface MarketOddsQuote {
  home_fair_odds: number;
  draw_fair_odds: number;
  away_fair_odds: number;
  bookmaker_count: number;
  source: string;
  fetched_at: string;
  oldest_quote_at?: string | null;
  newest_quote_at?: string | null;
  timestamped_bookmaker_count?: number;
  bookmakers?: string[];
}

export interface LiveFixture {
  fixture_id: string;
  competition: Competition;
  kickoff_at: string;
  home_team: string;
  away_team: string;
  home_badge_url?: string | null;
  away_badge_url?: string | null;
  status?: string;
  venue?: string | null;
  home_goals?: number | null;
  away_goals?: number | null;
}

export interface ScorecardFixture {
  id: string;
  competition: Competition;
  kickoff_date: string;
  home_team: string;
  away_team: string;
}

export type MatchOutcome = "H" | "D" | "A";

export interface Settlement {
  id: string;
  result: MatchOutcome | null;
  home_goals: number | null;
  away_goals: number | null;
  source: string | null;
  check_status?: "confirmed" | "pending" | "deferred" | "unavailable";
}

const API_ROOT = import.meta.env.DEV ? "/api" : "";

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      detail?: string | Array<{ msg: string }>;
    } | null;
    const detail = payload?.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item.msg).join("; ")
          : `Request failed with status ${response.status}`,
    );
  }
  return response.json() as Promise<T>;
}

// Share reads across StrictMode mounts and repeated league/date switches.
// Rejected requests are never cached, so retry works immediately.
const reads = new Map<string, { expires: number; promise: Promise<unknown> }>();
function cachedRead<T>(url: string, ttl: number): Promise<T> {
  const current = reads.get(url);
  if (current && current.expires > Date.now())
    return current.promise as Promise<T>;
  const entry = {
    expires: Infinity,
    promise: fetch(url).then(parseResponse<T>),
  };
  reads.set(url, entry);
  entry.promise.then(
    () => {
      entry.expires = Date.now() + ttl;
    },
    () => {
      if (reads.get(url) === entry) reads.delete(url);
    },
  );
  if (reads.size > 300)
    for (const [key, value] of reads)
      if (value.expires < Date.now()) reads.delete(key);
  return entry.promise;
}

export async function predictMatch(
  request: PredictionRequest,
): Promise<Prediction> {
  const response = await fetch(`${API_ROOT}/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return parseResponse<Prediction>(response);
}

export async function getMarketOdds(
  fixture: LiveFixture,
): Promise<MarketOddsQuote> {
  const params = new URLSearchParams({
    competition: fixture.competition,
    fixture_id: fixture.fixture_id,
    home_team: fixture.home_team,
    away_team: fixture.away_team,
    kickoff_at: fixture.kickoff_at,
  });
  const response = await fetch(`${API_ROOT}/odds?${params}`);
  return parseResponse<MarketOddsQuote>(response);
}

export async function getTeams(competition: Competition): Promise<string[]> {
  return cachedRead<string[]>(
    `${API_ROOT}/teams?${new URLSearchParams({ competition })}`,
    3600000,
  );
}

export async function getTeamBadges(
  competition: Competition,
): Promise<Record<string, string>> {
  return cachedRead<Record<string, string>>(
    `${API_ROOT}/team-badges?${new URLSearchParams({ competition })}`,
    86400000,
  );
}

export async function getNextFixture(
  competition: Competition,
  fromDate: string,
): Promise<LiveFixture | null> {
  const params = new URLSearchParams({
    competition,
    from: fromDate,
    days_ahead: "21",
  });
  return cachedRead<LiveFixture | null>(
    `${API_ROOT}/fixtures/next?${params}`,
    120000,
  );
}

export async function getFixtures(
  competition: Competition,
  fixtureDate: string,
): Promise<LiveFixture[]> {
  const params = new URLSearchParams({ competition, date: fixtureDate });
  return cachedRead<LiveFixture[]>(`${API_ROOT}/fixtures?${params}`, 600000);
}

export async function getScorecardResults(
  fixtures: ScorecardFixture[],
): Promise<Record<string, MatchOutcome | null>> {
  const details = await getScorecardSettlements(fixtures);
  return Object.fromEntries(
    Object.entries(details).map(([id, item]) => [id, item.result]),
  );
}

const settling = new Map<string, Promise<Record<string, Settlement>>>();
export function getScorecardSettlements(
  fixtures: ScorecardFixture[],
): Promise<Record<string, Settlement>> {
  const key = JSON.stringify(fixtures);
  const existing = settling.get(key);
  if (existing) return existing;
  const request = readSettlements(fixtures);
  settling.set(key, request);
  request.then(
    () => settling.delete(key),
    () => settling.delete(key),
  );
  return request;
}

async function readSettlements(
  fixtures: ScorecardFixture[],
): Promise<Record<string, Settlement>> {
  const results: Record<string, Settlement> = {};
  for (let start = 0; start < fixtures.length; start += 500) {
    const response = await fetch(`${API_ROOT}/scorecard/results`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fixtures: fixtures.slice(start, start + 500) }),
    });
    const page = await parseResponse<Settlement[]>(response);
    for (const item of page) results[item.id] = item;
  }
  return results;
}
