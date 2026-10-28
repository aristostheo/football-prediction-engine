# Touchline live dashboard

Touchline is the only app at `/`. Retired `/classic` and `/updated-mockup`
links replace their URL with `/` and open the current dashboard, preserving query
parameters, hash, and browser storage. The previous interfaces and simulator
have been removed; their design history remains in Git and the archived gallery.

## Real data flows

- Seven league catalogues and crest mappings come from `/teams` and
  `/team-badges`. Only the selected league is loaded.
- `/fixtures/next` discovers the next upcoming game. `/fixtures` then loads
  its local calendar day, merging the relevant UTC dates without duplicates.
  Date selection, previous/next days, and favourites filtering remain available.
- `/predict` supplies the production probabilities, actual recent form, Elo,
  venue context, H2H, goal rates, and ranked scorelines. No example numbers are
  substituted when data is missing. The history cutoff remains visible.
- `/odds` loads an optional bookmaker consensus. Manual decimal odds also
  work. Market probabilities have their margin removed and are compared with
  the independent model; they do not change its probabilities.
- Scheduled forecasts generated before kickoff enter the existing browser
  journal automatically. Hypothetical matchups do not. Re-generating before
  kickoff updates that fixture's saved forecast.
- `/scorecard/results` provides confirmed outcomes and regulation-time scores
  from bundled history or the live provider. The journal shows original model
  probabilities, top pick, and saved predicted score beside the actual result.
  It checks every five minutes while visible, or on **Check results**.

The journal keeps the existing storage format and accepts older records without
inventing a historical predicted score. It reports log loss, Brier score, RPS,
accuracy, and calibration. Model/market comparisons use the same settled games.
CSV exports include predictions and confirmed results. Favourites and journal
records remain local to this browser; accounts are not implemented.

## Logos and responsive behavior

Provider crests are preferred, followed by an exact league-specific local
crest, followed by club initials if neither image works. All 30 packaged crests
were visually inspected; the incorrect AEK asset was replaced with AEK Athens.
Provider catalogue coverage may vary and cannot be guaranteed offline.

Day and night themes persist. On phones, navigation becomes a drawer and
journal rows become readable match cards. The fixture ribbon and analysis tabs
scroll within their own containers. Stale fixture, odds, and forecast responses
cannot populate a newly selected matchup.

## Local run

From the repository root, after pulling:

```bash
cd web
npm run build
cd ..
uv run uvicorn football_predictor.api:app --reload
```

Open `http://localhost:8000`. Existing provider keys remain server-side. Stop an
already running server before restarting it. For Vite development, use
`npm run dev` in `web` with the API running separately.

## Verification and limits

Python tests exercise fixture normalization, canonical names, postponed/final
status handling, regulation-time score settlement, and prediction presentation.
Frontend tests exercise odds normalization, score matrices, browser storage,
legacy journal migration, and preservation of original model forecasts.
Browser checks cover real engine outputs for all seven leagues, selections,
odds comparisons, journal settlement, CSV, favourites, delayed responses,
hypothetical games, themes, and widths 320 through 1512 px.

The production prediction method is unchanged. Presentation fields expose
existing form and goal rates; the score lookup supplements the existing result
lookup. The goal map uses the same normalized 0–12 independent-Poisson matrix
as the backend scoreline model, which is distinct from the 1X2 ensemble.

The development workspace has no provider keys. Browser fixture/odds responses
were therefore intercepted test contracts; forecasts came from the real
engine and bundled data. Authenticated provider availability needs a local
smoke check with the user's keys. Empty or unavailable provider results are
shown explicitly. Fixture reads are cached briefly and shared across duplicate
mounts; browsing does not automatically scan all seven leagues.
