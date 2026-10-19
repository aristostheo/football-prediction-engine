import type { BettingMarket } from "../api";

export const price = (value: number | null | undefined) =>
  value != null && Number.isFinite(value) && value > 0 ? value.toFixed(2) : "—";

export function comparePair(values: string[]): [number, number] {
  if (values.length !== 2 || values.some((value) => !value.trim()))
    throw new Error(
      "Enter both decimal prices for the same bookmaker and line.",
    );
  const prices = values.map(Number);
  if (prices.some((value) => !Number.isFinite(value) || value <= 1))
    throw new Error("Decimal prices must be finite numbers greater than 1.");
  const total = 1 / prices[0] + 1 / prices[1];
  return [1 / prices[0] / total, 1 / prices[1] / total];
}

export function derivedMarket(
  market: BettingMarket,
  result: [number, number, number] | null,
): number[] | null {
  if (
    !result ||
    result.some((p) => !Number.isFinite(p) || p <= 0) ||
    Math.abs(result.reduce((a, b) => a + b, 0) - 1) > 1e-9
  )
    return null;
  const [home, draw, away] = result;
  if (market.key === "double_chance")
    return [home + draw, away + draw, home + away];
  if (market.key === "draw_no_bet")
    return [home / (home + away), away / (home + away)];
  return null;
}

export const difference = (model: number, market: number) => {
  const delta = (model - market) * 100;
  return `${Math.abs(delta) < 0.05 ? "" : delta > 0 ? "+" : ""}${Math.abs(delta) < 0.05 ? "0.0" : delta.toFixed(1)} pp`;
};
