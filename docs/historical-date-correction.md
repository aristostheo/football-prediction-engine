# Historical date correction and repeated betting-market benchmark

Completed 2026-10-18. This checkpoint fixes historical chronology; it does not change the production model recipe, market/model separation or the frontend. The Betting tab remains the next feature checkpoint.

## Source verification and correction

All 79 bundled OpenFootball sources were downloaded and checked against the original manifest. After normalizing CRLF to LF, every content hash matches. The reparse produces the same 24,950 matches and exactly the same teams, scores, results, source URLs and retrieval timestamps. Only 268 date fields change. No Goal API or Odds API requests were made.

The old parser assigned every omitted-year July/August header to the starting year of a season. That put July 2020 restart fixtures in July 2019 and Serie A’s August 2020 finish in August 2019. The initial check found 258 pre-August rows and therefore missed ten August fixtures.

| League | Corrected dates |
|---|---:|
| Premier League | 66 |
| La Liga | 57 |
| Serie A | 98 |
| Primeira Liga | 47 |
| **Total** | **268** |

Example: AFC Bournemouth–Newcastle United 1–4 moves from 2019-07-01 to 2020-07-01. Serie A’s final ten fixtures move from August 2019 to August 2020. Greece, Bundesliga and Ligue 1 have no changed regular-season dates. Some discarded Greek playoff headers also resolve differently; they remain excluded from the dataset.

Omitted years now use the weekday, month and day to choose between the two season years. This works with postponed fixtures listed out of order, a season continuing into August, leap days and legitimate first-year July dates. A header with no calendar-consistent year fails closed. Explicit years remain authoritative, including when a source contains a weekday typo. All 79 audited files have zero unresolved omitted-year headers and zero explicit weekday mismatches.

The bundled snapshot and checksum manifest were rebuilt. Per-source hashes remain the original LF-normalized hashes and record the new inference rule. The reviewed correction map is [date_corrections.json](../data/model/date_corrections.json). The ordinary refresh removal guard remains unchanged; the reviewed migration does not enable arbitrary removal acceptance.

## Repeated evaluation

The same 33 expanding-season folds and 10,984 distinct matches were used, with identical test fixture identities. Training-only alpha selection, frozen-season model coefficients and earlier-day feature updates are unchanged. Six leagues test 2021–22 through 2025–26; Greece tests 2020–21, 2023–24 and 2024–25. All fold counts, date ranges and chosen alphas are in the corrected JSON. No new candidate, calibration or blend was selected on these results.

The correction can change historical form/Elo/rest, fitted coefficients and future forecasts because training inputs change. It does not alter the modelling algorithms. Old journal records retain their original forecasts. These are repeated, exploratory historical comparisons, not fresh untouched holdouts.

| League | Original 1X2 log loss | Corrected 1X2 log loss | Corrected − original |
|---|---:|---:|---:|
| Premier League | 0.974034 | 0.973964 | -0.000070 |
| Greece | 0.995769 | 0.995769 | +0.000000 |
| La Liga | 0.991590 | 0.991556 | -0.000033 |
| Bundesliga | 0.998780 | 0.998780 | +0.000000 |
| Serie A | 0.996439 | 0.996272 | -0.000168 |
| Ligue 1 | 1.005865 | 1.005865 | +0.000000 |
| Primeira Liga | 0.937510 | 0.937532 | +0.000022 |

Lower is better. The headline changes are tiny. This is a correctness repair, not evidence of a materially stronger architecture.

| League | Original raw score NLL | Corrected raw score NLL | Corrected − original, 95% paired season interval |
|---|---:|---:|---|
| Premier League | 2.975197 | 2.975775 | +0.000579 [+0.000029, +0.001320] |
| Greece | 2.828347 | 2.828347 | +0.000000 [+0.000000, +0.000000] |
| La Liga | 2.814032 | 2.819570 | +0.005538 [+0.000739, +0.014316] |
| Bundesliga | 3.092508 | 3.092508 | +0.000000 [+0.000000, +0.000000] |
| Serie A | 2.825540 | 2.820558 | -0.004982 [-0.009622, -0.002096] |
| Ligue 1 | 2.963242 | 2.963242 | +0.000000 [+0.000000, +0.000000] |
| Primeira Liga | 2.799810 | 2.798031 | -0.001779 [-0.003998, +0.000273] |

## Corrected goal-market results

Binary log loss; lower is better. Base is training-only league climatology; raw and aligned are the same candidates as checkpoint 1.

| League | O2.5 base | O2.5 raw | O2.5 aligned | BTTS base | BTTS raw | BTTS aligned |
|---|---:|---:|---:|---:|---:|---:|
| Premier League | 0.6914 | 0.6844 | 0.6848 | 0.6919 | 0.6902 | 0.6898 |
| Greece | 0.7007 | 0.7128 | 0.7083 | 0.6974 | 0.7022 | 0.7068 |
| La Liga | 0.6922 | 0.6859 | 0.6860 | 0.6928 | 0.6949 | 0.6948 |
| Bundesliga | 0.6691 | 0.6595 | 0.6600 | 0.6729 | 0.6701 | 0.6709 |
| Serie A | 0.6998 | 0.6965 | 0.6943 | 0.6978 | 0.6929 | 0.6944 |
| Ligue 1 | 0.6920 | 0.6854 | 0.6863 | 0.6899 | 0.6892 | 0.6885 |
| Primeira Liga | 0.6959 | 0.6772 | 0.6779 | 0.6942 | 0.6914 | 0.6922 |

The conclusions remain similar: team goals show useful improvement over simple base rates; totals and BTTS need more care, especially in Greece. Result alignment ensures mathematical coherence but is not a universal accuracy improvement. Retain the current production recipe and keep any new goal-market UI explicit about experimental estimates. Do not choose different model variants per market from this test table.

The date warning is now zero. Existing limitations remain: Greek missing seasons/playoffs, only three Greek season blocks, five blocks elsewhere, repeated historical testing, row-based inner training CV and no local historical bookmaker lines for these extra markets. A known Greek 2023–24 repeated venue pair is preserved as a separate upstream anomaly; this date-only repair does not silently relabel it.

## Updating a local synced snapshot

The application prefers ignored `data/local/historical_matches.csv.gz` when it exists. Pulling the corrected Git bundle alone will not replace that local snapshot. Use the reviewed offline migration so newer results are retained. From the repository root:

```bash
git pull origin main
uv run python -m football_predictor.date_repair --apply
uv run uvicorn football_predictor.api:app --host 0.0.0.0 --port 8000
```

Stop the running backend with Ctrl+C first, and do not run a results sync concurrently. The frontend does not need rebuilding for this checkpoint. API keys do not need reconfiguration.

Without `--apply`, the repair is a dry run. Applying backs up both the CSV and manifest under `data/local/date-repair-backups/<original checksum>/`, verifies the old checksum and exact mapped fixture/score/source, and writes a new checksummed snapshot. All newer Goal API results and existing sync provenance are preserved. A second run is a no-op. An absent local snapshot needs no migration; the corrected bundle is used. Conflicting scores/dates/sources, duplicate fixture candidates or a mismatched manifest abort without changing the snapshot. Do not delete local results or use a fresh Goal API sync to perform this correction.

Only the default ignored local snapshot is targeted unless `--input` and its corresponding `--manifest` are explicitly supplied. Checksum-named backups allow manual recovery; original files are never removed as part of this process.

## Validation and evidence

Parser tests cover normal seasons, July/August pandemic endings, leap days, explicit years, out-of-order headers and inconsistent calendar evidence. Migration tests cover dry run, exact corrections, backups, preservation of newer results and source history, idempotence, missing fixtures, conflicting records and checksum protection. The full corrected bundle is checked against all 268 map entries. Backend regression suite: 351 tests passed; Ruff and whitespace checks passed. Frontend changes: none; existing browser CI is also run on publication.

- [Corrected full benchmark, calibration bins, fold details and source fingerprints](reviews/2026-10-18-betting-markets-corrected.json)
- [Source verification, correction counts and paired before/after intervals](reviews/2026-10-18-date-correction-audit.json)
- [Original checkpoint report](betting-markets.md) and [original measured snapshot results](reviews/2026-10-18-betting-markets.json)

Reproduce the corrected benchmark:

```bash
uv run python -m football_predictor.betting_benchmark --output data/local/research/betting-markets-corrected.json --predictions data/local/research/betting-markets-corrected.csv.gz
```

Next: implement the Betting tab with result-derived markets and clearly identified goal-model estimates, then add live market coverage and quota controls. No model replacement is justified by this correction.
