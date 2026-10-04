import { FormEvent, useEffect, useId, useMemo, useState } from "react";
import {
  Competition,
  getFixtures,
  getMarketOdds,
  getNextFixture,
  getScorecardResults,
  getTeams,
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
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function dateAfter(value: string, days: number): string {
  const date = new Date(`${value}T12:00:00`);
  date.setDate(date.getDate() + days);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function fixtureTime(value: string): string {
  return new Date(value).toLocaleString([], {
    weekday: "long", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function perMatch(value: number): string {
  return value.toFixed(2);
}

function outcomeSummary(values: [number, number, number]): string {
  return `Home ${percent(values[0])} · Draw ${percent(values[1])} · Away ${percent(values[2])}`;
}

function TeamPicker({
  label,
  value,
  teams,
  exclude,
  loading,
  onSelect,
}: {
  label: string;
  value: string;
  teams: string[];
  exclude: string;
  loading: boolean;
  onSelect: (team: string) => void;
}) {
  const listboxId = useId();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const filtered = teams
    .filter((team) => team !== exclude && team.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()))
    .slice(0, 8);

  function choose(team: string) {
    onSelect(team);
    setQuery("");
    setOpen(false);
  }

  return (
    <label className="team-picker-label">
      <span>{label}</span>
      <div className="team-picker">
        <input
          role="combobox"
          aria-controls={listboxId}
          aria-autocomplete="list"
          aria-expanded={open}
          aria-label={label}
          autoComplete="off"
          placeholder={loading ? "Loading teams…" : "Search teams"}
          value={query || value}
          onFocus={() => setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 120)}
          onChange={(event) => {
            setQuery(event.target.value);
            onSelect("");
            setActive(0);
            setOpen(true);
          }}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setOpen(true);
              setActive((index) => Math.min(index + 1, Math.max(filtered.length - 1, 0)));
            } else if (event.key === "ArrowUp") {
              event.preventDefault();
              setActive((index) => Math.max(index - 1, 0));
            } else if (event.key === "Enter" && open && filtered[active]) {
              event.preventDefault();
              choose(filtered[active]);
            } else if (event.key === "Escape") {
              setOpen(false);
              setQuery("");
            }
          }}
        />
        {open && (
          <div className="team-picker-options" id={listboxId} role="listbox">
            {filtered.length ? filtered.map((team, index) => (
              <button
                aria-selected={index === active}
                key={team}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => choose(team)}
                role="option"
                type="button"
              >
                {team}
              </button>
            )) : (
              <span className="team-picker-empty">{loading ? "Loading teams…" : "No matching teams"}</span>
            )}
          </div>
        )}
      </div>
    </label>
  );
}

function App() {
  const [competition, setCompetition] = useState<Competition>("premier_league");
  const [homeTeam, setHomeTeam] = useState("");
  const [awayTeam, setAwayTeam] = useState("");
  const [mode, setMode] = useState<"upcoming" | "explore">("upcoming");
  const [teamCatalog, setTeamCatalog] = useState<{ competition: Competition; teams: string[]; error?: string } | null>(null);
  const [nextFixtureResult, setNextFixtureResult] = useState<{ competition: Competition; search: number; fixture: LiveFixture | null; error?: string } | null>(null);
  const [nextFixtureSearch, setNextFixtureSearch] = useState(0);
  const [nextFixtureStart, setNextFixtureStart] = useState(today);
  const [selectedFixture, setSelectedFixture] = useState<LiveFixture | null>(null);
  const [browseDate, setBrowseDate] = useState(today());
  const [dateFixtures, setDateFixtures] = useState<LiveFixture[]>([]);
  const [dateFixturesLoading, setDateFixturesLoading] = useState(false);
  const [dateFixturesNotice, setDateFixturesNotice] = useState<string | null>(null);
  const [oddsHome, setOddsHome] = useState("");
  const [oddsDraw, setOddsDraw] = useState("");
  const [oddsAway, setOddsAway] = useState("");
  const [marketOddsNote, setMarketOddsNote] = useState<string | null>(null);
  const [marketOddsLoading, setMarketOddsLoading] = useState(false);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [trackingNotice, setTrackingNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
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

  useEffect(() => {
    let active = true;
    getTeams(competition)
      .then((teams) => {
        if (!active) return;
        setTeamCatalog({ competition, teams });
        setHomeTeam((current) => teams.includes(current) ? current : teams[0] ?? "");
        setAwayTeam((current) => teams.includes(current) && current !== teams[0] ? current : teams[1] ?? "");
      })
      .catch((caught: unknown) => {
        if (active) setTeamCatalog({ competition, teams: [], error: caught instanceof Error ? caught.message : "Could not load teams." });
      });
    return () => { active = false; };
  }, [competition]);

  const currentTeamCatalog = teamCatalog?.competition === competition ? teamCatalog : null;
  const teamOptions = currentTeamCatalog?.teams ?? [];
  const teamsLoading = currentTeamCatalog === null;
  const teamCatalogError = currentTeamCatalog?.error ?? null;

  useEffect(() => {
    let active = true;
    getNextFixture(competition, nextFixtureStart)
      .then((fixture) => {
        if (!active) return;
        setNextFixtureResult({ competition, search: nextFixtureSearch, fixture });
        if (fixture) setBrowseDate(fixture.kickoff_at.slice(0, 10));
      })
      .catch((caught: unknown) => {
        const raw = caught instanceof Error ? caught.message : "Upcoming fixtures are unavailable.";
        const message = raw.includes("must be configured")
          ? "Live fixture search needs a provider key. You can still explore a matchup."
          : raw;
        if (active) setNextFixtureResult({ competition, search: nextFixtureSearch, fixture: null, error: message });
      });
    return () => { active = false; };
  }, [competition, nextFixtureSearch, nextFixtureStart]);

  const currentFixtureResult = nextFixtureResult?.competition === competition
    && nextFixtureResult.search === nextFixtureSearch ? nextFixtureResult : null;
  const nextFixture = currentFixtureResult?.fixture ?? null;
  const nextFixtureError = currentFixtureResult?.error ?? null;
  const nextFixtureLoading = currentFixtureResult === null;
  const activeUpcomingFixture = selectedFixture?.competition === competition ? selectedFixture : nextFixture;
  const isAlternativeFixture = Boolean(
    activeUpcomingFixture && nextFixture && activeUpcomingFixture.fixture_id !== nextFixture.fixture_id,
  );

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
    if (next === competition) return;
    setCompetition(next);
    setHomeTeam("");
    setAwayTeam("");
    setNextFixtureStart(today());
    setNextFixtureSearch(0);
    setSelectedFixture(null);
    setBrowseDate(today());
    setDateFixtures([]);
    setDateFixturesNotice(null);
    setPrediction(null);
    setError(null);
    setTrackingNotice(null);
    setOddsHome("");
    setOddsDraw("");
    setOddsAway("");
    setMarketOddsNote(null);
  }

  function changeMode(next: "upcoming" | "explore") {
    setMode(next);
    setPrediction(null);
    setError(null);
    setTrackingNotice(null);
    setOddsHome("");
    setOddsDraw("");
    setOddsAway("");
    setMarketOddsNote(null);
  }

  async function loadFixturesForDate() {
    setDateFixturesNotice(null);
    setDateFixturesLoading(true);
    try {
      const fixturesForDate = await getFixtures(competition, browseDate);
      const upcoming = fixturesForDate
        .filter((fixture) => Date.parse(fixture.kickoff_at) > Date.now())
        .sort((first, second) => Date.parse(first.kickoff_at) - Date.parse(second.kickoff_at));
      setDateFixtures(upcoming);
      setDateFixturesNotice(upcoming.length ? null : "No upcoming fixtures were found on this date. Try another date.");
    } catch (caught) {
      setDateFixtures([]);
      setDateFixturesNotice(caught instanceof Error ? caught.message : "Fixtures are unavailable for this date.");
    } finally {
      setDateFixturesLoading(false);
    }
  }

  function chooseScheduledFixture(fixture: LiveFixture) {
    setSelectedFixture(fixture);
    setPrediction(null);
    setError(null);
    setMarketOddsNote(null);
    setOddsHome("");
    setOddsDraw("");
    setOddsAway("");
  }

  async function loadOddsForSelectedFixture() {
    if (!activeUpcomingFixture) return;
    setMarketOddsLoading(true);
    setMarketOddsNote(null);
    setError(null);
    try {
      const quote = await getMarketOdds(activeUpcomingFixture);
      setOddsHome(quote.home_fair_odds.toFixed(2));
      setOddsDraw(quote.draw_fair_odds.toFixed(2));
      setOddsAway(quote.away_fair_odds.toFixed(2));
      setMarketOddsNote(
        `Market consensus from ${quote.bookmaker_count} bookmakers · margin removed · updated ${new Date(quote.fetched_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}.`,
      );
    } catch (caught) {
      setMarketOddsNote(caught instanceof Error ? caught.message : "Live market odds are unavailable.");
    } finally {
      setMarketOddsLoading(false);
    }
  }

  async function generateForecast(event?: FormEvent, fixture?: LiveFixture) {
    event?.preventDefault();
    setError(null);
    setTrackingNotice(null);
    const odds = [oddsHome, oddsDraw, oddsAway];
    const hasAnyOdds = odds.some((value) => value.trim() !== "");
    if (hasAnyOdds && odds.some((value) => value.trim() === "")) {
      setError("Enter all three decimal odds, or leave all three blank.");
      return;
    }
    const selectedHome = fixture?.home_team ?? homeTeam.trim();
    const selectedAway = fixture?.away_team ?? awayTeam.trim();
    if (!selectedHome || !selectedAway) {
      setError("Choose both teams from the search suggestions.");
      return;
    }
    if (selectedHome === selectedAway) {
      setError("Choose two different teams.");
      return;
    }
    const selectedKickoff = fixture?.kickoff_at ?? null;
    const selectedDate = selectedKickoff?.slice(0, 10) ?? today();
    setLoading(true);
    try {
      const nextPrediction = await predictMatch({
        competition,
        kickoff_date: selectedDate,
        ...(selectedKickoff ? { kickoff_at: selectedKickoff } : {}),
        home_team: selectedHome,
        away_team: selectedAway,
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
        setTrackingNotice("Forecast saved and will be scored after this scheduled match.");
      } else {
        setTrackingNotice("Hypothetical matchup · based on the latest available results. It is not tracked in the live scorecard.");
      }
    } catch (caught) {
      setPrediction(null);
      setError(caught instanceof Error ? caught.message : "Prediction failed.");
    } finally {
      setLoading(false);
    }
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

            <div className="forecast-modes" role="group" aria-label="Choose forecast type">
              <button className={mode === "upcoming" ? "active" : ""} onClick={() => changeMode("upcoming")} aria-pressed={mode === "upcoming"} type="button">
                Next match
              </button>
              <button className={mode === "explore" ? "active" : ""} onClick={() => changeMode("explore")} aria-pressed={mode === "explore"} type="button">
                Explore matchup
              </button>
            </div>

            {mode === "upcoming" ? (
              <section className="upcoming-card" aria-live="polite">
                <div className="upcoming-card-heading">
                  <div><span className="section-label">Up next · {LEAGUES[competition].short}</span><h3>{LEAGUES[competition].name}</h3></div>
                  <span className={nextFixtureLoading ? "fixture-status searching" : "fixture-status"}>
                    {nextFixtureLoading ? "Finding match" : activeUpcomingFixture ? "Fixture found" : "No fixture"}
                  </span>
                </div>
                {nextFixtureLoading ? (
                  <div className="upcoming-empty"><span className="search-spinner" /><p>Checking today and upcoming dates…</p></div>
                ) : activeUpcomingFixture ? null : (
                  <div className="upcoming-empty">
                    <p>{nextFixtureError ?? `No upcoming fixture was found from in the next three weeks.`}</p>
                    {nextFixtureError ? (
                      <button className="text-button" onClick={() => setNextFixtureSearch((value) => value + 1)} type="button">Try again</button>
                    ) : (
                      <button className="text-button" onClick={() => { setNextFixtureStart((value) => dateAfter(value, 21)); setNextFixtureSearch((value) => value + 1); }} type="button">Search the following three weeks →</button>
                    )}
                    <button className="text-button" onClick={() => changeMode("explore")} type="button">Explore a matchup instead →</button>
                  </div>
                )}
                  {activeUpcomingFixture && (
                    <>
                      <div className="upcoming-card-heading selected-fixture-heading">
                        <div><span className="section-label">{isAlternativeFixture ? "Selected scheduled match" : "Soonest scheduled match"}</span></div>
                        {isAlternativeFixture && <button className="text-button" onClick={() => { setSelectedFixture(null); setPrediction(null); }} type="button">Use soonest</button>}
                      </div>
                      <p className="fixture-kickoff">{fixtureTime(activeUpcomingFixture.kickoff_at)}</p>
                      <div className="upcoming-teams"><strong>{activeUpcomingFixture.home_team}</strong><span>vs</span><strong>{activeUpcomingFixture.away_team}</strong></div>
                      <button className="primary-button" disabled={loading} onClick={() => void generateForecast(undefined, activeUpcomingFixture)} type="button">
                        {loading ? "Generating forecast…" : "Predict this match"}<span>→</span>
                      </button>
                    </>
                  )}
                  <details className="date-fixture-browser">
                    <summary>Choose another scheduled match <span>Browse by date</span></summary>
                    <p>Pick a match day to see every upcoming fixture listed by the provider.</p>
                    <div className="date-fixture-controls">
                      <label htmlFor="scheduled-fixture-date">Match date</label>
                      <input id="scheduled-fixture-date" type="date" min={today()} value={browseDate} onChange={(event) => { setBrowseDate(event.target.value); setDateFixtures([]); setDateFixturesNotice(null); }} />
                      <button className="secondary-button" disabled={dateFixturesLoading || !browseDate} onClick={() => void loadFixturesForDate()} type="button">
                        {dateFixturesLoading ? "Loading…" : "Load fixtures"}
                      </button>
                    </div>
                    {dateFixturesNotice && <div className="message">{dateFixturesNotice}</div>}
                    {dateFixtures.length > 0 && (
                      <div className="date-fixture-list" aria-label="Upcoming fixtures for selected date">
                        {dateFixtures.map((fixture) => {
                          const selected = activeUpcomingFixture?.fixture_id === fixture.fixture_id;
                          return (
                            <button className={selected ? "date-fixture-option selected" : "date-fixture-option"} key={fixture.fixture_id} aria-pressed={selected} onClick={() => chooseScheduledFixture(fixture)} type="button">
                              <span>{new Date(fixture.kickoff_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                              <strong>{fixture.home_team}<i>vs</i>{fixture.away_team}</strong>
                              <em>{selected ? "Selected" : "Choose"}</em>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </details>
              </section>
            ) : (
              <form className="explore-form" onSubmit={(event) => void generateForecast(event)}>
                <p className="mode-description">Choose any two teams. This hypothetical forecast uses their latest available results.</p>
                <div className="team-fields">
                  <TeamPicker key={`${competition}-home`} label="Home team" value={homeTeam} teams={teamOptions} exclude={awayTeam} loading={teamsLoading} onSelect={(team) => { setHomeTeam(team); setPrediction(null); }} />
                  <span className="versus">VS</span>
                  <TeamPicker key={`${competition}-away`} label="Away team" value={awayTeam} teams={teamOptions} exclude={homeTeam} loading={teamsLoading} onSelect={(team) => { setAwayTeam(team); setPrediction(null); }} />
                </div>
                <button className="primary-button" disabled={loading || teamsLoading || teamOptions.length < 2} type="submit">
                  {loading ? "Generating forecast…" : "Generate hypothetical forecast"}<span>→</span>
                </button>
              </form>
            )}

            <details className="odds-details">
              <summary>Add market odds <span>Optional</span></summary>
              <p>Load odds for the selected scheduled match, or enter three decimal prices yourself. The market stays separate from the model.</p>
              {mode === "upcoming" && activeUpcomingFixture && (
                <button className="secondary-button" disabled={marketOddsLoading} onClick={() => void loadOddsForSelectedFixture()} type="button">
                  {marketOddsLoading ? "Loading market odds…" : "Load live market odds"}
                </button>
              )}
              {marketOddsNote && <div className={marketOddsNote.startsWith("Market consensus") ? "market-odds-note" : "message"}>{marketOddsNote}</div>}
              <div className="market-odds-fields">
                <label><span>Home</span><input type="number" min="1.01" step="0.01" inputMode="decimal" placeholder="2.10" value={oddsHome} onChange={(event) => { setOddsHome(event.target.value); setMarketOddsNote(null); }} /></label>
                <label><span>Draw</span><input type="number" min="1.01" step="0.01" inputMode="decimal" placeholder="3.40" value={oddsDraw} onChange={(event) => { setOddsDraw(event.target.value); setMarketOddsNote(null); }} /></label>
                <label><span>Away</span><input type="number" min="1.01" step="0.01" inputMode="decimal" placeholder="3.60" value={oddsAway} onChange={(event) => { setOddsAway(event.target.value); setMarketOddsNote(null); }} /></label>
              </div>
              <small>With all three prices entered, headline probabilities use the supplied margin-removed odds. Model-only probabilities remain available below.</small>
            </details>

            {(error || (mode === "explore" && teamCatalogError)) && <div className="message error-message">{error ?? teamCatalogError}</div>}

            {prediction && (
              <div className="result-panel" aria-live="polite">
                <div className="result-title">
                  <span>Forecast result · {prediction.kickoff_at ? "Scheduled fixture" : "Hypothetical matchup"}</span>
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
                    {prediction.competition === "premier_league"
                      ? `Premier League probabilities combine Elo with a Poisson goal model. Both use pre-match history; the goal model also uses recent form, scoring/conceding rates, venue form, and rest. This summary does not assign an exact probability change to each factor.`
                      : "Greek league probabilities currently use team Elo ratings and home advantage. The form, goal, and venue figures below are context only; they do not directly change these probabilities."}
                    {` Snapshot through ${prediction.history_through}.`}
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
                <div className="component-panel">
                  <h3>How the model builds its probabilities</h3>
                  {prediction.components.goal_probabilities ? (
                    <>
                      <p>The Premier League model combines these two probability sets using the displayed weights.</p>
                      <div className="context-grid">
                        <span>Elo component ({percent(prediction.components.elo_weight)})</span>
                        <strong>{outcomeSummary(prediction.components.elo_probabilities)}</strong>
                        <span>Goal model ({percent(1 - prediction.components.elo_weight)})</span>
                        <strong>{outcomeSummary(prediction.components.goal_probabilities)}</strong>
                        <span>Expected goals · home / away</span>
                        <strong>{prediction.components.home_goal_rate?.toFixed(2)} / {prediction.components.away_goal_rate?.toFixed(2)}</strong>
                        <span>Combined model probabilities</span>
                        <strong>{outcomeSummary(prediction.components.core_model_probabilities)}</strong>
                      </div>
                    </>
                  ) : (
                    <>
                      <p>The Greek model uses the Elo probability set directly, including home advantage.</p>
                      <div className="context-grid">
                        <span>Elo model probabilities</span>
                        <strong>{outcomeSummary(prediction.components.elo_probabilities)}</strong>
                      </div>
                    </>
                  )}
                  {prediction.components.league_prior_probabilities && (
                    <p className="component-prior">
                      Promoted-team adjustment: {percent(prediction.components.base_model_weight)} core model ({outcomeSummary(prediction.components.core_model_probabilities)}) + {percent(1 - prediction.components.base_model_weight)} league prior ({outcomeSummary(prediction.components.league_prior_probabilities)}) = model probabilities ({outcomeSummary([prediction.model_home_win_probability, prediction.model_draw_probability, prediction.model_away_probability])}).
                    </p>
                  )}
                </div>
                {trackingNotice && <p className="scorecard-note">{trackingNotice}</p>}
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
            <div className="scorecard-empty">Predict a scheduled upcoming match to start tracking.</div>
          )}
          <p className="scorecard-footnote">A small live sample is noisy; wait for more settled matches before drawing conclusions. Calibration gap is a five-bin, three-outcome expected calibration error (lower is better). History updates are checked weekly.</p>
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
        <div className="metric-row" title="Five-bin classwise expected calibration error; lower is better."><span>Calibration gap (ECE)</span><strong>{metrics.calibrationError.toFixed(3)}</strong></div>
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
