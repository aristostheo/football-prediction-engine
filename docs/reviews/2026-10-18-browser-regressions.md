# Browser flow and mobile regression checkpoint

Starting main: `a7ce1ba958e2383e30900cb841338d99850978a4`.
Validated application/test revision: `a71d341d16cf12b36d5f084336de8651edd86d61`.
[Successful CI run](https://github.com/aristostheo/football-prediction-engine/actions/runs/39154539332).

## Results

| Check | Result |
| --- | --- |
| Browser flows | 40 passed, no retries, approximately one minute of test execution |
| Desktop Chromium | 10 passed |
| Desktop WebKit | 10 passed |
| Emulated Pixel 7 Chromium | 10 passed |
| Emulated iPhone 13 WebKit | 10 passed |
| Python suite and lint | 291 tests passed; `ruff check src tests` passed |
| Frontend helper tests | 15 passed |
| TypeScript, ESLint and production build | Passed, including separate browser-test type checking |

The suite tests the production build through an isolated preview server and
fully controlled API responses. It covers all seven league switches, selected
dates, crowded matchdays, prediction/odds failures and retries, stale responses,
live/manual odds precision and provenance, prospective journal preservation,
settlement/export/deletion, empty/postponed/finished fixtures, hypothetical team
validation, favourites and theme persistence. Provider image failures deliberately
exercise local/initial fallbacks.

Geometry checks cover page containment, dialog bounds and the actual text range
inside team columns at 320, 390, 768, 1280 and 1440 CSS pixels. Fixture ribbons
and journal panels retain their own scrolling. Market and journal screenshots
were captured in all four projects; final mobile and desktop images were also
visually inspected.

## Application fixes

1. **Long mobile club names could be clipped inside the match card.** Page-wide
   overflow checks alone did not detect this because the card clipped its child.
   Names now stay within their team columns, with responsive mobile sizing,
   wrapping/hyphenation and a smaller gap. Tests measure text bounds as well as
   document width. The full club identity is retained.
2. **A stale discovery response could spend unnecessary fixture lookups.** The
   earlier code checked the active league/date only after fetching its fixture
   dates. It now checks immediately when discovery resolves, before those extra
   reads. A late league-response regression verifies that no additional date
   request is made for the discarded result. This is not a global quota meter.

Initial browser runs also exposed test-selector assumptions about changing button
labels, favourite counts in accessible names and navigation immediately after
reload. Those were corrected in the test harness rather than changing working
application behavior to satisfy the tests.

## Reproducibility and limits

See [browser test setup](../browser-tests.md). Playwright is pinned to 1.64.1;
the verified runner used Chrome for Testing 156.0.8078.4 and WebKit 27.2 on Linux.
The report and screenshots are available as **browser-test-report** on the CI run
for seven days. Tests have isolated storage, a fixed clock and no retries.

This workspace cannot launch browsers because required socket operations are
blocked. Browser execution and screenshots therefore came from GitHub Actions;
local TypeScript, helper tests, lint and build checks also passed. No security
restriction was removed to run them locally.

No Goal API or Odds API credentials are used, external requests are blocked and
these tests consumed no provider quota. Mock predictions establish interface and
persistence behavior, not model accuracy or authenticated provider availability.
Mobile emulation/Linux WebKit do not replace physical iPhone/Mac Safari checks.
Classic/mockup screens are outside this Touchline suite.

Production model algorithms, data, weights and market/model separation are
unchanged. Greek coverage, rescheduled-fixture identity, broader quota accounting
and research-methodology findings from the original review remain separate work.

## Local update

```bash
git pull origin main
cd web
npm ci
npm run build
cd ..
```

Refresh the browser. The backend can remain running because this checkpoint only
changes frontend behavior and test infrastructure. Another results-sync run is
not required to apply this update.
