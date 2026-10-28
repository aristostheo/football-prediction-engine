# Touchline demo guide

Touchline is the only shipped interface. `/classic` and `/updated-mockup`
open the current app; the old pages and simulated match data are removed.
Shared Touchline fonts and club crests remain packaged locally. Existing
favourites, theme choices, and saved forecast records keep their storage keys.

## Start the local demo

Stop an existing backend with Ctrl+C, then run from the repository root:

```bash
git pull origin main
cd web
npm ci
npm run build
cd ..
uv run python -m football_predictor --check-data
uv run uvicorn football_predictor.api:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`. The data check reports local history coverage;
it does not update results or spend provider requests. Ensure the history is
current before presenting probabilities for upcoming matches. Use the existing
documented result-sync procedure if it needs updating, then restart the backend.

Use the server's existing `GOAL_API_KEY` for fixtures and `THE_ODDS_API_KEY` for
live odds. Keep keys server-side. Without live credentials, the registered-team
matchup explorer and manual odds comparison remain usable; the app never
substitutes simulated fixtures, odds, or predictions for missing live data.

## A five-minute walkthrough

1. **Match center:** choose a league, inspect its next matchday, then change the
   date. Explain that displayed kickoff times use the viewer's timezone.
2. **Forecast:** choose an upcoming fixture and generate its forecast. Point
   out the home/draw/away probabilities and the training-results cutoff.
3. **Analysis:** open Team performance and Head to head. H2H is context, not a
   production probability input. The scoreline estimate is separate from 1X2.
4. **Betting:** load 1X2 odds once, or enter all three decimal prices manually.
   The model remains independent of the comparison. Goal markets and team
   totals are experimental and use manually entered paired odds; extra live
   betting markets are not implemented.
5. **My teams:** follow a club. Return to the match center and use Following.
6. **Forecast journal:** show that pre-kickoff scheduled forecasts are saved.
   Completed matches show the original prediction against the actual score.
   Pending matches remain pending. Hypothetical matchups are not journalled.
7. **Model studio:** explain the methods. Historical numerical benchmarks are
   explicitly archived snapshots, not a live performance claim.
8. **Mobile/night theme:** check the drawer, long club names, odds fields, and
   journal cards. Escape closes the drawer and restores focus; analysis tabs
   support arrow keys, Home, and End.

## Verification and remaining release work

Automated browser tests use intercepted provider contracts and block external
data requests. They exercise all seven leagues, errors/retries, stale responses,
forecasts, journal results/export, favourites, themes, betting markets, retired
URLs, keyboard navigation, and narrow layouts. Backend tests verify real model
and API behavior separately. This does not establish authenticated live-provider
availability: do one local fixture/forecast/odds smoke check with your own keys.

This cleanup prepares a local demonstration, not a public deployment. Before
opening access to friends, finish account-wide persistent API-budget protection,
public endpoint rate limits, deployed history updates, and hosting resource
verification. Existing caches and journal backfill limits are useful but do
not enforce the provider account's complete daily allowance.

Favourites and journals remain in the same browser/device. No account or
cross-device sync is implied. This cleanup does not change prediction methods,
ensemble weights, calibration, historical results, or live provider endpoints.
