# Betting Insights

The app now has a **Betting insights** workspace page alongside the per-match
**Betting** tab. It summarizes upcoming forecasts already saved in the current
browser and places each outcome's independent model probability beside its
saved, margin-removed market probability.

## Data and behavior

- Forecast cards are saved when the user generates a forecast for a scheduled
  match before kickoff. Hypothetical forecasts are not included.
- Market probabilities appear only after the user loads or manually enters and
  compares 1X2 odds in Match center. Model forecasts remain independent; the
  page does not blend or replace them with market odds.
- Differences are shown in percentage points and the largest absolute outcome
  gap sorts first. A gap is not called a bet, guaranteed value, expected return,
  or staking recommendation.
- Live bookmaker source/count/time or manual-entry provenance is shown with the
  saved comparison. No odds are fetched in bulk; the page makes no API calls.
- Local forecasts are stored in this browser's existing forecast journal. They
  do not sync across browsers or devices.
- Users can filter by competition and open the Forecast journal. The existing
  match-level Betting tab remains the place to inspect result, totals, team
  totals, and scoreline markets for one fixture.

## Verification

Browser coverage checks saved live-market comparisons, model-only records,
competition filtering, mobile/desktop overflow, and confirms navigating to the
new page does not request more odds. Odds are mocked in browser tests; no live
provider credits are used.
