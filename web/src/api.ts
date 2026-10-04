export type Competition = "premier_league" | "super_league_greece";

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
  };
  components: {
    elo_probabilities: [number, number, number];
    goal_probabilities: [number, number, number] | null;
    core_model_probabilities: [number, number, number];
    home_goal_rate: number | null;
    away_goal_rate: number | null;
    top_scorelines: Array<{ home_goals: number; away_goals: number; probability: number }>;
    elo_weight: number;
    base_model_weight: number;
    league_prior_probabilities: [number, number, number] | null;
  };
}

export interface MarketOddsQuote {
  home_fair_odds: number;
  draw_fair_odds: number;
  away_fair_odds: number;
  bookmaker_count: number;
  source: string;
  fetched_at: string;
}

export interface LiveFixture {
  fixture_id: string;
  competition: Competition;
  kickoff_at: string;
  home_team: string;
  away_team: string;
}

export interface ScorecardFixture {
  id: string;
  competition: Competition;
  kickoff_date: string;
  home_team: string;
  away_team: string;
}

export type MatchOutcome = "H" | "D" | "A";

const API_ROOT = import.meta.env.DEV ? "/api" : "";

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function predictMatch(request: PredictionRequest): Promise<Prediction> {
  const response = await fetch(`${API_ROOT}/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return parseResponse<Prediction>(response);
}

export async function getMarketOdds(fixture: LiveFixture): Promise<MarketOddsQuote> {
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
  const response = await fetch(`${API_ROOT}/teams?${new URLSearchParams({ competition })}`);
  return parseResponse<string[]>(response);
}

export async function getNextFixture(
  competition: Competition,
  fromDate: string,
): Promise<LiveFixture | null> {
  const params = new URLSearchParams({ competition, from: fromDate, days_ahead: "21" });
  const response = await fetch(`${API_ROOT}/fixtures/next?${params}`);
  return parseResponse<LiveFixture | null>(response);
}

export async function getFixtures(
  competition: Competition,
  fixtureDate: string,
): Promise<LiveFixture[]> {
  const params = new URLSearchParams({ competition, date: fixtureDate });
  const response = await fetch(`${API_ROOT}/fixtures?${params}`);
  return parseResponse<LiveFixture[]>(response);
}

export async function getScorecardResults(
  fixtures: ScorecardFixture[],
): Promise<Record<string, MatchOutcome | null>> {
  const results: Record<string, MatchOutcome | null> = {};
  for (let start = 0; start < fixtures.length; start += 500) {
    const response = await fetch(`${API_ROOT}/scorecard/results`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fixtures: fixtures.slice(start, start + 500) }),
    });
    const page = await parseResponse<Array<{ id: string; result: MatchOutcome | null }>>(response);
    for (const item of page) results[item.id] = item.result;
  }
  return results;
}
