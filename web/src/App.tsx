import { FormEvent, useEffect, useId, useMemo, useState } from "react";
import {
  Competition,
  getFixtures,
  getMarketOdds,
  getNextFixture,
  getScorecardResults,
  getTeamBadges,
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

function TeamBadge({ name, src, size = "normal" }: { name: string; src?: string | null; size?: "normal" | "small" }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
  return (
    <span className={`team-badge team-badge-${size}`} aria-hidden="true">
      {src && !failed ? <img src={src} alt="" loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(true)} /> : initials}
    </span>
  );
}

function TeamPicker({
  label,
  value,
  teams,
  exclude,
  badges,
  loading,
  onSelect,
}: {
  label: string;
  value: string;
  teams: string[];
  exclude: string;
  badges: Record<string, string>;
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
                <TeamBadge name={team} src={badges[team.toLocaleLowerCase()]} size="small" />
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
  const [teamBadgeCatalog, setTeamBadgeCatalog] = useState<{ competition: Competition; badges: Record<string, string> } | null>(null);
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

  useEffect(() => {
    let active = true;
    getTeamBadges(competition)
      .then((badges) => { if (active) setTeamBadgeCatalog({ competition, badges }); })
      .catch(() => { if (active) setTeamBadgeCatalog({ competition, badges: {} }); });
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
  const teamBadges = useMemo(() => {
    const result: Record<string, string> = {};
    if (teamBadgeCatalog?.competition === competition) {
      for (const [team, badge] of Object.entries(teamBadgeCatalog.badges)) {
        result[team.toLocaleLowerCase()] = badge;
      }
    }
    for (const fixture of [nextFixture, selectedFixture, ...dateFixtures]) {
      if (!fixture || fixture.competition !== competition) continue;
      if (fixture.home_badge_url) result[fixture.home_team.toLocaleLowerCase()] = fixture.home_badge_url;
      if (fixture.away_badge_url) result[fixture.away_team.toLocaleLowerCase()] = fixture.away_badge_url;
    }
    return result;
  }, [competition, dateFixtures, nextFixture, selectedFixture, teamBadgeCatalog]);
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
          { label: prediction.home_team, short: "Home", badge: teamBadges[prediction.home_team.toLocaleLowerCase()], value: prediction.model_home_win_probability },
          { label: "Draw", short: "Draw", value: prediction.model_draw_probability },
          { label: prediction.away_team, short: "Away", badge: teamBadges[prediction.away_team.toLocaleLowerCase()], value: prediction.model_away_win_probability },
        ]
      : [],
    [prediction, teamBadges],
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
                      <div className="upcoming-teams"><div className="fixture-team"><TeamBadge name={activeUpcomingFixture.home_team} src={activeUpcomingFixture.home_badge_url} /><strong>{activeUpcomingFixture.home_team}</strong></div><span>vs</span><div className="fixture-team away"><TeamBadge name={activeUpcomingFixture.away_team} src={activeUpcomingFixture.away_badge_url} /><strong>{activeUpcomingFixture.away_team}</strong></div></div>
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
                              <strong className="date-fixture-teams"><span><TeamBadge name={fixture.home_team} src={fixture.home_badge_url} size="small" />{fixture.home_team}</span><i>vs</i><span><TeamBadge name={fixture.away_team} src={fixture.away_badge_url} size="small" />{fixture.away_team}</span></strong>
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
                  <TeamPicker key={`${competition}-home`} label="Home team" value={homeTeam} teams={teamOptions} exclude={awayTeam} badges={teamBadges} loading={teamsLoading} onSelect={(team) => { setHomeTeam(team); setPrediction(null); }} />
                  <span className="versus">VS</span>
                  <TeamPicker key={`${competition}-away`} label="Away team" value={awayTeam} teams={teamOptions} exclude={homeTeam} badges={teamBadges} loading={teamsLoading} onSelect={(team) => { setAwayTeam(team); setPrediction(null); }} />
                </div>
                <button className="primary-button" disabled={loading || teamsLoading || teamOptions.length < 2} type="submit">
                  {loading ? "Generating forecast…" : "Generate hypothetical forecast"}<span>→</span>
                </button>
              </form>
            )}

            <details className="odds-details">
              <summary>Add market odds <span>Optional</span></summary>
              <p>Your model forecast works without odds. Load odds for the selected scheduled match, or enter three decimal prices to compare it with the market.</p>
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
              <small>Market odds are converted to fair probabilities by removing the bookmaker margin. They are shown separately and do not change the model forecast.</small>
            </details>

            {(error || (mode === "explore" && teamCatalogError)) && <div className="message error-message">{error ?? teamCatalogError}</div>}

            {prediction && (
              <div className="result-panel" aria-live="polite">
                <div className="result-title">
                  <span>Model forecast · {prediction.kickoff_at ? "Scheduled fixture" : "Hypothetical matchup"}</span>
                  <strong>{LEAGUES[prediction.competition].name}</strong>
                </div>
                <div className="probabilities">
                  {probabilities.map((item, index) => (
                    <div className={`probability probability-${index}`} key={item.short}>
                      <div><span>{item.short}</span><strong>{percent(item.value)}</strong></div>
                      <div className="probability-track"><i style={{ width: percent(item.value) }} /></div>
                      <small className="probability-team"><TeamBadge name={item.label} src={"badge" in item ? item.badge : undefined} size="small" />{item.label}</small>
                    </div>
                  ))}
                </div>
                <div className="freshness">
                  <span>Model source: {prediction.model_policy.replaceAll("_", " ")}</span>
                  <span>History through {prediction.history_through} · {prediction.history_age_days} days old</span>
                </div>
                {prediction.market_home_win_probability !== null
                  && prediction.market_draw_probability !== null
                  && prediction.market_away_win_probability !== null ? (
                  <section className="market-comparison" aria-label="Model versus market probabilities">
                    <div className="market-comparison-heading">
                      <h3>Model vs market</h3>
                      <span>Fair market probabilities</span>
                    </div>
                    <p>Gap is model minus market in percentage points. Positive means the model assigns a higher probability to that outcome; it is not proof of betting value.</p>
                    <div className="market-comparison-grid" role="table" aria-label="Outcome probability comparison">
                      <div className="market-comparison-row market-comparison-head" role="row">
                        <span role="columnheader">Outcome</span><span role="columnheader">Model</span><span role="columnheader">Market</span><span role="columnheader">Gap</span>
                      </div>
                      {[
                        { label: `${prediction.home_team} win`, model: prediction.model_home_win_probability, market: prediction.market_home_win_probability },
                        { label: "Draw", model: prediction.model_draw_probability, market: prediction.market_draw_probability },
                        { label: `${prediction.away_team} win`, model: prediction.model_away_win_probability, market: prediction.market_away_win_probability },
                      ].map((row) => {
                        const gap = (row.model - row.market) * 100;
                        return (
                          <div className="market-comparison-row" role="row" key={row.label}>
                            <span role="cell">{row.label}</span>
                            <span role="cell">{percent(row.model)}</span>
                            <span role="cell">{percent(row.market)}</span>
                            <strong className={gap > 0 ? "gap-positive" : gap < 0 ? "gap-negative" : ""} role="cell">
                              {gap > 0 ? "+" : ""}{gap.toFixed(1)} pp
                            </strong>
                          </div>
                        );
                      })}
                    </div>
                  </section>
                ) : (
                  <p className="market-comparison-prompt">Want to compare this forecast with the market? Load live odds above, or enter the three prices.</p>
                )}
                <div className="context-panel">
                  <h3>What informs the model</h3>
                  <p>
                    {prediction.competition === "premier_league"
                      ? `Premier League probabilities combine Elo with a Poisson goal model. Both use pre-match history; the goal model also uses recent form, scoring/conceding rates, venue form, and rest. This summary does not assign an exact probability change to each factor.`
                      : "Greek league probabilities currently use team Elo ratings and home advantage. The form, goal, and venue figures below are context only; they do not directly change these probabilities."}
                    {` Snapshot through ${prediction.history_through}.`}
                  </p>
                  <div className="team-context-table" role="table" aria-label="Team form comparison">
                    <div className="team-context-row team-context-head" role="row">
                      <span role="columnheader">Metric</span><strong role="columnheader">{prediction.home_team}</strong><strong role="columnheader">{prediction.away_team}</strong>
                    </div>
                    <div className="team-context-row" role="row"><span role="rowheader">Team strength · Elo</span><strong>{prediction.context.home_elo.toFixed(0)}</strong><strong>{prediction.context.away_elo.toFixed(0)}</strong></div>
                    <div className="team-context-row" role="row"><span role="rowheader">Recent form · points / match</span><strong>{perMatch(prediction.context.home_form_points_per_match)} <small>({prediction.context.home_form_matches} matches)</small></strong><strong>{perMatch(prediction.context.away_form_points_per_match)} <small>({prediction.context.away_form_matches} matches)</small></strong></div>
                    <div className="team-context-row" role="row"><span role="rowheader">Recent goals · scored / conceded</span><strong>{perMatch(prediction.context.home_form_goals_for_per_match)} / {perMatch(prediction.context.home_form_goals_against_per_match)}</strong><strong>{perMatch(prediction.context.away_form_goals_for_per_match)} / {perMatch(prediction.context.away_form_goals_against_per_match)}</strong></div>
                    <div className="team-context-row" role="row"><span role="rowheader">Venue form · points / match</span><strong>{perMatch(prediction.context.home_venue_points_per_match)}</strong><strong>{perMatch(prediction.context.away_venue_points_per_match)}</strong></div>
                    <div className="team-context-row" role="row"><span role="rowheader">Recent head-to-head record</span><strong>{prediction.context.head_to_head_home_wins} wins · {prediction.context.head_to_head_draws} draws</strong><strong>{prediction.context.head_to_head_away_wins} wins · {prediction.context.head_to_head_draws} draws</strong></div>
                  </div>
                  <small>Head-to-head is shown as historical context and does not currently change the W/D/L probabilities. The current version does not use injuries, lineups, weather, or live odds as model inputs.</small>
                  {prediction.context.head_to_head_recent.length > 0 && (
                    <ul className="h2h-list" aria-label="Most recent head-to-head results">
                      {prediction.context.head_to_head_recent.map((meeting) => <li key={meeting}>{meeting}</li>)}
                    </ul>
                  )}
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
                      Promoted-team adjustment: {percent(prediction.components.base_model_weight)} core model ({outcomeSummary(prediction.components.core_model_probabilities)}) + {percent(1 - prediction.components.base_model_weight)} league prior ({outcomeSummary(prediction.components.league_prior_probabilities)}) = model probabilities ({outcomeSummary([prediction.model_home_win_probability, prediction.model_draw_probability, prediction.model_away_win_probability])}).
                    </p>
                  )}
                </div>
                <div className="component-panel scoreline-panel">
                  <h3>Most likely scorelines</h3>
                  <p>Separate estimate from the goal model, based on each team’s expected goals. Each scoreline is individually unlikely; these are the model’s three most likely outcomes.</p>
                  <div className="scoreline-list">
                    {prediction.components.top_scorelines.map((scoreline) => (
                      <div className="scoreline-row" key={`${scoreline.home_goals}-${scoreline.away_goals}`}>
                        <strong>{prediction.home_team} {scoreline.home_goals}–{scoreline.away_goals} {prediction.away_team}</strong>
                        <span>{percent(scoreline.probability)}</span>
                      </div>
                    ))}
                  </div>
                  {prediction.competition === "super_league_greece" && (
                    <small>Scorelines use the goal model; the Greek W/D/L probabilities continue to use Elo.</small>
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
                      <td>{item.market_probabilities ? "Model + market comparison" : "Model only"}</td>
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
