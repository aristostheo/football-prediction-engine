# Browser regression checks

The committed Playwright suite exercises the built Touchline interface with an
isolated production-preview server on `127.0.0.1:4174`. It never reuses a running
local app or starts the prediction backend. Every API response is mocked, and
external requests are blocked. The tests do not spend Goal API or Odds API quota.

## Run locally

From `web`:

```bash
npm ci
npx playwright install --no-shell chromium webkit
npm run test:e2e:typecheck
npm run test:e2e
```

On Linux, install browser system dependencies first with
`npx playwright install-deps chromium webkit` where your environment permits it.
These browser downloads are only needed for browser tests, not for normal app use.

Individual projects can be selected:

```bash
npm run test:e2e -- --project=webkit-mobile
npx playwright show-report
```

## Coverage and isolation

Ten flow tests (40 browser cases) run against desktop Chromium, desktop WebKit, emulated Pixel
7 Chromium and emulated iPhone 13 WebKit. Narrow-layout checks include 320, 390
and 768 CSS pixels; desktop checks include 1280 and 1440 pixels. The suite covers:

- Crowded matchdays, long club names, all seven leagues and manual date browsing.
- Forecast generation, two-decimal odds display with original calculation
  precision, live/manual comparison provenance and saved probabilities.
- Explicit retries after fixture, prediction and odds failures; empty searches
  and finished/postponed fixtures.
- Late league/date/odds/forecast responses after the user changes selection.
- Actual results disagreeing with the saved model pick; preservation through
  provider failure, pending replies and reload; CSV export and explicit deletion.
- Registered-team validation and hypothetical forecasts remaining outside the
  journal; favourites, filters, theme persistence and navigation.
- Page containment while fixture ribbons and journal tables scroll internally;
  matchup dialog bounds and rendered market/journal screenshots.

The fixture clock and provider payloads are deterministic. Unexpected fetch/XHR
requests and uncaught browser exceptions fail the suite. Tests deliberately fail
provider badge requests, checking that names and packaged/initial fallbacks keep
the interface usable. The prediction payload is a controlled test value: these
checks do not measure prediction accuracy or replace backend model tests.

## CI and evidence

Application checks run on pushes and pull requests to main. The frontend job
installs browsers, runs the suite without retries, and uploads the HTML report,
layout screenshots and failure traces as **browser-test-report**, retained for
seven days. A new run replaces no saved user data. Each test has a fresh browser
context and storage; the preview server cannot access your live API session.

Mobile emulation and Linux WebKit are useful regressions, not proof of behavior
on a physical iPhone or the exact Safari version on your Mac. Keep occasional
real-device checks for touch/keyboard behavior and browser-specific file downloads.
Authenticated provider availability, actual response latency and account quota
remaining still require a separate, bounded live check using your local keys.
