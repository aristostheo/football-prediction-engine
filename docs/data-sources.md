# Data sources and ingestion policy

## Initial historical-results source

The first adapter supports **OpenFootball Europe**, a public CC0 repository.
It contains Greek Super League results and uses a concise, text-based fixture
format. Raw data remains outside this repository; each generated canonical row
retains the exact file URL and retrieval timestamp.

The adapter is intentionally source-neutral at its output boundary. It converts
an external file into `HistoricalMatch` records, then the canonical dataset
builder applies cross-source validation.

## Premier League coverage decision

OpenFootball's Europe repository does not own the England data. Before the
first production ingest, we will select a separately licensed Premier League
results source and implement its own adapter. We will not silently reuse a
source whose stated terms prohibit the project's intended use.

## Competition-stage policy for V1

The V1 dataset includes regular-season fixtures only. Super League Greece
championship, European-playoff, and relegation stages are parsed but excluded.
Those stages change the fixture population and should be added only with an
explicit modelling policy, rather than being mixed into league form by default.
