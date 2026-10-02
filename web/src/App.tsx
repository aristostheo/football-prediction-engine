import { FormEvent, useMemo, useState } from "react";
import {
  Competition,
  getFixtures,
  LiveFixture,
  predictMatch,
  Prediction,
} from "./api";

const LEAGUES: Record<Competition, { name: string; short: string; code: string }> = {
  premier_league: { name: "Premier League", short: "England", code: "PL" },
  super_league_greece: { name: "Super League Greece", short: "Greece", code: "SL" },
};

const METRICS = {
  premier_league: { logLoss: "0.9879", brier: "0.5888", accuracy: "53.63%", model: "Elo + Poisson" },
  super_league_greece: { logLoss: "0.9857", brier: "0.5860", accuracy: "51.03%", model: "Elo" },
};

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function App() {
  const [competition, setCompetition] = useState<Competition>("premier_league");
  const [fixtureDate, setFixtureDate] = useState(today());
  const [homeTeam, setHomeTeam] = useState("Arsenal FC");
  const [awayTeam, setAwayTeam] = useState("Chelsea FC");
  const [oddsHome, setOddsHome] = useState("");
  const [oddsDraw, setOddsDraw] = useState("");
  const [oddsAway, setOddsAway] = useState("");
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [fixtures, setFixtures] = useState<LiveFixture[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [fixtureNotice, setFixtureNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [fixturesLoading, setFixturesLoading] = useState(false);

  const probabilities = useMemo(
    () => prediction
      ? [
          { label: prediction.home_team, short: "Home", value: prediction.home_win_probability },
          { label: "Draw", short: "Draw", value: prediction.draw_probability },
          { label: prediction.away_team, short: "Away", value: prediction.away_win_probability },
        ]
      : [],
    [prediction],
  );

  function changeLeague(next: Competition) {
    setCompetition(next);
    setPrediction(null);
    setOddsHome("");
    setOddsDraw("");
    setOddsAway("");
    setFixtures([]);
    setError(null);
    setFixtureNotice(null);
    if (next === "premier_league") {
      setHomeTeam("Arsenal FC");
      setAwayTeam("Chelsea FC");
    } else {
      setHomeTeam("Olympiakos Piraeus");
      setAwayTeam("PAOK Saloniki");
    }
  }

  async function submitPrediction(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const odds = [oddsHome, oddsDraw, oddsAway];
    const hasAnyOdds = odds.some((value) => value.trim() !== "");
    if (hasAnyOdds && odds.some((value) => value.trim() === "")) {
      setError("Enter all three decimal odds, or leave all three blank.");
      return;
    }
    setLoading(true);
    try {
      setPrediction(await predictMatch({
        competition,
        kickoff_date: fixtureDate,
        home_team: homeTeam.trim(),
        away_team: awayTeam.trim(),
        ...(hasAnyOdds
          ? {
              odds_home: Number(oddsHome),
              odds_draw: Number(oddsDraw),
              odds_away: Number(oddsAway),
            }
          : {}),
      }));
    } catch (caught) {
      setPrediction(null);
      setError(caught instanceof Error ? caught.message : "Prediction failed.");
    } finally {
      setLoading(false);
    }
  }

  async function loadFixtures() {
    setFixtureNotice(null);
    setFixturesLoading(true);
    try {
      const nextFixtures = await getFixtures(competition, fixtureDate);
      setFixtures(nextFixtures);
      setFixtureNotice(nextFixtures.length ? null : "No scheduled fixtures were returned for this date.");
    } catch (caught) {
      setFixtures([]);
      setFixtureNotice(caught instanceof Error ? caught.message : "Live fixtures are unavailable.");
    } finally {
      setFixturesLoading(false);
    }
  }

  function chooseFixture(fixture: LiveFixture) {
    setHomeTeam(fixture.home_team);
    setAwayTeam(fixture.away_team);
    setFixtureDate(fixture.kickoff_at.slice(0, 10));
    setPrediction(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Match Forecast home">
          <span className="brand-mark">MF</span>
          <span>Match Forecast</span>
        </a>
        <nav aria-label="Main navigation">
          <a href="#predict">Predict</a>
          <a href="#fixtures">Fixtures</a>
          <a href="#performance">Performance</a>
          <a className="github-link" href="https://github.com/aristostheo/football-prediction-engine">GitHub ↗</a>
        </nav>
      </header>

      <main id="top">
        <section className="hero" id="predict">
          <div className="hero-copy">
            <div className="eyebrow"><span /> Probabilistic match intelligence</div>
            <h1>See the match<br />before it unfolds.</h1>
            <p>
              Leakage-safe home, draw, and away probabilities for two European leagues,
              evaluated on future matches—not shuffled history.
            </p>
            <div className="hero-proof">
              <div><strong>10,468</strong><span>historical matches</span></div>
              <div><strong>25 seasons</strong><span>Premier League depth</span></div>
              <div><strong>0</strong><span>future-data leakage</span></div>
            </div>
          </div>

          <div className="prediction-card">
            <div className="card-heading">
              <div>
                <span className="section-label">New forecast</span>
                <h2>Match predictor</h2>
              </div>
              <span className="live-status"><i /> Model ready</span>
            </div>

            <div className="league-tabs" role="group" aria-label="Competition">
              {(Object.keys(LEAGUES) as Competition[]).map((key) => (
                <button
                  className={competition === key ? "active" : ""}
                  key={key}
                  onClick={() => changeLeague(key)}
                  type="button"
                >
                  <span>{LEAGUES[key].code}</span>
                  <div><strong>{LEAGUES[key].name}</strong><small>{LEAGUES[key].short}</small></div>
                </button>
              ))}
            </div>

            <form onSubmit={submitPrediction}>
              <label className="date-field">
                Match date
                <input type="date" value={fixtureDate} onChange={(event) => setFixtureDate(event.target.value)} required />
              </label>
              <div className="team-fields">
                <label>
                  <span>Home team</span>
                  <input value={homeTeam} onChange={(event) => setHomeTeam(event.target.value)} required />
                </label>
                <span className="versus">VS</span>
                <label>
                  <span>Away team</span>
                  <input value={awayTeam} onChange={(event) => setAwayTeam(event.target.value)} required />
                </label>
              </div>
              <fieldset className="market-odds-entry">
                <legend>Market odds <span>Optional</span></legend>
                <p>Enter all three decimal prices to use margin-removed market probabilities.</p>
                <div className="market-odds-fields">
                  <label>
                    <span>Home</span>
                    <input type="number" min="1.01" step="0.01" inputMode="decimal" placeholder="2.10" value={oddsHome} onChange={(event) => setOddsHome(event.target.value)} />
                  </label>
                  <label>
                    <span>Draw</span>
                    <input type="number" min="1.01" step="0.01" inputMode="decimal" placeholder="3.40" value={oddsDraw} onChange={(event) => setOddsDraw(event.target.value)} />
                  </label>
                  <label>
                    <span>Away</span>
                    <input type="number" min="1.01" step="0.01" inputMode="decimal" placeholder="3.60" value={oddsAway} onChange={(event) => setOddsAway(event.target.value)} />
                  </label>
                </div>
              </fieldset>
              <button className="primary-button" disabled={loading} type="submit">
                {loading ? "Training model…" : "Generate forecast"}<span>→</span>
              </button>
              <p className="training-note">Without odds, the forecast uses the model. With all three prices, it uses market-implied probabilities.</p>
            </form>

            {error && <div className="message error-message">{error}</div>}

            {prediction && (
              <div className="result-panel" aria-live="polite">
                <div className="result-title">
                  <span>Forecast result</span>
                  <strong>{LEAGUES[prediction.competition].name}</strong>
                </div>
                <div className="probabilities">
                  {probabilities.map((item, index) => (
                    <div className={`probability probability-${index}`} key={item.short}>
                      <div><span>{item.short}</span><strong>{percent(item.value)}</strong></div>
                      <div className="probability-track"><i style={{ width: percent(item.value) }} /></div>
                      <small>{item.label}</small>
                    </div>
                  ))}
                </div>
                <div className="freshness">
                  <span>{prediction.model_policy === "market_implied_odds"
                    ? "Forecast source: Market odds · margin removed"
                    : `Forecast source: Model · ${prediction.model_policy.replaceAll("_", " ")}`}</span>
                  <span>History through {prediction.history_through} · {prediction.history_age_days} days old</span>
                </div>
              </div>
            )}
          </div>
        </section>

        <section className="fixtures-section" id="fixtures">
          <div className="section-intro">
            <span className="section-label">Fixture discovery</span>
            <h2>Choose what plays next.</h2>
            <p>Pull the selected date from the optional live provider, then send a fixture into the predictor.</p>
          </div>
          <div className="fixture-browser">
            <div className="fixture-browser-head">
              <div><strong>{LEAGUES[competition].name}</strong><span>{fixtureDate}</span></div>
              <button className="secondary-button" onClick={loadFixtures} disabled={fixturesLoading} type="button">
                {fixturesLoading ? "Loading…" : "Load live fixtures"}
              </button>
            </div>
            {fixtureNotice && <div className="message">{fixtureNotice}</div>}
            {fixtures.length > 0 ? (
              <div className="fixture-list">
                {fixtures.map((fixture) => (
                  <button onClick={() => chooseFixture(fixture)} key={fixture.fixture_id} type="button">
                    <span>{new Date(fixture.kickoff_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                    <strong>{fixture.home_team}<i>vs</i>{fixture.away_team}</strong>
                    <em>Predict →</em>
                  </button>
                ))}
              </div>
            ) : !fixtureNotice && (
              <div className="fixture-empty">
                <span>⌁</span>
                <strong>Live fixtures are optional</strong>
                <p>Manual forecasts above work from the local model. Add a Goal API key to enable this feed.</p>
              </div>
            )}
          </div>
        </section>

        <section className="performance-section" id="performance">
          <div className="section-intro light">
            <span className="section-label">Held-out evaluation</span>
            <h2>Measured on the future.</h2>
            <p>Every score comes from the final chronological 20% of its league—not a random split.</p>
          </div>
          <div className="performance-grid">
            {(Object.keys(LEAGUES) as Competition[]).map((key) => (
              <article className={competition === key ? "selected" : ""} key={key}>
                <div className="metric-heading"><span>{LEAGUES[key].code}</span><div><strong>{LEAGUES[key].name}</strong><small>{METRICS[key].model}</small></div></div>
                <div className="metric-row"><span>Log loss</span><strong>{METRICS[key].logLoss}</strong></div>
                <div className="metric-row"><span>Brier score</span><strong>{METRICS[key].brier}</strong></div>
                <div className="metric-row"><span>Accuracy</span><strong>{METRICS[key].accuracy}</strong></div>
              </article>
            ))}
            <article className="method-card">
              <span className="method-icon">↗</span>
              <div><strong>Leakage-safe by design</strong><p>Rolling form, goal rates, rest, and Elo are calculated only from matches available before kickoff.</p></div>
              <a href="https://github.com/aristostheo/football-prediction-engine/blob/main/docs/model-comparison.md">Read methodology →</a>
            </article>
          </div>
        </section>
      </main>

      <footer>
        <a className="brand" href="#top"><span className="brand-mark">MF</span><span>Match Forecast</span></a>
        <p>Built by Aristotelis Theocharoulas · Probabilities, not promises.</p>
        <a href="https://github.com/aristostheo/football-prediction-engine">View source ↗</a>
      </footer>
    </div>
  );
}

export default App;
