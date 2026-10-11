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
  predicted_scoreline?: {
    home_goals: number;
    away_goals: number;
    probability: number;
  } | null;
  market_fetched_at?: string;
}

export interface ScoreMetrics {
  count: number;
  logLoss: number;
  brier: number;
  rankedProbabilityScore: number;
  calibrationError: number;
  accuracy: number;
}

export interface ConfidenceBucket {
  label: string;
  count: number;
  meanConfidence: number;
  observedAccuracy: number;
}

export function loadForecasts(): StoredForecast[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(isStoredForecast)
      .slice(-MAX_FORECASTS)
      .map((item) => ({
        ...item,
        market_probabilities: validProbabilities(item.market_probabilities)
          ? item.market_probabilities
          : null,
        predicted_scoreline:
          item.predicted_scoreline &&
          Number.isInteger(item.predicted_scoreline.home_goals) &&
          Number.isInteger(item.predicted_scoreline.away_goals) &&
          item.predicted_scoreline.home_goals >= 0 &&
          item.predicted_scoreline.away_goals >= 0 &&
          Number.isFinite(item.predicted_scoreline.probability) &&
          item.predicted_scoreline.probability >= 0 &&
          item.predicted_scoreline.probability <= 1
            ? item.predicted_scoreline
            : undefined,
      }));
  } catch {
    return [];
  }
}

export function saveForecast(
  prediction: Prediction,
  currentForecasts: StoredForecast[] = loadForecasts(),
): StoredForecast[] {
  if (
    !prediction.kickoff_at ||
    !Number.isFinite(Date.parse(prediction.kickoff_at)) ||
    Date.parse(prediction.kickoff_at) <= Date.now() ||
    !Number.isFinite(Date.parse(prediction.forecasted_at)) ||
    Date.parse(prediction.forecasted_at) >= Date.parse(prediction.kickoff_at)
  )
    return currentForecasts;
  const marketProbabilities =
    prediction.market_home_win_probability === null
      ? null
      : ([
          prediction.market_home_win_probability,
          prediction.market_draw_probability,
          prediction.market_away_win_probability,
        ] as [number, number, number]);
  const forecast: StoredForecast = {
    id: createForecastId(),
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
    predicted_scoreline: prediction.components.top_scorelines[0] ?? null,
  };
  const existing = [...currentForecasts];
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

export function removeForecast(
  id: string,
  currentForecasts = loadForecasts(),
): StoredForecast[] {
  return persistForecasts(currentForecasts.filter((item) => item.id !== id));
}

export function attachMarketComparison(
  prediction: Prediction,
  probabilities: [number, number, number],
  currentForecasts = loadForecasts(),
): StoredForecast[] {
  if (!prediction.kickoff_at || Date.parse(prediction.kickoff_at) <= Date.now())
    return currentForecasts;
  return persistForecasts(
    currentForecasts.map((item) =>
      forecastKey(item) === forecastKey(prediction)
        ? {
            ...item,
            market_probabilities: probabilities,
            market_fetched_at: new Date().toISOString(),
          }
        : item,
    ),
  );
}

function persistForecasts(forecasts: StoredForecast[]): StoredForecast[] {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(forecasts));
  } catch {
    /* Keep session usable. */
  }
  return forecasts;
}

export function forecastKey(
  forecast: Pick<
    StoredForecast,
    "competition" | "kickoff_date" | "home_team" | "away_team"
  >,
): string {
  return [
    forecast.competition,
    forecast.kickoff_date,
    forecast.home_team,
    forecast.away_team,
  ].join("|");
}

function createForecastId(): string {
  const uuid = globalThis.crypto?.randomUUID?.();
  if (uuid) return uuid;
  // randomUUID is unavailable in some browsers on a local-network HTTP origin.
  return `forecast-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}${Math.random().toString(36).slice(2)}`;
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
    brier += probs.reduce(
      (sum, probability, index) =>
        sum + (probability - Number(index === actualIndex)) ** 2,
      0,
    );
    const homeObserved = Number(actualIndex === 0);
    const drawObserved = Number(actualIndex === 1);
    rankedProbabilityScore +=
      ((probs[0] - homeObserved) ** 2 +
        (probs[0] + probs[1] - homeObserved - drawObserved) ** 2) /
      2;
    if (probs.indexOf(Math.max(...probs)) === actualIndex) correct += 1;
  }
  const binCount = 5;
  for (let outcomeIndex = 0; outcomeIndex < 3; outcomeIndex += 1) {
    for (let bin = 0; bin < binCount; bin += 1) {
      const lower = bin / binCount;
      const upper = (bin + 1) / binCount;
      const members = scored.filter(
        ({ probs }) =>
          probs[outcomeIndex] >= lower &&
          (probs[outcomeIndex] < upper ||
            (bin === binCount - 1 && probs[outcomeIndex] <= upper)),
      );
      if (!members.length) continue;
      const meanProbability =
        members.reduce((sum, item) => sum + item.probs[outcomeIndex], 0) /
        members.length;
      const observedRate =
        members.filter((item) => outcomeIndex === outcomeIndexOf(item.actual))
          .length / members.length;
      calibrationError +=
        (members.length / (scored.length * 3)) *
        Math.abs(meanProbability - observedRate);
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

export function calculateTopPickCalibration(
  forecasts: StoredForecast[],
  results: Record<string, MatchOutcome | null>,
  probabilities: (forecast: StoredForecast) => [number, number, number] | null,
): ConfidenceBucket[] {
  const ranges = [
    { lower: 0.3, upper: 0.4, label: "30–40%" },
    { lower: 0.4, upper: 0.5, label: "40–50%" },
    { lower: 0.5, upper: 0.55, label: "50–55%" },
    { lower: 0.55, upper: 0.6, label: "55–60%" },
    { lower: 0.6, upper: 0.65, label: "60–65%" },
    { lower: 0.65, upper: 0.7, label: "65–70%" },
    { lower: 0.7, upper: 0.75, label: "70–75%" },
    { lower: 0.75, upper: 0.8, label: "75–80%" },
    { lower: 0.8, upper: 1.01, label: "80%+" },
  ];
  return ranges.flatMap((range) => {
    const members = forecasts.flatMap((forecast) => {
      const actual = results[forecast.id];
      const probs = probabilities(forecast);
      if (
        !actual ||
        !probs ||
        probs.some((probability) => !Number.isFinite(probability))
      )
        return [];
      const confidence = Math.max(...probs);
      if (confidence < range.lower || confidence >= range.upper) return [];
      const predictedIndex = probs.indexOf(confidence);
      const actualIndex = actual === "H" ? 0 : actual === "D" ? 1 : 2;
      return [{ confidence, correct: predictedIndex === actualIndex }];
    });
    if (!members.length) return [];
    return [
      {
        label: range.label,
        count: members.length,
        meanConfidence:
          members.reduce((sum, item) => sum + item.confidence, 0) /
          members.length,
        observedAccuracy:
          members.filter((item) => item.correct).length / members.length,
      },
    ];
  });
}

function outcomeIndexOf(outcome: MatchOutcome): number {
  return outcome === "H" ? 0 : outcome === "D" ? 1 : 2;
}

function isStoredForecast(value: unknown): value is StoredForecast {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<StoredForecast>;
  return (
    typeof item.id === "string" &&
    [
      "premier_league",
      "super_league_greece",
      "la_liga",
      "bundesliga",
      "serie_a",
      "ligue_1",
      "primeira_liga",
    ].some((competition) => competition === item.competition) &&
    typeof item.kickoff_date === "string" &&
    typeof item.kickoff_at === "string" &&
    typeof item.home_team === "string" &&
    typeof item.away_team === "string" &&
    Number.isFinite(Date.parse(item.forecasted_at ?? "")) &&
    Number.isFinite(Date.parse(item.kickoff_at)) &&
    Date.parse(item.forecasted_at ?? "") < Date.parse(item.kickoff_at) &&
    Array.isArray(item.model_probabilities) &&
    item.model_probabilities.length === 3 &&
    item.model_probabilities.every(
      (p) => Number.isFinite(p) && p >= 0 && p <= 1,
    ) &&
    Math.abs(item.model_probabilities.reduce((a, b) => a + b, 0) - 1) < 0.01
  );
}

function validProbabilities(value: unknown): value is [number, number, number] {
  return (
    Array.isArray(value) &&
    value.length === 3 &&
    value.every(
      (p) => typeof p === "number" && Number.isFinite(p) && p >= 0 && p <= 1,
    ) &&
    Math.abs(value.reduce((sum, p) => sum + p, 0) - 1) < 0.01
  );
}
