import type { MatchOutcome, Prediction } from "./api";

const STORAGE_KEY = "match-forecast.prospective-scorecard.v1";
const MAX_FORECASTS = 1000;

export interface StoredForecast {
  id: string;
  competition: Prediction["competition"];
  kickoff_date: string;
  kickoff_at: string;
  home_team: string;
  away_team: string;
  forecasted_at: string;
  history_through: string;
  model_policy: string;
  model_probabilities: [number, number, number];
  market_probabilities: [number, number, number] | null;
}

export interface ScoreMetrics {
  count: number;
  logLoss: number;
  brier: number;
  rankedProbabilityScore: number;
  calibrationError: number;
  accuracy: number;
}

export function loadForecasts(): StoredForecast[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isStoredForecast).slice(-MAX_FORECASTS);
  } catch {
    return [];
  }
}

export function saveForecast(prediction: Prediction): StoredForecast[] {
  if (!prediction.kickoff_at) return loadForecasts();
  const marketProbabilities = prediction.market_home_win_probability === null
    ? null
    : [
        prediction.market_home_win_probability,
        prediction.market_draw_probability,
        prediction.market_away_win_probability,
      ] as [number, number, number];
  const forecast: StoredForecast = {
    id: crypto.randomUUID(),
    competition: prediction.competition,
    kickoff_date: prediction.kickoff_date,
    kickoff_at: prediction.kickoff_at,
    home_team: prediction.home_team,
    away_team: prediction.away_team,
    forecasted_at: prediction.forecasted_at,
    history_through: prediction.history_through,
    model_policy: prediction.model_policy,
    model_probabilities: [
      prediction.model_home_win_probability,
      prediction.model_draw_probability,
      prediction.model_away_win_probability,
    ],
    market_probabilities: marketProbabilities,
  };
  const existing = loadForecasts();
  const key = forecastKey(forecast);
  const previous = existing.findIndex((item) => forecastKey(item) === key);
  if (previous >= 0) {
    const previousTime = Date.parse(existing[previous].forecasted_at);
    if (previousTime >= Date.parse(forecast.forecasted_at)) return existing;
    existing.splice(previous, 1);
  }
  const updated = [...existing, forecast].slice(-MAX_FORECASTS);
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  } catch {
    // Storage can be disabled or full; the visible scorecard still stays usable
    // for the current page session.
  }
  return updated;
}

export function forecastKey(forecast: Pick<StoredForecast, "competition" | "kickoff_date" | "home_team" | "away_team">): string {
  return [forecast.competition, forecast.kickoff_date, forecast.home_team, forecast.away_team].join("|");
}

export function calculateMetrics(
  forecasts: StoredForecast[],
  results: Record<string, MatchOutcome | null>,
  probabilities: (forecast: StoredForecast) => [number, number, number] | null,
): ScoreMetrics | null {
  const scored = forecasts.flatMap((forecast) => {
    const actual = results[forecast.id];
    const probs = probabilities(forecast);
    return actual && probs ? [{ actual, probs }] : [];
  });
  if (!scored.length) return null;
  const outcomeIndex: Record<MatchOutcome, number> = { H: 0, D: 1, A: 2 };
  let logLoss = 0;
  let brier = 0;
  let rankedProbabilityScore = 0;
  let calibrationError = 0;
  let correct = 0;
  for (const { actual, probs } of scored) {
    const actualIndex = outcomeIndex[actual];
    logLoss -= Math.log(Math.max(probs[actualIndex], 1e-15));
    brier += probs.reduce((sum, probability, index) => (
      sum + (probability - Number(index === actualIndex)) ** 2
    ), 0);
    const homeObserved = Number(actualIndex === 0);
    const drawObserved = Number(actualIndex === 1);
    rankedProbabilityScore += (
      (probs[0] - homeObserved) ** 2
      + (probs[0] + probs[1] - homeObserved - drawObserved) ** 2
    ) / 2;
    if (probs.indexOf(Math.max(...probs)) === actualIndex) correct += 1;
  }
  const binCount = 5;
  for (let outcomeIndex = 0; outcomeIndex < 3; outcomeIndex += 1) {
    for (let bin = 0; bin < binCount; bin += 1) {
      const lower = bin / binCount;
      const upper = (bin + 1) / binCount;
      const members = scored.filter(({ probs }) => (
        probs[outcomeIndex] >= lower
        && (probs[outcomeIndex] < upper || (bin === binCount - 1 && probs[outcomeIndex] <= upper))
      ));
      if (!members.length) continue;
      const meanProbability = members.reduce((sum, item) => sum + item.probs[outcomeIndex], 0)
        / members.length;
      const observedRate = members.filter((item) => outcomeIndex === outcomeIndexOf(item.actual))
        .length / members.length;
      calibrationError += members.length / (scored.length * 3)
        * Math.abs(meanProbability - observedRate);
    }
  }
  return {
    count: scored.length,
    logLoss: logLoss / scored.length,
    brier: brier / scored.length,
    rankedProbabilityScore: rankedProbabilityScore / scored.length,
    calibrationError,
    accuracy: correct / scored.length,
  };
}

function outcomeIndexOf(outcome: MatchOutcome): number {
  return outcome === "H" ? 0 : outcome === "D" ? 1 : 2;
}

function isStoredForecast(value: unknown): value is StoredForecast {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<StoredForecast>;
  return typeof item.id === "string"
    && (item.competition === "premier_league" || item.competition === "super_league_greece")
    && typeof item.kickoff_date === "string"
    && typeof item.kickoff_at === "string"
    && typeof item.home_team === "string"
    && typeof item.away_team === "string"
    && Array.isArray(item.model_probabilities)
    && item.model_probabilities.length === 3;
}
