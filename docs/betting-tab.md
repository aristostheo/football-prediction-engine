# Match Betting tab — checkpoint 2

The live Touchline match-analysis navigation now has a **Betting** tab, replacing
the previous Market comparison label. It contains four sections and preserves
the existing live/manual 1X2 comparison and its journal provenance.

## User flow

1. Choose a scheduled fixture or a hypothetical matchup and open **Betting**.
2. **Result** retains the 1X2 live-odds loader and manual three-price comparison.
   Generate the forecast to see model fair prices, double chance and draw-no-bet.
3. **Goals** defaults to total goals 2.5, with 0.5, 1.5, 3.5 and 4.5 available.
   Both teams to score has its own Yes/No card.
4. **Team totals** defaults to 1.5 goals per team, with 0.5 and 2.5 available.
   Cards show the actual selected home/away club names.
5. **Scores** shows the nine most likely regulation-time scores, their individual
   probabilities and model fair prices. The remaining score probability stays
   visible and is not redistributed over the top nine.

Opening a goal section before forecasting offers **Calculate these markets**.
It uses the existing prediction call and stays in the chosen section when the
forecast arrives. Switching sections does not make extra provider requests.

## Forecast sources and limits

`/predict` now includes a `betting` presentation object computed from that same
forecast. It does not refit a new model or change existing fields:

- `result_forecast`: final headline 1X2, including promoted-team shrinkage where
  applicable. Double chance sums these probabilities; draw-no-bet conditions
  home/away wins on the match not ending in a draw.
- `goal_model`: the existing separate independent-Poisson score distribution,
  used for goal totals, BTTS, team totals and scores. This source is visibly
  labelled **experimental** and may imply different result probabilities from
  the headline forecast. The tab explains the distinction and exposes the
  implied goal-model H/D/A values in its methodology disclosure.

The experimental classwise score alignment from the benchmark was not promoted.
No additional H2H, odds blending, calibration or football features were added.
See the [corrected benchmark](historical-date-correction.md) for mixed totals/BTTS
results and Greek coverage/sample limitations. These markets are estimates, not
a newly validated betting model or evidence of profitable returns.

All markets refer to 90 minutes plus stoppage time, excluding extra time and
penalties. The initial total lines are half-goal lines with no refunds. DNB
displays the draw refund probability separately; its displayed win chance and
fair price are conditional on no refund. API outcomes retain both conditional
`probability` and unconditional `win_probability`, plus `push_probability`.

Model fair odds use `(P(win) + P(loss)) / P(win)`. Prices are displayed to two
decimals; probability calculations retain full precision. Goal-model estimates
are withheld if rates are missing/invalid, capped above the existing rate limit,
or if the 0–12 grid captures less than 99.9% of the underlying probability mass.
Result-derived markets and live result odds remain usable in that case.

## Market comparisons and quota

- **Live loading still covers 1X2 only.** It remains an explicit user action and
  uses the existing server cache, precision handling and source timestamps.
- Double-chance and DNB market comparisons can be derived from those margin-free
  1X2 probabilities. The UI labels them as derived comparisons, not direct
  bookmaker prices for those lines. Overlapping double-chance selections are
  never normalized together as a three-outcome partition.
- Goal/BTTS/team-total cards accept two manually entered decimal prices from
  the same bookmaker and exact line. Inverse prices are normalized to remove
  that pair's margin. Both inputs must be finite and greater than one.
- Editing a price clears its old comparison. Changing the line or selected
  fixture clears manual goal comparisons. A new forecast clears them as well.
  These comparisons are temporary view state; extra-market journal persistence
  and settlement are a later checkpoint. The existing 1X2 journal is preserved.
- Correct scores have model prices only in this checkpoint. A partial list of
  bookmaker score quotes cannot be normalized as if it covered the whole market.
- Differences are percentage points, not a claim of guaranteed edge, expected
  profit or a staking recommendation. Loading/comparing odds never changes the
  independent model prediction.

No new credentials, provider endpoints, background polling or automatic market
fetches were added. Goal API's daily quota is separate from Odds API credits.
The next integration checkpoint will audit real per-event market availability
and add explicitly requested, cached additional live odds.

## Verification

Backend tests cover the API contract, existing 1X2 invariance with/without odds,
refund semantics, separate model provenance, original scoreline parity and
unavailable/extreme-rate handling. Frontend helper tests cover paired margin
removal, precision, formatting and overlapping/conditional result derivatives.

Browser coverage includes the existing full-app flows plus all four Betting
sections, calculation before forecasting, manual input validation, line/fixture
resets, result-derived market comparisons, unavailable goal estimates and
screenshots of desktop/mobile layouts. Providers are mocked; no real API quota
is consumed by verification.

Verified application revision: `5ffdb43476f6d4bd4765cd6acd9af0741060674f`.
[Successful CI run](https://github.com/aristostheo/football-prediction-engine/actions/runs/39163960971):
360 backend tests, 18 frontend helper tests, 48 browser cases (12 each on desktop
Chromium/WebKit and emulated mobile Chromium/WebKit), lint, production build and
browser TypeScript checks passed. There were no browser retries. Final desktop
goal/score and mobile goal/team/score screenshots were also visually inspected.
Mobile emulation does not replace a physical iPhone/Mac Safari check.

The first CI attempt exposed a JSON test-fixture import requirement before browser
discovery; it was corrected with an explicit JSON import attribute and verified
through local test discovery. The final suite also covers disabled Betting actions
for postponed/finished fixtures, preserving the main forecast eligibility rule.

## Run locally

Stop the running backend with Ctrl+C, then from the repository root:

```bash
git pull origin main
cd web
npm run build
cd ..
uv run uvicorn football_predictor.api:app --host 0.0.0.0 --port 8000
```

Refresh the browser and open a match → Betting. Both frontend and backend need
this update because `/predict` supplies the new market estimates. No packages
were added. Existing API keys continue to work. The earlier date-repair migration
is separate and only needs to be applied once to an older local synced snapshot.
