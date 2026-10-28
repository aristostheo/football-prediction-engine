import { useCallback, useEffect, useRef, useState } from "react";
import type { CSSProperties, FormEvent, KeyboardEvent } from "react";
import {
  getFixtures,
  getMarketOdds,
  getNextFixture,
  getScorecardSettlements,
  getTeamBadges,
  getTeams,
  predictMatch,
} from "../api";
import type { Competition, LiveFixture, MarketOddsQuote, Prediction, Settlement } from "../api";
import { loadFavoriteTeams, saveFavoriteTeams } from "../favorites";
import type { FavoriteTeams } from "../favorites";
import {
  attachMarketComparison,
  calculateMetrics,
  calculateTopPickCalibration,
  forecastKey,
  loadForecasts,
  marketAuditValues,
  MARKET_AUDIT_HEADERS,
  removeForecast,
  saveForecast,
} from "../scorecard";
import type { StoredForecast } from "../scorecard";
import { Icon, Brand, StadiumCanvas } from "./Visuals";
import type { IconName } from "./Visuals";
import { Club, FormPills } from "./Club";
import Betting from "./Betting";
import { useNavigationDrawer } from "./useNavigationDrawer";
import {
  dateAfter,
  dateLabel,
  isUpcoming,
  leagueName,
  leagues,
  localDate,
  message,
  marketQuoteNote,
  mergeSettlements,
  modelProbabilities,
  normalizeOdds,
  oddsForCalculation,
  pct,
  scoreMatrix,
  teamShort,
  timeLabel,
} from "./live";
import "./theme.css";
import "./live.css";

type Page = "center" | "teams" | "scorecard" | "studio";
type Tab = "overview" | "market" | "form" | "h2h";
type Selected = LiveFixture & { hypothetical?: boolean };
const pages: { id: Page; title: string; icon: IconName }[] = [
  { id: "center", title: "Match center", icon: "grid" },
  { id: "teams", title: "My teams", icon: "star" },
  { id: "scorecard", title: "Forecast journal", icon: "chart" },
  { id: "studio", title: "Model studio", icon: "layers" },
];
function initialTheme() {
  try {
    return localStorage.getItem("match-forecast.theme") === "night";
  } catch {
    return false;
  }
}
function cachedSettlements(): Record<string, Settlement> {
  try {
    const parsed: unknown = JSON.parse(
      localStorage.getItem("match-forecast.settlements.v1") ?? "{}",
    );
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed))
      return {};
    return Object.fromEntries(
      Object.entries(parsed).filter(([id, value]) => {
        if (!value || typeof value !== "object") return false;
        const item = value as Settlement;
        return (
          item.id === id &&
          ["H", "D", "A", null].includes(item.result) &&
          [item.home_goals, item.away_goals].every(
            (score) =>
              score === null || (Number.isInteger(score) && score >= 0),
          )
        );
      }),
    );
  } catch {
    return {};
  }
}

async function localFixtures(
  competition: Competition,
  day: string,
): Promise<LiveFixture[]> {
  const dates = [
    ...new Set([
      new Date(`${day}T00:00:00`).toISOString().slice(0, 10),
      new Date(`${day}T23:59:59`).toISOString().slice(0, 10),
    ]),
  ];
  const values = await Promise.all(
    dates.map((date) => getFixtures(competition, date)),
  );
  return [
    ...new Map(
      values
        .flat()
        .filter((f) => localDate(f.kickoff_at) === day)
        .map((f) => [f.fixture_id, f]),
    ).values(),
  ];
}

export default function Dashboard() {
  const [page, setPage] = useState<Page>("center");
  const [competition, setCompetition] = useState<Competition>("premier_league");
  const [teams, setTeams] = useState<Partial<Record<Competition, string[]>>>(
    {},
  );
  const [badges, setBadges] = useState<
    Partial<Record<Competition, Record<string, string>>>
  >({});
  const [favorites, setFavorites] = useState<FavoriteTeams>(loadFavoriteTeams);
  const [selected, setSelected] = useState<Selected | null>(null);
  const [fixtures, setFixtures] = useState<LiveFixture[]>([]);
  const [browseDate, setBrowseDate] = useState(localDate());
  const [nextFrom, setNextFrom] = useState(localDate());
  const [reload, setReload] = useState(0);
  const [fixturesLoading, setFixturesLoading] = useState(true);
  const [fixturesError, setFixturesError] = useState("");
  const [teamsError, setTeamsError] = useState("");
  const [badgeNotice, setBadgeNotice] = useState("");
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [generating, setGenerating] = useState(false);
  const [predictionError, setPredictionError] = useState("");
  const [tab, setTab] = useState<Tab>("overview");
  const [scoreView, setScoreView] = useState<"scores" | "map">("scores");
  const [night, setNight] = useState(initialTheme);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [onlyFavorites, setOnlyFavorites] = useState(false);
  const [teamQuery, setTeamQuery] = useState("");
  const [prices, setPrices] = useState(["", "", ""]);
  const [market, setMarket] = useState<[number, number, number] | null>(null);
  const [marketNote, setMarketNote] = useState("");
  const [marketSnapshot, setMarketSnapshot] = useState<MarketOddsQuote>();
  const [marketError, setMarketError] = useState("");
  const [oddsLoading, setOddsLoading] = useState(false);
  const [records, setRecords] = useState<StoredForecast[]>(loadForecasts);
  const [settlements, setSettlements] =
    useState<Record<string, Settlement>>(cachedSettlements);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [resultsError, setResultsError] = useState("");
  const [resultCheckedAt, setResultCheckedAt] = useState("");
  const [recordFilter, setRecordFilter] = useState("all");
  const [journalLeague, setJournalLeague] = useState<Competition | "all">(
    "all",
  );
  const [toast, setToast] = useState("");
  const [exploreOpen, setExploreOpen] = useState(false);
  const [exploreLeague, setExploreLeague] =
    useState<Competition>("premier_league");
  const [exploreHome, setExploreHome] = useState("");
  const [exploreAway, setExploreAway] = useState("");
  const [exploreError, setExploreError] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const sidebar = useRef<HTMLElement>(null);
  useNavigationDrawer(sidebar, sidebarOpen, () => setSidebarOpen(false));
  const fixtureRequest = useRef(0),
    forecastRequest = useRef(0),
    oddsRequest = useRef(0),
    resultRequest = useRef(0);
  const manualSelection = useRef(false);
  const toastTimer = useRef<number | undefined>(undefined);
  const recordsRef = useRef(records);
  recordsRef.current = records;
  const favoritesRef = useRef(favorites);
  favoritesRef.current = favorites;
  const settlementsRef = useRef(settlements);
  settlementsRef.current = settlements;

  useEffect(() => {
    saveFavoriteTeams(favorites);
  }, [favorites]);
  useEffect(() => {
    try {
      localStorage.setItem(
        "match-forecast.theme",
        night ? "night" : "daylight",
      );
    } catch {
      /* Theme stays usable. */
    }
  }, [night]);
  useEffect(() => {
    document.title = "Match Forecast — Touchline";
    return () => window.clearTimeout(toastTimer.current);
  }, []);
  useEffect(() => {
    if (exploreOpen && !dialog.current?.open) dialog.current?.showModal();
    if (!exploreOpen && dialog.current?.open) dialog.current?.close();
  }, [exploreOpen]);
  useEffect(() => {
    let active = true;
    const id = ++fixtureRequest.current;
    getTeams(competition)
      .then((values) => {
        if (active) {
          setTeams((current) => ({ ...current, [competition]: values }));
          setTeamsError("");
        }
      })
      .catch((error) => {
        if (active) setTeamsError(message(error));
      });
    getTeamBadges(competition)
      .then((values) => {
        if (active) {
          setBadges((current) => ({ ...current, [competition]: values }));
          setBadgeNotice("");
        }
      })
      .catch(() => {
        if (active)
          setBadgeNotice(
            "Some club crests are unavailable. Club names remain available.",
          );
      });
    getNextFixture(
      competition,
      new Date(`${nextFrom}T00:00:00`).toISOString().slice(0, 10),
    )
      .then(async (next) => {
        if (!active || id !== fixtureRequest.current) return;
        const day = next ? localDate(next.kickoff_at) : nextFrom;
        const values = next ? await localFixtures(competition, day) : [];
        if (!active || id !== fixtureRequest.current) return;
        const currentFixtures = values.filter(
          (f) => localDate(f.kickoff_at) === day,
        );
        // Include the discovered fixture even if a subsequent provider response changes.
        const all =
          next && !currentFixtures.some((f) => f.fixture_id === next.fixture_id)
            ? [next, ...currentFixtures]
            : currentFixtures;
        setFixtures(all);
        setBrowseDate(day);
        setFixturesError("");
        const upcoming = all
          .filter(isUpcoming)
          .sort((a, b) => Date.parse(a.kickoff_at) - Date.parse(b.kickoff_at));
        const followed = favoritesRef.current[competition] ?? [];
        const preferred = upcoming.find(
          (f) =>
            followed.includes(f.home_team) || followed.includes(f.away_team),
        );
        if (!manualSelection.current)
          selectMatch(preferred ?? upcoming[0] ?? null);
      })
      .catch((error) => {
        if (active && id === fixtureRequest.current) {
          setFixturesError(message(error));
          setFixtures([]);
          if (!manualSelection.current) selectMatch(null);
        }
      })
      .finally(() => {
        if (active && id === fixtureRequest.current) setFixturesLoading(false);
      });
    return () => {
      active = false;
    };
  }, [competition, nextFrom, reload]);
  useEffect(() => {
    if (!exploreOpen) return;
    let active = true;
    getTeams(exploreLeague)
      .then((values) => {
        if (active)
          setTeams((current) => ({ ...current, [exploreLeague]: values }));
      })
      .catch((error) => {
        if (active) setExploreError(message(error));
      });
    return () => {
      active = false;
    };
  }, [exploreLeague, exploreOpen]);
  const checkResults = useCallback(
    async (isActive: () => boolean = () => true) => {
      if (!records.length) return;
      const id = ++resultRequest.current;
      setResultsLoading(true);
      setResultsError("");
      try {
        const details = await getScorecardSettlements(records);
        if (id !== resultRequest.current || !isActive()) return;
        const merged = mergeSettlements(settlementsRef.current, details);
        setSettlements(merged);
        setResultCheckedAt(new Date().toISOString());
        try {
          localStorage.setItem(
            "match-forecast.settlements.v1",
            JSON.stringify(merged),
          );
        } catch {
          /* Results remain visible. */
        }
      } catch (error) {
        if (id === resultRequest.current && isActive())
          setResultsError(message(error));
      } finally {
        if (id === resultRequest.current && isActive())
          setResultsLoading(false);
      }
    },
    [records],
  );

  useEffect(() => {
    if (page !== "scorecard" || !records.length) return;
    let active = true;
    const check = () => {
      if (active && document.visibilityState !== "hidden")
        void checkResults(() => active);
    };
    check();
    const timer = window.setInterval(check, 300000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [page, records, checkResults]);

  const activeLeague = leagues.find((l) => l.id === competition)!;
  const catalog = teams[competition] ?? [];
  const followed = favorites[competition] ?? [];
  const favoriteCount = Object.values(favorites).reduce(
    (sum, list) => sum + (list?.length ?? 0),
    0,
  );
  const p = prediction ? modelProbabilities(prediction) : null;
  const winner = p ? p.indexOf(Math.max(...p)) : 0;
  const home = selected?.home_team ?? "",
    away = selected?.away_team ?? "";
  const currentRecord = prediction
    ? records.find((r) => forecastKey(r) === forecastKey(prediction))
    : undefined;
  const visibleFixtures = fixtures
    .filter(
      (f) =>
        !onlyFavorites ||
        followed.includes(f.home_team) ||
        followed.includes(f.away_team),
    )
    .sort(
      (a, b) =>
        Number(
          followed.includes(b.home_team) || followed.includes(b.away_team),
        ) -
          Number(
            followed.includes(a.home_team) || followed.includes(a.away_team),
          ) || Date.parse(a.kickoff_at) - Date.parse(b.kickoff_at),
    );
  const results = Object.fromEntries(
    records.map((r) => [r.id, settlements[r.id]?.result ?? null]),
  );
  const filteredRecords = records
    .filter(
      (r) =>
        (journalLeague === "all" || r.competition === journalLeague) &&
        (recordFilter === "all" ||
          (recordFilter === "pending" ? !results[r.id] : !!results[r.id])),
    )
    .sort((a, b) => Date.parse(b.kickoff_at) - Date.parse(a.kickoff_at));
  const metricRecords = records.filter(
    (r) => journalLeague === "all" || r.competition === journalLeague,
  );
  const metrics = calculateMetrics(
    metricRecords,
    results,
    (r) => r.model_probabilities,
  );
  const matchedRecords = metricRecords.filter(
    (r) => r.market_probabilities && results[r.id],
  );
  const matchedModelMetrics = calculateMetrics(
    matchedRecords,
    results,
    (r) => r.model_probabilities,
  );
  const marketMetrics = calculateMetrics(
    matchedRecords,
    results,
    (r) => r.market_probabilities,
  );
  const calibration = calculateTopPickCalibration(
    metricRecords,
    results,
    (r) => r.model_probabilities,
  );

  function notify(value: string) {
    setToast(value);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(""), 4500);
  }
  function handleAnalysisKeys(event: KeyboardEvent<HTMLDivElement>) {
    const order: Tab[] = ["overview", "market", "form", "h2h"];
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const index = order.indexOf(tab);
    const next = event.key === "Home" ? 0 : event.key === "End" ? order.length - 1
      : (index + (event.key === "ArrowRight" ? 1 : -1) + order.length) % order.length;
    setTab(order[next]);
    document.getElementById(`live-tab-${order[next]}`)?.focus();
  }
  function navigate(next: Page) {
    setPage(next);
    setSidebarOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  function selectMatch(fixture: Selected | null) {
    forecastRequest.current++;
    oddsRequest.current++;
    setSelected(fixture);
    setPrediction(null);
    setPredictionError("");
    setGenerating(false);
    setPrices(["", "", ""]);
    setMarket(null);
    setMarketError("");
    setMarketNote("");
    setMarketSnapshot(undefined);
    setOddsLoading(false);
    setTab("overview");
  }
  function changeLeague(next: Competition) {
    fixtureRequest.current++;
    manualSelection.current = false;
    selectMatch(null);
    setCompetition(next);
    setReload((n) => n + 1);
    setFixtures([]);
    setFixturesError("");
    setTeamsError("");
    setBadgeNotice("");
    setNextFrom(localDate());
    setBrowseDate(localDate());
    setFixturesLoading(true);
    setOnlyFavorites(false);
    setSidebarOpen(false);
    setTeamQuery("");
  }
  function chooseFixture(fixture: LiveFixture) {
    manualSelection.current = false;
    selectMatch(fixture);
    setBrowseDate(localDate(fixture.kickoff_at));
    navigate("center");
  }
  function toggleFavorite(name: string, league = competition) {
    setFavorites((current) => ({
      ...current,
      [league]: (current[league] ?? []).includes(name)
        ? (current[league] ?? []).filter((t) => t !== name)
        : [...(current[league] ?? []), name],
    }));
  }
  function badge(name: string, league = competition) {
    return badges[league]?.[name] ?? badges[league]?.[name.toLowerCase()];
  }
  function club(
    name: string,
    league = competition,
    src?: string | null,
    large = false,
  ) {
    return (
      <Club
        key={`${league}|${name}|${src ?? ""}`}
        name={name}
        competition={league}
        src={src ?? badge(name, league)}
        large={large}
      />
    );
  }
  async function browse(day: string) {
    manualSelection.current = false;
    const id = ++fixtureRequest.current;
    setBrowseDate(day);
    setFixturesLoading(true);
    setFixturesError("");
    setFixtures([]);
    selectMatch(null);
    try {
      const all = await localFixtures(competition, day);
      if (id !== fixtureRequest.current) return;
      setFixtures(all);
      setCalendarOpen(false);
      const eligible = all
        .filter(isUpcoming)
        .sort((a, b) => Date.parse(a.kickoff_at) - Date.parse(b.kickoff_at));
      selectMatch(
        eligible.find(
          (f) =>
            followed.includes(f.home_team) || followed.includes(f.away_team),
        ) ??
          eligible[0] ??
          all[0] ??
          null,
      );
    } catch (error) {
      if (id === fixtureRequest.current) setFixturesError(message(error));
    } finally {
      if (id === fixtureRequest.current) setFixturesLoading(false);
    }
  }
  function findNext() {
    manualSelection.current = false;
    fixtureRequest.current++;
    selectMatch(null);
    setFixturesLoading(true);
    setFixturesError("");
    setNextFrom(dateAfter(browseDate, fixtures.length ? 1 : 21));
    setReload((n) => n + 1);
  }
  async function generate() {
    if (!selected || (!selected.hypothetical && !isUpcoming(selected))) return;
    const id = ++forecastRequest.current;
    setGenerating(true);
    setPredictionError("");
    try {
      const hasOdds = prices.some((value) => value.trim() !== "");
      const calculationPrices = oddsForCalculation(prices, marketSnapshot);
      if (hasOdds) normalizeOdds(calculationPrices);
      const response = await predictMatch({
        competition,
        home_team: home,
        away_team: away,
        kickoff_date: selected.hypothetical
          ? localDate()
          : selected.kickoff_at.slice(0, 10),
        ...(selected.hypothetical ? {} : { kickoff_at: selected.kickoff_at }),
        ...(hasOdds
          ? {
              odds_home: Number(calculationPrices[0]),
              odds_draw: Number(calculationPrices[1]),
              odds_away: Number(calculationPrices[2]),
            }
          : {}),
      });
      if (id !== forecastRequest.current) return;
      setPrediction(response);
      if (response.kickoff_at) {
        setRecords(saveForecast(response, recordsRef.current, marketSnapshot));
        notify(
          "Forecast saved before kickoff. The journal will check the final result.",
        );
      } else
        notify(
          "Hypothetical forecast ready. It is not recorded in the journal.",
        );
      if (hasOdds) setMarket(normalizeOdds(calculationPrices));
    } catch (error) {
      if (id === forecastRequest.current) setPredictionError(message(error));
    } finally {
      if (id === forecastRequest.current) setGenerating(false);
    }
  }
  async function loadOdds() {
    if (!selected || selected.hypothetical || !isUpcoming(selected)) return;
    const id = ++oddsRequest.current;
    setOddsLoading(true);
    setMarketError("");
    try {
      const quote = await getMarketOdds(selected);
      if (id !== oddsRequest.current) return;
      const values = [
        String(quote.home_fair_odds),
        String(quote.draw_fair_odds),
        String(quote.away_fair_odds),
      ];
      const comparison = normalizeOdds(values);
      setPrices(values.map((value) => Number(value).toFixed(2)));
      setMarket(comparison);
      setMarketSnapshot(quote);
      setMarketNote(marketQuoteNote(quote));
      if (prediction)
        setRecords(
          attachMarketComparison(prediction, comparison, recordsRef.current, quote),
        );
      notify(
        "Market odds loaded. The independent model forecast is unchanged.",
      );
    } catch (error) {
      if (id === oddsRequest.current) setMarketError(message(error));
    } finally {
      if (id === oddsRequest.current) setOddsLoading(false);
    }
  }
  function compareOdds(event: FormEvent) {
    event.preventDefault();
    try {
      const comparison = normalizeOdds(oddsForCalculation(prices, marketSnapshot));
      setMarket(comparison);
      setMarketError("");
      setMarketNote(marketSnapshot
        ? marketQuoteNote(marketSnapshot)
        : "Manually entered decimal odds · margin removed");
      if (prediction)
        setRecords(
          attachMarketComparison(prediction, comparison, recordsRef.current, marketSnapshot),
        );
      notify("Market comparison updated.");
    } catch (error) {
      setMarketError(message(error));
    }
  }
  function openExplorer() {
    setExploreLeague(competition);
    setExploreHome(catalog[0] ?? "");
    setExploreAway(catalog[1] ?? "");
    setExploreError("");
    setExploreOpen(true);
  }
  function explore(event: FormEvent) {
    event.preventDefault();
    const values = teams[exploreLeague] ?? [];
    const h = values.find(
        (t) => t.toLocaleLowerCase() === exploreHome.trim().toLocaleLowerCase(),
      ),
      a = values.find(
        (t) => t.toLocaleLowerCase() === exploreAway.trim().toLocaleLowerCase(),
      );
    if (!h || !a || h === a) {
      setExploreError(
        "Choose two different clubs from this league's team list.",
      );
      return;
    }
    if (exploreLeague !== competition) changeLeague(exploreLeague);
    manualSelection.current = true;
    selectMatch({
      fixture_id: "hypothetical",
      competition: exploreLeague,
      home_team: h,
      away_team: a,
      kickoff_at: "",
      hypothetical: true,
      venue: "A hypothetical matchup",
    });
    setExploreOpen(false);
    navigate("center");
  }
  function exportJournal() {
    const cell = (v: unknown) => `"${String(v ?? "").replaceAll('"', '""')}"`;
    const rows = filteredRecords.map((r) => {
      const s = settlements[r.id];
      const picked = r.model_probabilities.indexOf(
        Math.max(...r.model_probabilities),
      );
      return [
        leagueName(r.competition),
        r.home_team,
        r.away_team,
        r.kickoff_at,
        r.forecasted_at,
        ...r.model_probabilities,
        ["H", "D", "A"][picked],
        r.predicted_scoreline
          ? `${r.predicted_scoreline.home_goals}-${r.predicted_scoreline.away_goals}`
          : "",
        s?.result ?? "Pending",
        s?.home_goals,
        s?.away_goals,
        ...(r.market_probabilities ?? ["", "", ""]),
        r.model_policy,
        r.history_through,
        ...marketAuditValues(r),
      ];
    });
    const csv = [
      [
        "League",
        "Home",
        "Away",
        "Kickoff",
        "Forecasted at",
        "Model home",
        "Model draw",
        "Model away",
        "Model pick",
        "Predicted score",
        "Actual outcome",
        "Actual home goals",
        "Actual away goals",
        "Market home",
        "Market draw",
        "Market away",
        "Policy",
        "History through",
        ...MARKET_AUDIT_HEADERS,
      ],
      ...rows,
    ]
      .map((row) => row.map(cell).join(","))
      .join("\r\n");
    const url = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "match-forecast-journal.csv";
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return (
    <div className={`tl-app tl-live ${night ? "tl-night" : ""}`}>
      <a className="tl-skip-link" href="#main-content">Skip to content</a>
      {sidebarOpen && (
        <button
          className="tl-sidebar-overlay"
          aria-label="Dismiss navigation backdrop"
          tabIndex={-1}
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <aside
        ref={sidebar}
        id="main-navigation"
        className={`tl-sidebar ${sidebarOpen ? "tl-sidebar-open" : ""}`}
        role={sidebarOpen ? "dialog" : undefined}
        aria-modal={sidebarOpen || undefined}
        aria-label="Navigation"
      >
        <div className="tl-sidebar-brand">
          <Brand />
          <button className="tl-icon-button tl-drawer-close" aria-label="Close navigation" onClick={() => setSidebarOpen(false)}>
            <Icon name="close" />
          </button>
        </div>
        <div className="tl-sidebar-label">YOUR WORKSPACE</div>
        <nav aria-label="Main navigation">
          {pages.map((item) => (
            <button
              key={item.id}
              className={page === item.id ? "tl-nav-active" : ""}
              onClick={() => navigate(item.id)}
              aria-current={page === item.id ? "page" : undefined}
            >
              <Icon name={item.icon} />
              <span>{item.title}</span>
              {item.id === "teams" && <small>{favoriteCount}</small>}
              {item.id === "center" && <i />}
            </button>
          ))}
        </nav>
        <div className="tl-sidebar-label tl-leagues-label">
          THE COMPETITIONS <span>07</span>
        </div>
        <div className="tl-league-list">
          {leagues.map((item) => (
            <button
              key={item.id}
              className={competition === item.id ? "tl-league-active" : ""}
              onClick={() => changeLeague(item.id)}
            >
              <span
                className="tl-league-mark"
                style={{ "--league-color": item.color } as CSSProperties}
              >
                {item.code}
              </span>
              <span>
                {item.name}
                <small>{item.country}</small>
              </span>
              {competition === item.id && <Icon name="chevron" size={14} />}
            </button>
          ))}
        </div>
        <div className="tl-sidebar-bottom">
          <div className="tl-edition-mark">
            A new perspective.
            <br />
            <span>The same love for football.</span>
          </div>
          <p>
            Forecasts & favourites stay in this browser.
            <br />
            Real fixtures. Independent probabilities.
          </p>
        </div>
      </aside>
      <div className="tl-workspace" inert={sidebarOpen}>
        <header className="tl-topbar">
          <div className="tl-topbar-left">
            <button
              className="tl-icon-button tl-mobile-menu"
              aria-label="Open navigation"
              aria-expanded={sidebarOpen}
              aria-controls="main-navigation"
              onClick={() => setSidebarOpen(true)}
            >
              <Icon name="menu" />
            </button>
            <span className="tl-breadcrumb">
              WORKSPACE <span>/</span>
              {pages.find((item) => item.id === page)!.title.toUpperCase()}
            </span>
          </div>
          <div className="tl-topbar-actions">
            <span className="tl-preview-pill">
              <i /> TOUCHLINE
            </span>
            <button
              className="tl-icon-button"
              aria-label={
                night ? "Switch to daylight theme" : "Switch to night theme"
              }
              onClick={() => setNight((value) => !value)}
            >
              <Icon name={night ? "sun" : "moon"} size={19} />
            </button>
            <button
              className="tl-avatar"
              onClick={() => navigate("teams")}
              aria-label="Open your favorite teams"
            >
              <Icon name="star" size={17} />
            </button>
          </div>
        </header>
        <main className="tl-main" id="main-content" tabIndex={-1}>
          {page === "center" && (
            <>
              <section className="tl-page-heading">
                <div>
                  <div className="tl-kicker">
                    <span /> FOOTBALL, FROM A DIFFERENT ANGLE
                  </div>
                  <h1>
                    Read the <em>game.</em>
                  </h1>
                  <p>
                    Find your match. See the possibilities. Understand the why.
                  </p>
                </div>
                <button className="tl-outline-button" onClick={openExplorer}>
                  <Icon name="swap" size={17} /> Explore a matchup{" "}
                  <Icon name="arrow" size={17} />
                </button>
              </section>
              <section className="tl-matchday" aria-label="Browse fixtures">
                <div className="tl-matchday-toolbar">
                  <div className="tl-matchday-date">
                    <span className="tl-mini-label">MATCHDAY</span>
                    <button
                      className="tl-icon-button"
                      aria-label="Previous matchday"
                      onClick={() => void browse(dateAfter(browseDate, -1))}
                    >
                      <Icon name="back" size={16} />
                    </button>
                    <button
                      className="tl-date-button"
                      aria-expanded={calendarOpen}
                      onClick={() => setCalendarOpen((value) => !value)}
                    >
                      <Icon name="calendar" size={17} />
                      {dateLabel(browseDate)}
                      <Icon name="chevron" size={13} />
                    </button>
                    <button
                      className="tl-icon-button"
                      aria-label="Next matchday"
                      onClick={() => void browse(dateAfter(browseDate, 1))}
                    >
                      <Icon name="arrow" size={16} />
                    </button>
                  </div>
                  <div className="tl-segmented">
                    <button
                      className={!onlyFavorites ? "tl-segment-active" : ""}
                      onClick={() => setOnlyFavorites(false)}
                    >
                      All matches
                    </button>
                    <button
                      className={onlyFavorites ? "tl-segment-active" : ""}
                      onClick={() => setOnlyFavorites(true)}
                    >
                      <Icon name="star" size={12} /> Following
                    </button>
                  </div>
                </div>
                {calendarOpen && (
                  <div className="tl-calendar">
                    <label>
                      Choose a matchday
                      <input
                        type="date"
                        value={browseDate}
                        onChange={(e) => {
                          if (e.target.value) void browse(e.target.value);
                        }}
                      />
                    </label>
                    <small>Kickoff times use your device's timezone.</small>
                    <button onClick={() => void browse(localDate())}>
                      Today <Icon name="arrow" size={14} />
                    </button>
                  </div>
                )}
                {fixturesError && (
                  <div className="tl-error" role="alert">
                    {fixturesError}
                    <button
                      className="tl-text-button"
                      onClick={() => {
                        setFixturesLoading(true);
                        setReload((n) => n + 1);
                      }}
                    >
                      Retry fixture search
                    </button>
                  </div>
                )}
                <div className="tl-fixture-strip" aria-busy={fixturesLoading}>
                  {fixturesLoading ? (
                    <div className="tl-fixture-empty" role="status">
                      <Icon name="clock" size={24} />
                      <div>
                        <strong>Finding your next match…</strong>
                        <p>
                          Searching upcoming fixtures in {activeLeague.name}.
                        </p>
                      </div>
                    </div>
                  ) : (
                    visibleFixtures.map((fixture) => (
                      <button
                        key={fixture.fixture_id}
                        className={`tl-fixture ${selected?.fixture_id === fixture.fixture_id ? "tl-fixture-selected" : ""}`}
                        onClick={() => chooseFixture(fixture)}
                        aria-pressed={
                          selected?.fixture_id === fixture.fixture_id
                        }
                      >
                        <div className="tl-fixture-time">
                          <span>
                            {timeLabel(fixture.kickoff_at)}
                            <small> LOCAL</small>
                          </span>
                          {(followed.includes(fixture.home_team) ||
                            followed.includes(fixture.away_team)) && (
                            <Icon name="star" size={12} filled />
                          )}
                        </div>
                        <div className="tl-fixture-clubs">
                          <span>
                            {club(
                              fixture.home_team,
                              competition,
                              fixture.home_badge_url,
                            )}
                            {teamShort(fixture.home_team)}
                          </span>
                          <span className="tl-fixture-vs">—</span>
                          <span>
                            {club(
                              fixture.away_team,
                              competition,
                              fixture.away_badge_url,
                            )}
                            {teamShort(fixture.away_team)}
                          </span>
                        </div>
                        <div className="tl-fixture-footer">
                          <span>
                            {fixture.home_goals != null &&
                            fixture.away_goals != null
                              ? `FT ${fixture.home_goals}–${fixture.away_goals}`
                              : !isUpcoming(fixture)
                                ? (fixture.status ?? "Kickoff passed")
                                : selected?.fixture_id === fixture.fixture_id
                                  ? "IN FOCUS"
                                  : "View forecast"}
                          </span>
                          <Icon name="arrow" size={14} />
                        </div>
                      </button>
                    ))
                  )}
                  {!fixturesLoading &&
                    !fixturesError &&
                    !visibleFixtures.length && (
                      <div className="tl-fixture-empty">
                        <Icon name="calendar" size={24} />
                        <div>
                          <strong>
                            {onlyFavorites
                              ? "No followed clubs on this matchday."
                              : "No fixtures found in this view."}
                          </strong>
                          <p>
                            {onlyFavorites
                              ? "View all matches or choose another date."
                              : "Choose a date, explore a matchup, or search the next window."}
                          </p>
                        </div>
                        <button
                          className="tl-text-button"
                          onClick={
                            onlyFavorites
                              ? () => setOnlyFavorites(false)
                              : findNext
                          }
                        >
                          {onlyFavorites
                            ? "View all matches"
                            : "Find next matches"}
                          <Icon name="arrow" size={14} />
                        </button>
                      </div>
                    )}
                </div>
              </section>
              {selected ? (
                <>
                  <section
                    className="tl-focus-grid"
                    aria-label="Selected match forecast"
                  >
                    <article className="tl-match-hero">
                      <StadiumCanvas />
                      <div className="tl-match-hero-top">
                        <span className="tl-match-league">
                          <span style={{ background: activeLeague.color }}>
                            {activeLeague.code}
                          </span>
                          {selected.hypothetical
                            ? "MATCHUP EXPLORER"
                            : activeLeague.name.toUpperCase()}
                        </span>
                        <span className="tl-match-kickoff">
                          <Icon name="clock" size={14} />
                          {selected.hypothetical
                            ? "HYPOTHETICAL"
                            : `${dateLabel(localDate(selected.kickoff_at), true)} · ${timeLabel(selected.kickoff_at)}`}
                        </span>
                      </div>
                      <div className="tl-match-teams">
                        {[home, away].map((name, i) => (
                          <div className="tl-match-team" key={i}>
                            <button
                              className={`tl-follow-hero ${followed.includes(name) ? "is-following" : ""}`}
                              onClick={() => toggleFavorite(name)}
                              aria-label={`${followed.includes(name) ? "Unfollow" : "Follow"} ${name}`}
                            >
                              <Icon
                                name="star"
                                size={15}
                                filled={followed.includes(name)}
                              />
                            </button>
                            {club(
                              name,
                              competition,
                              i === 0
                                ? selected.home_badge_url
                                : selected.away_badge_url,
                              true,
                            )}
                            <span className="tl-team-role">
                              {i === 0 ? "HOME" : "AWAY"}
                            </span>
                            <h2>{teamShort(name)}</h2>
                          </div>
                        ))}
                      </div>
                      <div className="tl-versus-art tl-live-versus">
                        <strong>vs</strong>
                      </div>
                      <div className="tl-match-hero-bottom">
                        <div>
                          <span className="tl-mini-label">RECENT FORM</span>
                          <FormPills
                            name={home}
                            results={
                              prediction?.context.home_form_results ?? []
                            }
                          />
                        </div>
                        <span className="tl-venue">
                          <Icon name="pin" size={13} />
                          {selected.venue ?? "Venue not supplied"}
                        </span>
                        <div>
                          <span className="tl-mini-label">RECENT FORM</span>
                          <FormPills
                            name={away}
                            results={
                              prediction?.context.away_form_results ?? []
                            }
                          />
                        </div>
                      </div>
                    </article>
                    <article
                      className={`tl-forecast ${generating ? "tl-generating" : ""}`}
                    >
                      <div className="tl-panel-heading">
                        <span className="tl-mini-label">
                          THE MODEL FORECAST
                        </span>
                        <button
                          className={`tl-icon-button ${currentRecord ? "tl-saved" : ""}`}
                          disabled={!prediction || selected.hypothetical}
                          aria-label={
                            currentRecord
                              ? "Forecast saved to journal"
                              : "Save forecast to journal"
                          }
                          title={
                            currentRecord
                              ? "Saved automatically before kickoff"
                              : "Scheduled forecasts are saved automatically"
                          }
                          onClick={() => {
                            if (prediction && !selected.hypothetical) {
                              setRecords(
                                saveForecast(prediction, recordsRef.current),
                              );
                              notify("Forecast saved to your journal.");
                            }
                          }}
                        >
                          <Icon
                            name={currentRecord ? "check" : "bookmark"}
                            size={18}
                          />
                        </button>
                      </div>
                      {p ? (
                        <>
                          <div className="tl-forecast-pick">
                            <span className="tl-pick-label">
                              <i />
                              {winner === 1
                                ? "Draw is most likely"
                                : `${teamShort(winner === 0 ? home : away)} to win`}
                            </span>
                            <div className="tl-jumbo-probability">
                              {(p[winner] * 100).toFixed(1)}
                              <span>%</span>
                            </div>
                            <p>Most likely outcome · independent model</p>
                          </div>
                          <div
                            className="tl-probability-rail"
                            aria-hidden="true"
                          >
                            {p.map((value, i) => (
                              <span
                                className={`tl-outcome-${i}`}
                                style={{ width: pct(value) }}
                                key={i}
                              />
                            ))}
                          </div>
                          <div className="tl-outcome-values">
                            {["HOME", "DRAW", "AWAY"].map((name, i) => (
                              <div key={name}>
                                <span>
                                  <i className={`tl-outcome-${i}`} />
                                  {name}
                                </span>
                                <strong>{pct(p[i])}</strong>
                              </div>
                            ))}
                          </div>
                        </>
                      ) : (
                        <div className="tl-forecast-empty">
                          <span className="tl-pick-label">
                            <i /> A clearer view of the match
                          </span>
                          <h3>
                            Ready when
                            <br />
                            <em>you are.</em>
                          </h3>
                          <p>
                            Generate a forecast to see real model probabilities
                            and match context.
                          </p>
                        </div>
                      )}
                      {predictionError && (
                        <p className="tl-error" role="alert">
                          {predictionError}
                        </p>
                      )}
                      <button
                        className="tl-orange-button"
                        onClick={() => void generate()}
                        disabled={
                          generating ||
                          (!selected.hypothetical && !isUpcoming(selected))
                        }
                      >
                        <Icon name="bolt" size={17} />
                        <span>
                          {generating
                            ? "Reading the game…"
                            : prediction
                              ? "Regenerate forecast"
                              : "Generate forecast"}
                        </span>
                        <Icon name="arrow" size={18} />
                      </button>
                      <div className="tl-forecast-foot">
                        <span>
                          <i />
                          {selected.hypothetical
                            ? "HYPOTHETICAL MATCHUP"
                            : !isUpcoming(selected)
                              ? "KICKOFF PASSED"
                              : currentRecord
                                ? "SAVED BEFORE KICKOFF"
                                : "UPCOMING MATCH"}
                        </span>
                        <button onClick={() => setTab("market")}>
                          Compare odds <Icon name="arrow" size={12} />
                        </button>
                      </div>
                    </article>
                  </section>
                  {prediction && (
                    <div
                      className={`tl-freshness ${prediction.history_age_days > 21 ? "tl-freshness-warning" : ""}`}
                    >
                      <Icon name="clock" size={17} />
                      <span>
                        Training results through{" "}
                        <strong>{prediction.history_through}</strong> ·{" "}
                        {prediction.history_age_days} days before this matchup.{" "}
                        {prediction.history_age_days > 21
                          ? "History is dated; treat the forecast with extra caution."
                          : "Uses the results available to this model."}
                      </span>
                      <small>
                        {prediction.components.elo_weight === 1 ? "Elo forecast" : "Elo + goal model"}
                      </small>
                    </div>
                  )}
                  <div className="tl-insights-nav">
                    <div role="tablist" aria-label="Match analysis" onKeyDown={handleAnalysisKeys}>
                      {(
                        [
                          { id: "overview", label: "The bigger picture" },
                          { id: "market", label: "Betting" },
                          { id: "form", label: "Team performance" },
                          { id: "h2h", label: "Head to head" },
                        ] as { id: Tab; label: string }[]
                      ).map((item) => (
                        <button
                          role="tab"
                          id={`live-tab-${item.id}`}
                          aria-controls={`live-panel-${item.id}`}
                          aria-selected={tab === item.id}
                          tabIndex={tab === item.id ? 0 : -1}
                          key={item.id}
                          className={tab === item.id ? "tl-insight-active" : ""}
                          onClick={() => setTab(item.id)}
                        >
                          {item.label}
                          {item.id === "market" && (
                            <span className="tl-small-dot" />
                          )}
                        </button>
                      ))}
                    </div>
                    <span className="tl-analysis-label">
                      <Icon name="layers" size={14} /> THE DETAILS BEHIND THE
                      NUMBERS
                    </span>
                  </div>
                  <section
                    className="tl-insight-content"
                    role="tabpanel"
                    id={`live-panel-${tab}`}
                    aria-labelledby={`live-tab-${tab}`}
                    tabIndex={0}
                  >
                    {tab === "market" ? (
                      <Betting
                        key={`${competition}|${selected?.fixture_id}`}
                        prediction={prediction} home={home} away={away} market={market}
                        resultView={renderMarket()} generate={() => void generate()} generating={generating}
                        canGenerate={Boolean(selected?.hypothetical || (selected && isUpcoming(selected)))}
                      />
                    ) : prediction ? (
                      renderAnalysis()
                    ) : (
                      <div className="tl-panel tl-empty-panel">
                        Generate this match's forecast to see its form, team
                        strength, H2H context, and scoreline estimates.
                      </div>
                    )}
                  </section>
                </>
              ) : (
                !fixturesLoading && (
                  <div className="tl-panel tl-empty-panel">
                    <h3>Your next match starts here.</h3>
                    <p>
                      Select a fixture or explore two teams to generate a
                      forecast.
                    </p>
                    <button
                      className="tl-outline-button"
                      onClick={openExplorer}
                    >
                      Explore a matchup <Icon name="arrow" size={17} />
                    </button>
                  </div>
                )
              )}
              <section className="tl-closing-note">
                <span className="tl-closing-star">✳</span>
                <div>
                  <strong>More insight. Less guesswork.</strong>
                  <p>
                    Probabilities show the possibilities. The match always has
                    the final word.
                  </p>
                </div>
                <button
                  className="tl-text-button"
                  onClick={() => navigate("studio")}
                >
                  Inside the model <Icon name="arrow" size={17} />
                </button>
              </section>
            </>
          )}
          {page === "teams" && renderTeams()}
          {page === "scorecard" && renderJournal()}
          {page === "studio" && renderStudio()}
        </main>
        <footer className="tl-footer">
          <span>
            MATCH FORECAST <i>/</i> TOUCHLINE EDITION
          </span>
          <span>Designed for the beautiful game. ◉</span>
          <a
            href="https://github.com/aristostheo/football-prediction-engine"
            target="_blank"
            rel="noreferrer"
          >
            Project on GitHub <Icon name="external" size={12} />
          </a>
        </footer>
      </div>
      <dialog
        ref={dialog}
        className="tl-explore-dialog"
        onCancel={() => setExploreOpen(false)}
        onClose={() => setExploreOpen(false)}
      >
        <div className="tl-panel-heading">
          <span className="tl-kicker">THE MATCHUP EXPLORER</span>
          <button
            className="tl-icon-button"
            aria-label="Close matchup explorer"
            onClick={() => setExploreOpen(false)}
          >
            <Icon name="close" />
          </button>
        </div>
        <h2>
          What if they <em>played?</em>
        </h2>
        <p>
          Explore any two registered teams. Hypothetical matches are not saved
          in your journal.
        </p>
        <form onSubmit={explore}>
          <label>
            Competition
            <select
              value={exploreLeague}
              onChange={(e) => {
                setExploreLeague(e.target.value as Competition);
                setExploreHome("");
                setExploreAway("");
                setExploreError("");
              }}
            >
              {leagues.map((l) => (
                <option value={l.id} key={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Home team
            <input
              list="live-home-teams"
              value={exploreHome}
              onChange={(e) => setExploreHome(e.target.value)}
              required
              placeholder="Search teams"
              autoComplete="off"
            />
          </label>
          <datalist id="live-home-teams">
            {(teams[exploreLeague] ?? [])
              .filter((t) => t !== exploreAway)
              .map((t) => (
                <option value={t} key={t} />
              ))}
          </datalist>
          <button
            className="tl-explore-swap"
            type="button"
            aria-label="Swap home and away teams"
            onClick={() => {
              setExploreHome(exploreAway);
              setExploreAway(exploreHome);
            }}
          >
            <Icon name="swap" />
          </button>
          <label>
            Away team
            <input
              list="live-away-teams"
              value={exploreAway}
              onChange={(e) => setExploreAway(e.target.value)}
              required
              placeholder="Search teams"
              autoComplete="off"
            />
          </label>
          <datalist id="live-away-teams">
            {(teams[exploreLeague] ?? [])
              .filter((t) => t !== exploreHome)
              .map((t) => (
                <option value={t} key={t} />
              ))}
          </datalist>
          {exploreError && (
            <p className="tl-error" role="alert">
              {exploreError}
            </p>
          )}
          <button className="tl-orange-button" type="submit">
            Explore matchup <Icon name="arrow" size={17} />
          </button>
        </form>
      </dialog>
      {toast && (
        <div className="tl-toast" role="status">
          <Icon name="check" size={17} />
          {toast}
          <button
            aria-label="Dismiss notification"
            onClick={() => setToast("")}
          >
            <Icon name="close" size={15} />
          </button>
        </div>
      )}
    </div>
  );

  function renderMarket() {
    return (
      <div className="tl-market-layout">
        <article className="tl-panel">
          <div className="tl-panel-heading">
            <h3>Model meets market.</h3>
            <span className="tl-chip">INDEPENDENT VIEWS</span>
          </div>
          <p className="tl-panel-copy">
            Compare model probabilities with the bookmaker market, after
            removing margin.
          </p>
          <div className="tl-market-legend">
            <span>
              <i className="tl-outcome-0" />
              Model
            </span>
            <span>
              <i className="tl-market-color" />
              Margin-free market
            </span>
          </div>
          {[teamShort(home), "Draw", teamShort(away)].map((name, i) => (
            <div className="tl-market-row" key={i}>
              <div className="tl-market-row-label">
                <strong>{name}</strong>
                <small className="tl-bet-result-fair">Model fair odds {p ? (1 / p[i]).toFixed(2) : "—"}</small>
                <span>
                  {p && market
                    ? `${(p[i] - market[i]) * 100 >= 0 ? "+" : ""}${((p[i] - market[i]) * 100).toFixed(1)} pp`
                    : "—"}
                </span>
              </div>
              <div className="tl-comparison-line">
                <span>Model</span>
                <div>
                  <i style={{ width: p ? pct(p[i]) : "0%" }} />
                </div>
                <strong>{p ? pct(p[i]) : "—"}</strong>
              </div>
              <div className="tl-comparison-line tl-comparison-market">
                <span>Market</span>
                <div>
                  <i style={{ width: market ? pct(market[i]) : "0%" }} />
                </div>
                <strong>{market ? pct(market[i]) : "—"}</strong>
              </div>
            </div>
          ))}
          <small className="tl-context-note">
            A difference is measured in percentage points, not a guaranteed
            betting edge. Loading odds does not change the independent model
            forecast.
          </small>
        </article>
        <article className="tl-panel tl-odds-panel">
          <div className="tl-kicker">A SECOND POINT OF VIEW</div>
          <h3>Add the market.</h3>
          <p>
            Load live odds for the selected scheduled match, or enter three
            decimal prices.
          </p>
          <button
            className="tl-dark-button"
            onClick={() => void loadOdds()}
            disabled={
              oddsLoading ||
              !selected ||
              selected.hypothetical ||
              !isUpcoming(selected)
            }
          >
            <Icon name="download" size={17} />
            {oddsLoading ? "Loading odds…" : "Load live market odds"}
          </button>
          {selected?.hypothetical && (
            <small>Live odds are available for scheduled matches only.</small>
          )}
          {marketNote && <p className="tl-market-note">{marketNote}</p>}
          <form onSubmit={compareOdds}>
            <div className="tl-odds-inputs">
              {["Home", "Draw", "Away"].map((label, i) => (
                <label key={label}>
                  {label}
                  <input
                    type="number"
                    min={marketSnapshot ? "1" : "1.000001"}
                    step="any"
                    value={prices[i]}
                    onChange={(e) => {
                      oddsRequest.current++;
                      setOddsLoading(false);
                      setPrices((current) =>
                        current.map((v, j) => (i === j ? e.target.value : v)),
                      );
                      setMarket(null);
                      setMarketNote("");
                      setMarketSnapshot(undefined);
                    }}
                    required
                  />
                </label>
              ))}
            </div>
            {marketError && (
              <p className="tl-error" role="alert">
                {marketError}
              </p>
            )}
            <button className="tl-dark-button" type="submit">
              {market ? "Update comparison" : "Compare odds"}
              <Icon name="arrow" size={18} />
            </button>
          </form>
          <small>
            Quotes are requested on demand and cached by the server. The model
            works without odds.
          </small>
        </article>
      </div>
    );
  }
  function renderAnalysis() {
    const context = prediction!.context;
    return (
      <div className="tl-detail-grid">
        <article className="tl-panel">
          {tab === "overview" && (
            <>
              <div className="tl-panel-heading">
                <h3>What shapes the forecast</h3>
                <span className="tl-number-tag">01 — 03</span>
              </div>
              <p className="tl-panel-copy">
                The actual inputs and component probabilities behind this
                estimate.
              </p>
              <div className="tl-story-row">
                <span className="tl-story-number">01</span>
                <div>
                  <strong>Strength over time</strong>
                  <p>
                    {teamShort(
                      context.home_elo >= context.away_elo ? home : away,
                    )}{" "}
                    has the higher pre-match Elo rating.
                  </p>
                </div>
                <span className="tl-story-stat">
                  {Math.abs(context.home_elo - context.away_elo).toFixed(0)}
                  <small>ELO GAP</small>
                </span>
              </div>
              <div className="tl-story-row">
                <span className="tl-story-number">02</span>
                <div>
                  <strong>The recent picture</strong>
                  <p>
                    {teamShort(home)}:{" "}
                    {context.home_form_matches
                      ? context.home_form_points_per_match.toFixed(2)
                      : "—"}{" "}
                    points per match across {context.home_form_matches} recent
                    games.
                  </p>
                </div>
                <span className="tl-story-stat">
                  {context.home_form_matches}
                  <small>MATCHES</small>
                </span>
              </div>
              <div className="tl-story-row">
                <span className="tl-story-number">03</span>
                <div>
                  <strong>Home ground matters</strong>
                  <p>
                    Home advantage is included in the Elo comparison. Venue form
                    is shown as context.
                  </p>
                </div>
                <span className="tl-story-stat">
                  <Icon name="pin" size={23} />
                  <small>HOME</small>
                </span>
              </div>
              <div className="tl-live-components">
                <strong>How the 1X2 forecast is assembled</strong>
                {componentRow("Elo", prediction!.components.elo_probabilities)}
                {prediction!.components.goal_probabilities &&
                  componentRow(
                    "Goal model",
                    prediction!.components.goal_probabilities,
                  )}
                {componentRow("Final model", modelProbabilities(prediction!))}
                <p>
                  {competition === "premier_league"
                    ? "25% Elo + 75% Poisson goal model."
                    : "Elo supplies the 1X2 probabilities; scoreline estimates use a separate goal model."}
                  {prediction!.components.base_model_weight < 1
                    ? " A promoted-team prior reduces confidence for a club without historical results."
                    : ""}
                </p>
              </div>
              <small className="tl-context-note">
                Form and H2H are context, not an exact attribution of
                probability changes. H2H does not change the production 1X2
                forecast.
              </small>
            </>
          )}
          {tab === "form" && (
            <>
              <div className="tl-panel-heading">
                <h3>The form guide</h3>
                <span className="tl-chip">UP TO LAST 5</span>
              </div>
              <p className="tl-panel-copy">
                Recorded league results before this matchup, oldest to newest.
              </p>
              <div className="tl-form-comparison">
                {[home, away].map((name, i) => {
                  const prefix = i === 0 ? "home" : "away";
                  const count = context[`${prefix}_form_matches`];
                  return (
                    <div key={name}>
                      <span className="tl-form-team">
                        {club(name)}
                        <strong>{teamShort(name)}</strong>
                      </span>
                      <FormPills
                        name={name}
                        results={context[`${prefix}_form_results`] ?? []}
                      />
                      {[
                        ["Recorded matches", count],
                        [
                          "Points per match",
                          count
                            ? context[
                                `${prefix}_form_points_per_match`
                              ].toFixed(2)
                            : "—",
                        ],
                        [
                          "Goals scored / match",
                          count
                            ? context[
                                `${prefix}_form_goals_for_per_match`
                              ].toFixed(2)
                            : "—",
                        ],
                        [
                          "Goals conceded / match",
                          count
                            ? context[
                                `${prefix}_form_goals_against_per_match`
                              ].toFixed(2)
                            : "—",
                        ],
                        ["Elo rating", context[`${prefix}_elo`].toFixed(0)],
                        [
                          i === 0
                            ? "Home points / match"
                            : "Away points / match",
                          context[`${prefix}_venue_points_per_match`].toFixed(
                            2,
                          ),
                        ],
                      ].map(([label, value]) => (
                        <div className="tl-form-stat" key={label}>
                          <span>{label}</span>
                          <strong>{value}</strong>
                        </div>
                      ))}
                    </div>
                  );
                })}
              </div>
              <small className="tl-context-note">
                Missing or long-gap history may leave fewer than five matches.
                Injuries, lineups, weather, and xG are not inputs to this model.
              </small>
            </>
          )}
          {tab === "h2h" && (
            <>
              <div className="tl-panel-heading">
                <h3>The shared history</h3>
                <span className="tl-chip">
                  {context.head_to_head_matches} MEETINGS
                </span>
              </div>
              <p className="tl-panel-copy">
                Recent recorded meetings, aligned to the selected home and away
                clubs.
              </p>
              <div className="tl-h2h-summary">
                <span>
                  <strong>{context.head_to_head_home_wins}</strong>
                  {teamShort(home)} wins
                </span>
                <span>
                  <strong>{context.head_to_head_draws}</strong>Draws
                </span>
                <span>
                  <strong>{context.head_to_head_away_wins}</strong>
                  {teamShort(away)} wins
                </span>
              </div>
              <div className="tl-live-h2h">
                {context.head_to_head_recent.length ? (
                  context.head_to_head_recent.map((meeting, i) => (
                    <p key={i}>{meeting}</p>
                  ))
                ) : (
                  <p>
                    No recent head-to-head results available in the local
                    history.
                  </p>
                )}
              </div>
              <small className="tl-context-note">
                H2H is contextual and does not alter production probabilities.
                Venue orientation is preserved in each recorded meeting.
              </small>
            </>
          )}
        </article>
        {renderScorelines()}
      </div>
    );
  }
  function componentRow(label: string, values: [number, number, number]) {
    return (
      <div className="tl-component-row">
        <span>{label}</span>
        {values.map((v, i) => (
          <span key={i}>
            {["H", "D", "A"][i]} {pct(v)}
          </span>
        ))}
      </div>
    );
  }
  function renderScorelines() {
    const matrix = scoreMatrix(prediction!),
      scores = prediction!.components.top_scorelines;
    return (
      <article className="tl-panel tl-scorelines">
        <div className="tl-panel-heading">
          <h3>A game in goals</h3>
          <span className="tl-chip">SCORELINE EXPLORER</span>
        </div>
        <div className="tl-scoreline-tabs">
          <button
            className={scoreView === "scores" ? "tl-score-view-active" : ""}
            onClick={() => setScoreView("scores")}
          >
            Likely scores
          </button>
          <button
            className={scoreView === "map" ? "tl-score-view-active" : ""}
            onClick={() => setScoreView("map")}
            disabled={!matrix}
          >
            Goal map <Icon name="grid" size={12} />
          </button>
        </div>
        {scoreView === "scores" || !matrix ? (
          <div className="tl-scoreline-list">
            {scores.map((score, i) => (
              <div
                className={`tl-scoreline-row ${i === 0 ? "tl-scoreline-first" : ""}`}
                key={`${score.home_goals}-${score.away_goals}`}
              >
                <span className="tl-scoreline-order">0{i + 1}</span>
                <strong>
                  {score.home_goals}
                  <i>—</i>
                  {score.away_goals}
                </strong>
                <div>
                  <i
                    style={{
                      width: `${(score.probability / scores[0].probability) * 100}%`,
                    }}
                  />
                </div>
                <span>{pct(score.probability)}</span>
              </div>
            ))}
            {!scores.length && <p>Scoreline estimates are not available.</p>}
          </div>
        ) : (
          <div className="tl-goal-map">
            <span className="tl-map-direction">
              Home goals → · Away goals ↓
            </span>
            <div className="tl-map-grid">
              <span />
              {[0, 1, 2, 3, 4].map((n) => (
                <span className="tl-map-axis" key={n}>
                  {n}
                </span>
              ))}
              {[0, 1, 2, 3, 4].map((a) => (
                <div className="tl-map-row" key={a}>
                  <span className="tl-map-axis">{a}</span>
                  {[0, 1, 2, 3, 4].map((h) => {
                    const v = matrix.probability(h, a);
                    return (
                      <span
                        className="tl-map-cell"
                        key={h}
                        style={
                          { "--cell-opacity": 0.08 + v * 5 } as CSSProperties
                        }
                        title={`${home} ${h}–${a} ${away}: ${pct(v)}`}
                      >
                        {(v * 100).toFixed(1)}
                        <small>%</small>
                      </span>
                    );
                  })}
                </div>
              ))}
            </div>
            <small>
              The map shows 0–4 goals; higher-score probability remains in the
              full distribution.
            </small>
          </div>
        )}
        {matrix && (
          <div className="tl-goal-rates">
            <span>
              <small>HOME GOAL ESTIMATE</small>
              <strong>{matrix.homeRate.toFixed(2)}</strong>
            </span>
            <div className="tl-goal-rates-divider" />
            <span>
              <small>AWAY GOAL ESTIMATE</small>
              <strong>{matrix.awayRate.toFixed(2)}</strong>
            </span>
          </div>
        )}
        <small className="tl-context-note">
          Independent Poisson score estimates. These are goal-model rates, not
          observed xG. The likeliest exact score is only one possibility; 1X2
          may also include Elo.
        </small>
      </article>
    );
  }
  function renderTeams() {
    return (
      <>
        <section className="tl-page-heading">
          <div>
            <div className="tl-kicker">
              <span />
              YOUR SIDE OF THE GAME
            </div>
            <h1>
              Keep them <em>close.</em>
            </h1>
            <p>Follow your clubs. Their matchday fixtures rise to the top.</p>
          </div>
          <span className="tl-count-label">
            {favoriteCount} followed across all leagues
          </span>
        </section>
        <div className="tl-section-title">
          <h2>Coming up for you</h2>
          <span>{activeLeague.name}</span>
        </div>
        <div className="tl-follow-fixtures">
          {fixtures
            .filter(
              (f) =>
                isUpcoming(f) &&
                (followed.includes(f.home_team) ||
                  followed.includes(f.away_team)),
            )
            .map((f) => (
              <button
                className="tl-panel"
                key={f.fixture_id}
                onClick={() => chooseFixture(f)}
              >
                <span className="tl-mini-label">
                  {dateLabel(localDate(f.kickoff_at), true)} ·{" "}
                  {timeLabel(f.kickoff_at)}
                </span>
                <span className="tl-follow-fixture-teams">
                  {club(f.home_team, competition, f.home_badge_url)}
                  {teamShort(f.home_team)}
                  <small>vs</small>
                  {club(f.away_team, competition, f.away_badge_url)}
                  {teamShort(f.away_team)}
                </span>
                <span className="tl-text-button">
                  Open forecast <Icon name="arrow" size={16} />
                </span>
              </button>
            ))}
        </div>
        {!fixtures.some(
          (f) =>
            isUpcoming(f) &&
            (followed.includes(f.home_team) || followed.includes(f.away_team)),
        ) && (
          <div className="tl-panel tl-empty-panel">
            No followed clubs in the loaded matchday. Choose another date in
            Match center, or follow a club below.
            <button
              className="tl-text-button"
              onClick={() => navigate("center")}
            >
              Browse matches <Icon name="arrow" size={15} />
            </button>
          </div>
        )}
        <div className="tl-section-title">
          <h2>{activeLeague.name} clubs</h2>
          <label className="tl-search">
            <Icon name="search" size={17} />
            <input
              placeholder="Find a club…"
              aria-label="Search clubs"
              value={teamQuery}
              onChange={(e) => setTeamQuery(e.target.value)}
            />
          </label>
        </div>
        {teamsError && (
          <p className="tl-error" role="alert">
            {teamsError}
          </p>
        )}
        {badgeNotice && <p className="tl-page-footnote">{badgeNotice}</p>}
        <div className="tl-club-grid">
          {catalog
            .filter((t) =>
              t.toLocaleLowerCase().includes(teamQuery.toLocaleLowerCase()),
            )
            .map((name) => (
              <article className="tl-team-card" key={name}>
                {club(name)}
                <div>
                  <strong>{teamShort(name)}</strong>
                  <small>
                    {followed.includes(name) ? "Following · " : ""}
                    {activeLeague.name}
                  </small>
                </div>
                <button
                  className={`tl-icon-button ${followed.includes(name) ? "tl-favorited" : ""}`}
                  aria-label={`${followed.includes(name) ? "Unfollow" : "Follow"} ${name}`}
                  onClick={() => toggleFavorite(name)}
                >
                  <Icon
                    name="star"
                    size={18}
                    filled={followed.includes(name)}
                  />
                </button>
              </article>
            ))}
        </div>
        {!catalog.length && !teamsError && (
          <p className="tl-empty-panel">Loading club catalogue…</p>
        )}
        <p className="tl-page-footnote">
          Switch leagues in the sidebar to find more clubs. The catalogue
          includes registered historical teams. Favourites are saved in this
          browser; they do not sync between devices.
        </p>
      </>
    );
  }
  function renderJournal() {
    return (
      <>
        <section className="tl-page-heading">
          <div>
            <div className="tl-kicker">
              <span />
              KEEP THE MODEL HONEST
            </div>
            <h1>
              The long <em>game.</em>
            </h1>
            <p>
              The prediction before kickoff. The result after the final whistle.
            </p>
          </div>
          <div className="tl-journal-actions">
            <button
              className="tl-outline-button"
              onClick={() => void checkResults()}
              disabled={resultsLoading || !records.length}
            >
              <Icon name="check" size={17} />
              {resultsLoading ? "Checking results…" : "Check results"}
            </button>
            <button
              className="tl-outline-button"
              onClick={exportJournal}
              disabled={!filteredRecords.length}
            >
              <Icon name="download" size={17} />
              Export CSV
            </button>
          </div>
        </section>
        <div className="tl-scorecard-metrics">
          <article>
            <span>FORECASTS TRACKED</span>
            <strong>{metricRecords.length}</strong>
            <small>
              {metricRecords.filter((r) => !results[r.id]).length} awaiting a
              final result
            </small>
          </article>
          <article>
            <span>SETTLED FORECASTS</span>
            <strong>{metrics?.count ?? 0}</strong>
            <small>Results confirmed by history or provider</small>
          </article>
          <article>
            <span>LOG LOSS</span>
            <strong>{metrics ? metrics.logLoss.toFixed(3) : "—"}</strong>
            <small>Lower is better</small>
          </article>
          <article>
            <span>TOP PICK ACCURACY</span>
            <strong>{metrics ? pct(metrics.accuracy) : "—"}</strong>
            <small>Secondary to probability quality</small>
          </article>
        </div>
        {resultsError && (
          <p className="tl-error" role="alert">
            {resultsError} Previously checked results remain visible.
          </p>
        )}
        <div className="tl-panel tl-scorecard-table">
          <div className="tl-panel-heading">
            <h3>Your forecast journal</h3>
            <div className="tl-journal-filters">
              <select
                aria-label="Journal league"
                value={journalLeague}
                onChange={(e) =>
                  setJournalLeague(e.target.value as Competition | "all")
                }
              >
                <option value="all">All leagues</option>
                {leagues.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
              </select>
              <div className="tl-segmented">
                {["all", "settled", "pending"].map((filter) => (
                  <button
                    className={
                      recordFilter === filter ? "tl-segment-active" : ""
                    }
                    key={filter}
                    onClick={() => setRecordFilter(filter)}
                  >
                    {filter}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="tl-table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Match</th>
                  <th>Model prediction</th>
                  <th>Actual result</th>
                  <th>Review</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {filteredRecords.map((record) => {
                  const s = settlements[record.id],
                    actual = s?.result ?? null,
                    pick = record.model_probabilities.indexOf(
                      Math.max(...record.model_probabilities),
                    );
                  const correct = actual
                    ? ["H", "D", "A"][pick] === actual
                    : null;
                  const exact =
                    actual &&
                    record.predicted_scoreline &&
                    s?.home_goals != null &&
                    s.away_goals != null
                      ? record.predicted_scoreline.home_goals ===
                          s.home_goals &&
                        record.predicted_scoreline.away_goals === s.away_goals
                      : null;
                  const names = [
                    teamShort(record.home_team),
                    "Draw",
                    teamShort(record.away_team),
                  ];
                  return (
                    <tr key={record.id}>
                      <td>
                        <span className="tl-table-clubs">
                          {club(record.home_team, record.competition)}
                          <strong>{teamShort(record.home_team)}</strong>
                          <small>vs</small>
                          {club(record.away_team, record.competition)}
                          <strong>{teamShort(record.away_team)}</strong>
                        </span>
                        <small className="tl-table-date">
                          {leagueName(record.competition)} ·{" "}
                          {dateLabel(localDate(record.kickoff_at), true)}{" "}
                          {timeLabel(record.kickoff_at)}
                        </small>
                        <small className="tl-table-date">
                          Saved{" "}
                          {new Date(record.forecasted_at).toLocaleString()}
                        </small>
                      </td>
                      <td className="tl-journal-prediction">
                        <strong>
                          {names[pick]} ·{" "}
                          {pct(record.model_probabilities[pick])}
                        </strong>
                        <small>
                          H {pct(record.model_probabilities[0])} · D{" "}
                          {pct(record.model_probabilities[1])} · A{" "}
                          {pct(record.model_probabilities[2])}
                        </small>
                        <span>
                          Likely score:{" "}
                          {record.predicted_scoreline
                            ? `${record.predicted_scoreline.home_goals}–${record.predicted_scoreline.away_goals} (${pct(record.predicted_scoreline.probability)})`
                            : "not saved in this older forecast"}
                        </span>
                        {record.market_probabilities && (
                          <small>
                            Market: H {pct(record.market_probabilities[0])} · D{" "}
                            {pct(record.market_probabilities[1])} · A{" "}
                            {pct(record.market_probabilities[2])}
                          </small>
                        )}
                      </td>
                      <td>
                        <span
                          className={`tl-status ${!actual ? "tl-pending" : ""}`}
                        >
                          {actual
                            ? actual === "H"
                              ? `${teamShort(record.home_team)} win`
                              : actual === "A"
                                ? `${teamShort(record.away_team)} win`
                                : "Draw"
                            : Date.parse(record.kickoff_at) > Date.now()
                              ? "Upcoming"
                              : s?.check_status === "deferred"
                                ? "Queued for a later check"
                                : s?.check_status === "unavailable"
                                  ? "Result provider unavailable"
                                  : "Awaiting final result"}
                        </span>
                        {s?.home_goals != null && s.away_goals != null && (
                          <strong className="tl-journal-score">
                            {s.home_goals}–{s.away_goals}
                            <small>REGULATION TIME</small>
                          </strong>
                        )}
                        {actual && s?.home_goals == null && (
                          <small className="tl-table-date">
                            Outcome confirmed; score unavailable
                          </small>
                        )}
                      </td>
                      <td>
                        {actual ? (
                          <>
                            <span
                              className={`tl-review ${correct ? "tl-review-correct" : "tl-review-miss"}`}
                            >
                              {correct ? "Top pick correct" : "Top pick missed"}
                            </span>
                            {exact !== null && (
                              <small className="tl-table-date">
                                {exact
                                  ? "Exact score matched"
                                  : "Exact score differed"}
                              </small>
                            )}
                            <small className="tl-table-date">
                              {s?.source === "live_provider"
                                ? "Live provider"
                                : s?.source === "bundled_history"
                                  ? "Local match history"
                                  : "Confirmed result"}
                            </small>
                          </>
                        ) : (
                          <span className="tl-table-date">
                            Checked after completion
                          </span>
                        )}
                      </td>
                      <td>
                        <button
                          className="tl-icon-button"
                          aria-label={`Delete forecast ${record.home_team} vs ${record.away_team}`}
                          onClick={() => {
                            if (
                              window.confirm(
                                "Delete this saved forecast from your journal?",
                              )
                            )
                              setRecords(
                                removeForecast(record.id, recordsRef.current),
                              );
                          }}
                        >
                          <Icon name="close" size={16} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {!filteredRecords.length && (
            <div className="tl-empty-panel">
              <h3>
                {records.length
                  ? "No forecasts in this view."
                  : "Your first forecast starts the journal."}
              </h3>
              <p>
                Generate an upcoming scheduled match forecast. It is saved
                automatically before kickoff.
              </p>
              <button
                className="tl-text-button"
                onClick={() => navigate("center")}
              >
                Find a match <Icon name="arrow" size={15} />
              </button>
            </div>
          )}
        </div>
        <p className="tl-page-footnote">
          {resultCheckedAt
            ? `Last checked ${timeLabel(resultCheckedAt)}. `
            : ""}
          Results refresh every five minutes while this journal is open. Older
          journals may need several checks to finish updating. An
          unfinished, postponed, missing, or unavailable result stays pending.
          Saved model probabilities are never regenerated to match the outcome.
        </p>
        <div className="tl-scorecard-bottom">
          <article className="tl-panel">
            <h3>Probability, with perspective.</h3>
            <p>
              A 60% forecast should succeed about six times in ten over a large
              sample. Small samples move around; a correct top pick does not
              validate a model on its own.
            </p>
            {metrics && (
              <div className="tl-live-metrics">
                <span>
                  Brier <strong>{metrics.brier.toFixed(3)}</strong>
                </span>
                <span>
                  RPS{" "}
                  <strong>{metrics.rankedProbabilityScore.toFixed(3)}</strong>
                </span>
                <span>
                  Calibration gap{" "}
                  <strong>{pct(metrics.calibrationError)}</strong>
                </span>
              </div>
            )}
            <button
              className="tl-text-button"
              onClick={() => navigate("studio")}
            >
              Explore the methodology <Icon name="arrow" size={17} />
            </button>
          </article>
          <article className="tl-panel">
            <h3>Model vs market</h3>
            <p>Compared on the same settled matches with saved odds.</p>
            {marketMetrics && matchedModelMetrics ? (
              <div className="tl-live-metrics">
                <span>
                  Matched games <strong>{marketMetrics.count}</strong>
                </span>
                <span>
                  Model log loss{" "}
                  <strong>{matchedModelMetrics.logLoss.toFixed(3)}</strong>
                </span>
                <span>
                  Market log loss{" "}
                  <strong>{marketMetrics.logLoss.toFixed(3)}</strong>
                </span>
              </div>
            ) : (
              <p>
                Add market odds before kickoff to build a matched comparison.
              </p>
            )}
          </article>
        </div>
        {!!calibration.length && (
          <article className="tl-panel tl-calibration">
            <h3>Does confidence match reality?</h3>
            <p>Top-pick confidence buckets across settled journal forecasts.</p>
            <div className="tl-table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Confidence</th>
                    <th>Matches</th>
                    <th>Mean predicted</th>
                    <th>Observed wins</th>
                  </tr>
                </thead>
                <tbody>
                  {calibration.map((b) => (
                    <tr key={b.label}>
                      <td>{b.label}</td>
                      <td>{b.count}</td>
                      <td>{pct(b.meanConfidence)}</td>
                      <td>{pct(b.observedAccuracy)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        )}
        <p className="tl-page-footnote">
          Forecasts and results are stored in this browser. Hypothetical matches
          are excluded. Historical research remains the stronger evaluation
          until many prospective forecasts have settled.
        </p>
      </>
    );
  }
  function renderStudio() {
    return (
      <>
        <section className="tl-page-heading">
          <div>
            <div className="tl-kicker">
              <span />
              INSIDE THE METHOD
            </div>
            <h1>
              Inside the <em>engine.</em>
            </h1>
            <p>
              Clear methods. Honest evaluation. Football intelligence you can
              inspect.
            </p>
          </div>
          <a
            className="tl-outline-button"
            href="https://github.com/aristostheo/football-prediction-engine"
            target="_blank"
            rel="noreferrer"
          >
            Explore the project <Icon name="external" size={17} />
          </a>
        </section>
        <article className="tl-studio-hero">
          <div>
            <span className="tl-mini-label">THE PRINCIPLE</span>
            <h2>
              Confidence is earned.
              <br />
              <em>Match by match.</em>
            </h2>
            <p>
              The engine gives home, draw, and away probabilities using only
              historical results available before the matchup. The journal lets
              real results test them.
            </p>
          </div>
          <div className="tl-studio-orbit">
            <span />
            <span />
            <span />
            <div>
              <Icon name="layers" size={42} />
              <small>
                FOOTBALL
                <br />
                INTELLIGENCE
              </small>
            </div>
          </div>
        </article>
        <div className="tl-studio-grid">
          {[
            {
              n: "01",
              icon: "chart" as IconName,
              title: "A longer view",
              text: "Elo starts at 1500, updates by match result with K=20, and includes a 60-point home advantage. Registered unseen clubs receive a conservative promoted-team prior.",
            },
            {
              n: "02",
              icon: "grid" as IconName,
              title: "A picture in goals",
              text: "Premier League 1X2 blends 25% Elo with 75% Poisson probabilities. Other leagues use Elo for 1X2. Separate Poisson goal models estimate likely scorelines across all leagues.",
            },
            {
              n: "03",
              icon: "layers" as IconName,
              title: "Context, clearly shown",
              text: "Recent form uses up to five recorded league games, equally weighted, with goals for/against and venue performance. H2H is displayed as context. Long history gaps reset form and shrink Elo.",
            },
            {
              n: "04",
              icon: "swap" as IconName,
              title: "A market perspective",
              text: "Live bookmaker consensus and manual decimal prices are converted into margin-free probabilities. They are compared with the independent model and do not change its probabilities.",
            },
          ].map((item) => (
            <article className="tl-panel" key={item.n}>
              <div className="tl-panel-heading">
                <Icon name={item.icon} size={24} />
                <span className="tl-number-tag">{item.n}</span>
              </div>
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
        <article className="tl-panel tl-method-note">
          <Icon name="clock" size={26} />
          <div>
            <h3>Always before kickoff.</h3>
            <p>
              Scheduled forecasts are rejected after kickoff. Their original
              probabilities, timestamp, policy, and likely score are saved for
              later comparison. The local results dataset must remain current;
              its cutoff appears on every forecast.
            </p>
          </div>
        </article>
        <details className="tl-panel tl-research">
          <summary>Historical benchmarks <span>Methods, results & limitations</span></summary>
          <h3>The evidence so far</h3>
          <p>
            Archived research snapshot from October 2, 2026, before later dataset
            corrections. These historical figures are not current live scores
            or guarantees for upcoming games.
          </p>
          <div className="tl-table-scroll">
            <table>
              <thead>
                <tr>
                  <th>League</th>
                  <th>Test games</th>
                  <th>Production log loss</th>
                  <th>Closing-market log loss</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Premier League</td>
                  <td>1,900</td>
                  <td>0.9741</td>
                  <td>0.9570</td>
                </tr>
                <tr>
                  <td>Greece</td>
                  <td>364 (market: 361)</td>
                  <td>1.0012</td>
                  <td>0.9252</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p>
            Lower log loss is better. Closing odds outperformed the independent
            model in this experiment. Greece's sample is small. The five added
            leagues use the Elo baseline and have separate evaluation reports.
          </p>
          <div className="tl-research-links">
            <a
              href="https://github.com/aristostheo/football-prediction-engine/blob/main/docs/probability-benchmark.md"
              target="_blank"
              rel="noreferrer"
            >
              Probability research <Icon name="external" size={14} />
            </a>
            <a
              href="https://github.com/aristostheo/football-prediction-engine/blob/main/docs/model-comparison.md"
              target="_blank"
              rel="noreferrer"
            >
              Evaluation & league coverage <Icon name="external" size={14} />
            </a>
          </div>
        </details>
        <p className="tl-page-footnote">
          The production predictor has no separate calibration transform.
          Injuries, lineups, weather, shots, and xG are not available inputs in
          this version. Scoreline estimates are independent Poisson, not
          Dixon–Coles.
        </p>
      </>
    );
  }
}
