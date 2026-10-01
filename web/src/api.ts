export type Competition = "premier_league" | "super_league_greece";

export interface PredictionRequest {
  competition: Competition;
  kickoff_date: string;
  home_team: string;
  away_team: string;
}

export interface Prediction extends PredictionRequest {
  home_win_probability: number;
  draw_probability: number;
  away_win_probability: number;
  model_policy: string;
  history_through: string;
  history_age_days: number;
}

export interface LiveFixture {
  fixture_id: string;
  competition: Competition;
  kickoff_at: string;
  home_team: string;
  away_team: string;
}

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

export async function getFixtures(
  competition: Competition,
  fixtureDate: string,
): Promise<LiveFixture[]> {
  const params = new URLSearchParams({ competition, date: fixtureDate });
  const response = await fetch(`${API_ROOT}/fixtures?${params}`);
  return parseResponse<LiveFixture[]>(response);
}
