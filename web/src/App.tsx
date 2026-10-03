import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Competition,
  getFixtures,
  getScorecardResults,
  LiveFixture,
  MatchOutcome,
  predictMatch,
  Prediction,
} from "./api";
import { calculateMetrics, loadForecasts, saveForecast, StoredForecast } from "./scorecard";

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

function perMatch(value: number): string {
  return value.toFixed(2);
}

function App() {
  const [competition, setCompetition] = useState<Competition>("premier_league");
  const [fixtureDate, setFixtureDate] = useState(today());
  const [kickoffAt, setKickoffAt] = useState<string | null>(null);
  const [homeTeam, setHomeTeam] = useState("Arsenal FC");
  const [awayTeam, setAwayTeam] = useState("Chelsea FC");
  const [oddsHome, setOddsHome] = useState("");
  const [oddsDraw, setOddsDraw] = useState("");
  const [oddsAway, setOddsAway] = useState("");
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [trackingNotice, setTrackingNotice] = useState<string | null>(null);
  const [fixtures, setFixtures] = useState<LiveFixture[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [fixtureNotice, setFixtureNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [fixturesLoading, setFixturesLoading] = useState(false);
  const [forecastLog, setForecastLog] = useState<StoredForecast[]>(loadForecasts);
  const [settledResults, setSettledResults] = useState<Record<string, MatchOutcome | null>>({});
  const [scorecardLoading, setScorecardLoading] = useState(false);
  const [scorecardError, setScorecardError] = useState<string | null>(null);

  useEffect(() => {
    if (!forecastLog.length) return;
    let active = true;
    getScorecardResults(forecastLog)
      .then((results) => { if (active) setSettledResults(results); })
      .catch((caught: unknown) => {
        if (active) setScorecardError(caught instanceof Error ? caught.message : "Could not load results.");
      })
    return () => { active = false; };
  }, [forecastLog]);

  const scorecardByCompetition = useMemo(
    () => (Object.keys(LEAGUES) as Competition[]).map((key) => {
      const leagueForecasts = forecastLog.filter((item) => item.competition === key);
      const marketForecasts = leagueForecasts.filter((item) => item.market_probabilities !== null);
      const allModel = calculateMetrics(
        leagueForecasts, settledResults, (item) => item.model_probabilities,
      );
      const pairedModel = calculateMetrics(
        marketForecasts, settledResults, (item) => item.model_probabilities,
      );
      const market = calculateMetrics(
        marketForecasts, settledResults, (item) => item.market_probabilities,
      );
      return {
        competition: key,
        allModel,
        pairedModel,
        market,
        pairedLogLossDifference: pairedModel && market
          ? pairedModel.logLoss - market.logLoss
          : null,
      };
    }),
    [forecastLog, settledResults],
  );

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
    setKickoffAt(null);
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
    setTrackingNotice(null);
    const odds = [oddsHome, oddsDraw, oddsAway];
    const hasAnyOdds = odds.some((value) => value.trim() !== "");
    if (hasAnyOdds && odds.some((value) => value.trim() === "")) {
      setError("Enter all three decimal odds, or leave all three blank.");
      return;
    }
    setLoading(true);
    try {
      const nextPrediction = await predictMatch({
        competition,
        kickoff_date: fixtureDate,
        ...(kickoffAt ? { kickoff_at: kickoffAt } : {}),
        home_team: homeTeam.trim(),
        away_team: awayTeam.trim(),
        ...(hasAnyOdds
          ? {
              odds_home: Number(oddsHome),
              odds_draw: Number(oddsDraw),
              odds_away: Number(oddsAway),
            }
          : {}),
      });
      setPrediction(nextPrediction);
      if (nextPrediction.kickoff_at && Date.parse(nextPrediction.kickoff_at) > Date.now()) {
        setForecastLog(saveForecast(nextPrediction));
        setTrackingNotice("Timestamped forecast saved in this browser.");
      } else if (nextPrediction.kickoff_at) {
        setTrackingNotice("Kickoff passed before the forecast reached this browser, so it was not tracked.");
      } else {
        setTrackingNotice("Select a fixture from the live list to include it in the prospective scorecard.");
      }
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
    setKickoffAt(fixture.kickoff_at);
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
          <a href="#scorecard">Live scorecard</a>
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
                <input type="date" value={fixtureDate} onChange={(event) => { setFixtureDate(event.target.value); setKickoffAt(null); }} required />
              </label>
              <div className="team-fields">
                <label>
                  <span>Home team</span>
                  <input value={homeTeam} onChange={(event) => { setHomeTeam(event.target.value); setKickoffAt(null); }} required />
                </label>
                <span className="versus">VS</span>
                <label>
                  <span>Away team</span>
                  <input value={awayTeam} onChange={(event) => { setAwayTeam(event.target.value); setKickoffAt(null); }} required />
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
                {prediction.model_policy === "market_implied_odds" && (
                  <p className="model-market-note">
                    Model-only probabilities: {percent(prediction.model_home_win_probability)} home · {percent(prediction.model_draw_probability)} draw · {percent(prediction.model_away_probability)} away.
                    The headline probabilities above come from the odds.
                  </p>
                )}
                <div className="context-panel">
                  <h3>What informs the model</h3>
                  <p>
                    Pre-match snapshot through {prediction.history_through}. The {prediction.competition === "premier_league" ? "Premier League model combines Elo with recent-form and goal-rate features" : "Greek league model uses Elo ratings, which summarize past results"}. Home advantage is included in the rating comparison. Other figures give context; they are not individual causal explanations.
                  </p>
                  <div className="context-grid">
                    <span>Team strength (Elo)</span>
                    <strong>{prediction.home_team} {prediction.context.home_elo.toFixed(0)} · {prediction.context.away_elo.toFixed(0)} {prediction.away_team}</strong>
                    <span>Recent form · points per match</span>
                    <strong>{perMatch(prediction.context.home_form_points_per_match)} ({prediction.context.home_form_matches} matches) · {perMatch(prediction.context.away_form_points_per_match)} ({prediction.context.away_form_matches} matches)</strong>
                    <span>Recent goals · scored / conceded per match</span>
                    <strong>{perMatch(prediction.context.home_form_goals_for_per_match)} / {perMatch(prediction.context.home_form_goals_against_per_match)} · {perMatch(prediction.context.away_form_goals_for_per_match)} / {perMatch(prediction.context.away_form_goals_against_per_match)}</strong>
                    <span>Venue form · points per match</span>
                    <strong>Home at home {perMatch(prediction.context.home_venue_points_per_match)} · away away {perMatch(prediction.context.away_venue_points_per_match)}</strong>
                  </div>
                  <small>The current version does not use injuries, lineups, weather, or live odds as model inputs.</small>
                </div>
                {trackingNotice && <p className="scorecard-note">{trackingNotice}</p>}
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

        <section className="scorecard-section" id="scorecard">
          <div className="section-intro">
            <span className="section-label">2026–27 prospective test</span>
            <h2>Track forecasts against results.</h2>
            <p>Timestamped forecasts stay in this browser. Results are matched after they enter the bundled history.</p>
          </div>
          <div className="scorecard-toolbar">
            <span>{forecastLog.length} tracked · {forecastLog.filter((item) => settledResults[item.id]).length} settled</span>
            <button className="secondary-button" type="button" disabled={scorecardLoading || !forecastLog.length} onClick={() => {
              setScorecardError(null);
              setScorecardLoading(true);
              getScorecardResults(forecastLog)
                .then(setSettledResults)
                .catch((caught: unknown) => setScorecardError(caught instanceof Error ? caught.message : "Could not load results."))
                .finally(() => setScorecardLoading(false));
            }}>{scorecardLoading ? "Checking results…" : "Update results"}</button>
          </div>
          {scorecardError && <div className="message error-message">{scorecardError}</div>}
          {scorecardByCompetition.map((group) => (
            <div className="scorecard-league" key={group.competition}>
              <h3>{LEAGUES[group.competition].name}</h3>
              <div className="scorecard-grid">
                <ScorecardCard title="Model · all tracked fixtures" metrics={group.allModel} />
                <ScorecardCard title="Model · odds-covered fixtures" metrics={group.pairedModel} />
                <ScorecardCard title="Market · odds-covered fixtures" metrics={group.market} />
              </div>
              {group.pairedLogLossDifference !== null && (
                <p className="scorecard-comparison">
                  Paired log-loss difference (model − market): {group.pairedLogLossDifference >= 0 ? "+" : ""}{group.pairedLogLossDifference.toFixed(3)}
                  {group.pairedLogLossDifference < 0 ? " · lower favors the model" : " · lower favors the market"}
                </p>
              )}
            </div>
          ))}
          {forecastLog.length > 0 ? (
            <div className="scorecard-table-wrap">
              <table className="scorecard-table">
                <thead><tr><th>Fixture</th><th>Kickoff</th><th>Saved</th><th>Source</th><th>Actual</th></tr></thead>
                <tbody>
                  {[...forecastLog].sort((a, b) => b.forecasted_at.localeCompare(a.forecasted_at)).slice(0, 12).map((item) => (
                    <tr key={item.id}>
                      <td>{item.home_team} vs {item.away_team}</td>
                      <td>{new Date(item.kickoff_at).toLocaleString()}</td>
                      <td>{new Date(item.forecasted_at).toLocaleString()}</td>
                      <td>{item.market_probabilities ? "Market + model" : "Model"}</td>
                      <td>{resultLabel(settledResults[item.id], scorecardLoading)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <small>Showing up to 12 recent forecasts. Re-forecasts replace the saved version for that fixture; the scorecard uses the latest timestamped forecast before kickoff.</small>
            </div>
          ) : (
            <div className="scorecard-empty">Select a future fixture from the live-fixtures list, then generate a forecast to start tracking.</div>
          )}
          <p className="scorecard-footnote">A small live sample is noisy; wait for more settled matches before drawing conclusions. History updates are checked weekly.</p>
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

function ScorecardCard({ title, metrics }: { title: string; metrics: ReturnType<typeof calculateMetrics> }) {
  return (
    <article className="scorecard-card">
      <div className="scorecard-card-heading"><strong>{title}</strong><span>{metrics ? `${metrics.count} matches` : "No settled matches"}</span></div>
      {metrics ? <>
        <div className="metric-row"><span>Log loss</span><strong>{metrics.logLoss.toFixed(3)}</strong></div>
        <div className="metric-row"><span>Brier score</span><strong>{metrics.brier.toFixed(3)}</strong></div>
        <div className="metric-row"><span>Ranked probability score</span><strong>{metrics.rankedProbabilityScore.toFixed(3)}</strong></div>
        <div className="metric-row"><span>Accuracy</span><strong>{percent(metrics.accuracy)}</strong></div>
      </> : <p>Scores appear after tracked fixtures have completed and results are refreshed.</p>}
    </article>
  );
}

function outcomeLabel(outcome: MatchOutcome): string {
  return outcome === "H" ? "Home win" : outcome === "D" ? "Draw" : "Away win";
}

function resultLabel(result: MatchOutcome | null | undefined, loading: boolean): string {
  return result ? outcomeLabel(result) : loading ? "Checking…" : "Pending";
}

export default App;
