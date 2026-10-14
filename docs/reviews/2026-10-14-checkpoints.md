# Correctness checkpoints: results refresh and prediction replay

Follow-up to the [October 14 review](2026-10-14-review.md). This change repairs data identity and execution correctness; it does not select a new model or claim an improvement in predictive accuracy.

## Results refresh

- Replaced the unavailable `astral-sh/setup-uv@v10` alias with the verified, pinned v10.3.0 commit. Kept the weekly schedule and manual run option; changes to refresh code also trigger a verification run on main.
- Added an Actions summary and a read-only `--check-data` command. They report actual latest match dates and current-season counts rather than treating the retrieval timestamp as the results cutoff.
- Downloaded and validated all 79 configured OpenFootball source files locally. The resulting snapshot has 24,950 fixtures, zero added fixtures, zero score corrections and zero removed fixtures.
- Reconciled 5,039 home/away label cells to explicit club identities. Names such as Bayern München / FC Bayern München, Hoffenheim / TSG 1899 Hoffenheim and Lazio Roma / SS Lazio no longer form separate histories. Existing provider aliases remain registered.
- The removal guard compares canonical identities and still rejects genuine removals. Canonical fixture collisions cause an error; no duplicate fixtures are silently discarded.

**Freshness is still unresolved:** every league's latest result remains September 20, 2026, 24 days before this check. The source downloads succeeded but supplied no newer matches. Fetching a live fixture or market quote does not add completed results to this model. A verified results source covering the missing rounds is still required. Existing gaps in Greek historical seasons are also unchanged.

## Live and historical state

- Live forecasts now apply the same existing long-gap policy as historical feature generation: clear form after a gap over 180 days and regress Elo with the existing 365-day half-life. The policy is applied to copies, leaving cached terminal state unchanged and avoiding repeated regression across requests.
- Both paths canonicalize team labels before constructing state. Registered unseen clubs use the same existing 1400 starting Elo and 50% league-prior mixture in the deployed-policy benchmark helper and runtime.
- Later same-day prospective fixtures no longer fail solely because a completed fixture from that day is stored. They use a cached engine trained only on strictly earlier dates. Same-day rows are excluded from Elo, form, goal-model fitting, outcome priors and H2H. Already-passed kickoffs remain rejected.
- The first same-day request fits an earlier-day league engine once; subsequent requests reuse it. This is additional cold-request work, not an O(1) fit on every request.

The Premier League remains a 25% Elo / 75% Poisson blend. The other six leagues remain Elo-only for 1X2; their scorelines remain separate Poisson estimates. No Elo constants, form windows, blending weights or calibration parameters were tuned.

## Regression evidence

Tests cover the real Sunderland return to the Premier League in August 2025, exact live/historical pre-match feature and probability parity for the same training prefix, unseen-club prior parity, unchanged cached states across repeated forecasts, and mutation of a stored same-day score/result without changing the later forecast's probabilities, context or scoreline components. Refresh tests cover canonical alias migration, collision rejection and the existing removal guard. Coverage reporting is tested against a recent retrieval timestamp with old match dates.

This does not establish equivalence between every research experiment and live retraining. In particular, season-frozen research fits and continuously refreshed runtime fits have different fitting schedules. Prior published benchmark numbers describe their original data version; canonical identity fixes and benchmark-prior alignment can change recomputed scores. Re-run comparable experiments before drawing a model-selection conclusion.

Validation passed: 160 backend tests, 10 frontend tests, `ruff check src tests`, frontend ESLint, the TypeScript/Vite production build and `git diff --check`. No authenticated live fixture/odds requests were made because provider keys are unavailable in this review environment.

## Local use

From the repository root:

```bash
git pull origin main
uv sync --locked
uv run python -m football_predictor --check-data
cd web
npm ci
npm run build
cd ..
uv run uvicorn football_predictor.api:app --host 0.0.0.0 --port 8000
```

Stop the existing API before restarting it. Open `http://localhost:8000`, or your computer's Wi-Fi IP on port 8000 from your phone. Keep API keys in your existing local environment configuration; these changes do not require exposing them.

## Next work

1. Verify a source of newer completed results using the locally configured provider and import through the same validation/removal controls. Do not mark freshness resolved until the actual cutoff advances.
2. Add general backend/frontend CI, beyond the ingestion-only refresh workflow.
3. Fix older journal result backfill, provider request coalescing, odds quote timestamps and the remaining robustness findings from the review.
4. Re-run aligned chronological research comparisons after correctness and source coverage are stable.
