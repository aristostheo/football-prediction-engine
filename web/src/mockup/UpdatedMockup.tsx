import { useEffect, useRef, useState } from "react";
import type { CSSProperties, FormEvent } from "react";
import {
  dayForDate,
  demoDate,
  demoFixtures,
  demoLeagues,
  demoTeams,
  formattedDate,
  initialDemoRecords,
  pct,
  points,
  sampleForecast,
  teamById,
} from "./demoData";
import type { DemoFixture, DemoRecord, DemoTeam, LeagueId } from "./demoData";
import "./mockup.css";

type IconName =
  | "grid"
  | "star"
  | "chart"
  | "layers"
  | "arrow"
  | "back"
  | "chevron"
  | "calendar"
  | "search"
  | "close"
  | "sun"
  | "moon"
  | "bookmark"
  | "check"
  | "clock"
  | "pin"
  | "bolt"
  | "swap"
  | "download"
  | "external"
  | "menu";
const iconPaths: Record<IconName, string> = {
  grid: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
  star: "m12 3 2.8 5.8 6.4.9-4.6 4.5 1.1 6.4-5.7-3-5.7 3 1.1-6.4L3 9.7l6.4-.9Z",
  chart: "M3 3v18h18M7 15l4-5 4 3 5-7",
  layers: "m12 3 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 16l9 5 9-5",
  arrow: "M4 12h16m-6-6 6 6-6 6",
  back: "M20 12H4m6-6-6 6 6 6",
  chevron: "m9 5 7 7-7 7",
  calendar:
    "M5 4h14a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2ZM7 2v4m10-4v4M3 10h18M7 14h2m4 0h4m-10 4h2",
  search: "M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z",
  close: "m6 6 12 12M18 6 6 18",
  sun: "M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z",
  moon: "M20.5 13.5A9 9 0 0 1 10.5 3a9 9 0 1 0 10 10.5Z",
  bookmark: "M6 3h12v18l-6-4-6 4V3Z",
  check: "m5 12 4 4L19 6",
  clock: "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM12 7v5l3 2",
  pin: "M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0ZM14 10a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z",
  bolt: "m13 2-9 12h7l-1 8 10-13h-7l0-7Z",
  swap: "M3 7h18m-4-4 4 4-4 4M21 17H3m4-4-4 4 4 4",
  download: "M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5",
  external: "M14 3h7v7m0-7L10 14M10 3H3v18h18v-7",
  menu: "M3 6h18M3 12h18M3 18h18",
};

function Icon({
  name,
  size = 20,
  filled = false,
}: {
  name: IconName;
  size?: number;
  filled?: boolean;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={iconPaths[name]} />
    </svg>
  );
}
function Club({ team, large = false }: { team: DemoTeam; large?: boolean }) {
  return (
    <span className={`tl-club ${large ? "tl-club-large" : ""}`}>
      <img
        src={`/mockup/${team.id}.png`}
        alt={`${team.name} badge`}
        width={large ? 112 : 32}
        height={large ? 112 : 32}
      />
    </span>
  );
}
function FormPills({ team }: { team: DemoTeam }) {
  return (
    <div
      className="tl-form-pills"
      aria-label={`${team.name} last five results, oldest first`}
    >
      {team.form.map((result, index) => (
        <span
          className={`tl-form-${result.toLowerCase()}`}
          key={index}
          title={result === "W" ? "Win" : result === "D" ? "Draw" : "Loss"}
        >
          {result}
        </span>
      ))}
    </div>
  );
}
function Brand() {
  return (
    <div className="tl-brand">
      <span className="tl-logo">
        <svg viewBox="0 0 32 32" fill="none" aria-hidden="true">
          <path d="M8 25V7h17M8 16h12" stroke="currentColor" strokeWidth="3" />
          <circle cx="22" cy="24" r="3" fill="currentColor" />
        </svg>
      </span>
      <div>
        <strong>
          match forecast<span>®</span>
        </strong>
        <small>THE TOUCHLINE EDITION</small>
      </div>
    </div>
  );
}
function StadiumCanvas() {
  return (
    <svg
      className="tl-stadium"
      viewBox="0 0 900 500"
      fill="none"
      aria-hidden="true"
    >
      <defs>
        <radialGradient id="tl-stadium-glow">
          <stop stopColor="#ed5d34" stopOpacity=".17" />
          <stop offset="1" stopColor="#ed5d34" stopOpacity="0" />
        </radialGradient>
      </defs>
      <ellipse
        cx="450"
        cy="290"
        rx="430"
        ry="270"
        fill="url(#tl-stadium-glow)"
      />
      {[0, 1, 2, 3, 4, 5, 6].map((i) => (
        <rect
          key={i}
          x={75 + i * 15}
          y={-65 + i * 20}
          width={750 - i * 30}
          height={610 - i * 40}
          rx={200 - i * 20}
          stroke="#e4e7d7"
          strokeOpacity={0.025 + i * 0.012}
        />
      ))}
      <g stroke="#e4e7d7" strokeOpacity=".1" transform="translate(215,100)">
        <rect width="470" height="275" rx="2" />
        <path d="M235 0v275M0 60h75v155H0m470-155h-75v155h75M0 100h27v75H0m470-75h-27v75h27" />
        <circle cx="235" cy="137.5" r="49" />
        <circle cx="235" cy="137.5" r="2" fill="#e4e7d7" />
      </g>
    </svg>
  );
}

type Page = "center" | "teams" | "scorecard" | "studio";
type InsightTab = "overview" | "market" | "form" | "h2h";
const pages: { id: Page; title: string; icon: IconName }[] = [
  { id: "center", title: "Match center", icon: "grid" },
  { id: "teams", title: "My teams", icon: "star" },
  { id: "scorecard", title: "Scorecard", icon: "chart" },
  { id: "studio", title: "Model studio", icon: "layers" },
];

export default function UpdatedMockup() {
  const [page, setPage] = useState<Page>("center");
  const [league, setLeague] = useState<LeagueId>("england");
  const [selected, setSelected] = useState<DemoFixture>(demoFixtures[0]);
  const [day, setDay] = useState(0);
  const [favorites, setFavorites] = useState([
    "arsenal",
    "liverpool",
    "olympiacos",
  ]);
  const [onlyFavorites, setOnlyFavorites] = useState(false);
  const [insight, setInsight] = useState<InsightTab>("overview");
  const [night, setNight] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [exploreOpen, setExploreOpen] = useState(false);
  const [exploreLeague, setExploreLeague] = useState<LeagueId>("england");
  const [exploreHome, setExploreHome] = useState("Arsenal");
  const [exploreAway, setExploreAway] = useState("Liverpool");
  const [exploreError, setExploreError] = useState("");
  const [toast, setToast] = useState("");
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState(false);
  const [records, setRecords] = useState<DemoRecord[]>(initialDemoRecords);
  const [recordFilter, setRecordFilter] = useState("all");
  const [teamQuery, setTeamQuery] = useState("");
  const [market, setMarket] = useState<[number, number, number] | null>(null);
  const [prices, setPrices] = useState(["1.90", "3.80", "4.25"]);
  const [marketError, setMarketError] = useState("");
  const [scoreView, setScoreView] = useState<"scores" | "map">("scores");
  const dialogRef = useRef<HTMLDialogElement>(null);
  const generationTimer = useRef<number | undefined>(undefined);
  const toastTimer = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (exploreOpen && !dialogRef.current?.open) dialogRef.current?.showModal();
    if (!exploreOpen && dialogRef.current?.open) dialogRef.current?.close();
  }, [exploreOpen]);
  useEffect(
    () => () => {
      window.clearTimeout(generationTimer.current);
      window.clearTimeout(toastTimer.current);
    },
    [],
  );
  useEffect(() => {
    const previous = document.title;
    document.title = "Touchline — Updated mockup | Match Forecast";
    return () => {
      document.title = previous;
    };
  }, []);

  const home = teamById[selected.home];
  const away = teamById[selected.away];
  const activeLeague = demoLeagues.find((item) => item.id === league)!;
  const forecast = sampleForecast(selected);
  const p = forecast.probabilities;
  const winner = p.indexOf(Math.max(...p));
  const selectedSaved = records.some(
    (record) => record.fixture.id === selected.id && record.result === null,
  );
  const visibleFixtures = demoFixtures
    .filter(
      (fixture) =>
        teamById[fixture.home].league === league &&
        fixture.day === day &&
        (!onlyFavorites ||
          favorites.includes(fixture.home) ||
          favorites.includes(fixture.away)),
    )
    .sort(
      (a, b) =>
        Number(favorites.includes(b.home) || favorites.includes(b.away)) -
        Number(favorites.includes(a.home) || favorites.includes(a.away)),
    );

  function notify(message: string) {
    setToast(message);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(""), 3600);
  }
  function navigate(next: Page) {
    setPage(next);
    setSidebarOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  function chooseFixture(fixture: DemoFixture) {
    window.clearTimeout(generationTimer.current);
    setGenerating(false);
    setSelected(fixture);
    setDay(fixture.day);
    setMarket(null);
    setMarketError("");
    setGenerated(false);
    setLeague(teamById[fixture.home].league);
    setPage("center");
    setInsight("overview");
  }
  function chooseLeague(next: LeagueId) {
    const fixture = demoFixtures.find(
      (item) => teamById[item.home].league === next,
    )!;
    chooseFixture(fixture);
    setDay(0);
    setOnlyFavorites(false);
    setSidebarOpen(false);
    const teams = demoTeams.filter((team) => team.league === next);
    setExploreHome(teams[0].name);
    setExploreAway(teams[1].name);
    setExploreLeague(next);
  }
  function toggleFavorite(id: string) {
    setFavorites((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id],
    );
  }
  function generate() {
    setGenerating(true);
    window.clearTimeout(generationTimer.current);
    generationTimer.current = window.setTimeout(() => {
      setGenerating(false);
      setGenerated(true);
      notify("Demo forecast generated. No live data requested.");
    }, 650);
  }
  function save() {
    if (selected.hypothetical) return;
    setRecords((current) =>
      current.some(
        (record) => record.fixture.id === selected.id && record.result === null,
      )
        ? current.filter(
            (record) =>
              record.fixture.id !== selected.id || record.result !== null,
          )
        : [
            {
              id: `saved-${selected.id}`,
              fixture: selected,
              probabilities: p,
              result: null,
            },
            ...current,
          ],
    );
    notify(
      selectedSaved
        ? "Demo forecast removed from your scorecard."
        : "Demo forecast saved to your scorecard.",
    );
  }
  function explore(event: FormEvent) {
    event.preventDefault();
    const teams = demoTeams.filter((team) => team.league === exploreLeague);
    const h = teams.find(
      (team) => team.name.toLowerCase() === exploreHome.trim().toLowerCase(),
    );
    const a = teams.find(
      (team) => team.name.toLowerCase() === exploreAway.trim().toLowerCase(),
    );
    if (!h || !a || h.id === a.id) {
      setExploreError("Choose two different clubs from the team list.");
      return;
    }
    chooseFixture({
      id: `explore-${h.id}-${a.id}`,
      home: h.id,
      away: a.id,
      day: 0,
      time: "",
      venue: "A hypothetical matchup",
      hypothetical: true,
    });
    setExploreOpen(false);
    setExploreError("");
    notify("Your hypothetical matchup is ready to explore.");
  }
  function compareOdds(event?: FormEvent) {
    event?.preventDefault();
    const values = prices.map(Number);
    if (values.some((value) => !Number.isFinite(value) || value <= 1)) {
      setMarketError("Enter three decimal odds greater than 1.");
      return;
    }
    const raw = values.map((value) => 1 / value);
    const total = raw.reduce((a, b) => a + b, 0);
    setMarket(raw.map((value) => value / total) as [number, number, number]);
    setMarketError("");
    notify("Example odds compared with the model. Bookmaker margin removed.");
  }
  function exportScorecard() {
    const csv =
      "Example forecasts — demo data only\nHome,Away,Home probability,Draw probability,Away probability,Result\n" +
      records
        .map((record) =>
          [
            teamById[record.fixture.home].name,
            teamById[record.fixture.away].name,
            ...record.probabilities.map((value) => value.toFixed(4)),
            record.result === null
              ? "Pending"
              : ["Home", "Draw", "Away"][record.result],
          ].join(","),
        )
        .join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "touchline-demo-scorecard.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className={`tl-app ${night ? "tl-night" : ""}`}>
      {sidebarOpen && (
        <button
          className="tl-sidebar-overlay"
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <aside className={`tl-sidebar ${sidebarOpen ? "tl-sidebar-open" : ""}`}>
        <Brand />
        <div className="tl-sidebar-label">YOUR WORKSPACE</div>
        <nav aria-label="Preview navigation">
          {pages.map((item) => (
            <button
              className={page === item.id ? "tl-nav-active" : ""}
              key={item.id}
              onClick={() => navigate(item.id)}
            >
              <Icon name={item.icon} />
              <span>{item.title}</span>
              {item.id === "teams" && <small>{favorites.length}</small>}
              {item.id === "center" && <i />}
            </button>
          ))}
        </nav>
        <div className="tl-sidebar-label tl-leagues-label">
          THE COMPETITIONS <span>07</span>
        </div>
        <div className="tl-league-list">
          {demoLeagues.map((item) => (
            <button
              key={item.id}
              className={league === item.id ? "tl-league-active" : ""}
              onClick={() => chooseLeague(item.id)}
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
              {league === item.id && <Icon name="chevron" size={14} />}
            </button>
          ))}
        </div>
        <div className="tl-sidebar-bottom">
          <div className="tl-edition-mark">
            A new perspective.
            <br />
            <span>The same love for football.</span>
          </div>
          <a href="/">
            <Icon name="back" size={16} /> Original dashboard
          </a>
          <p>
            Design preview · Sample data
            <br />
            No live API requests
          </p>
        </div>
      </aside>

      <div className="tl-workspace">
        <header className="tl-topbar">
          <div className="tl-topbar-left">
            <button
              className="tl-icon-button tl-mobile-menu"
              aria-label="Open navigation"
              onClick={() => setSidebarOpen(true)}
            >
              <Icon name="menu" />
            </button>
            <span className="tl-breadcrumb">
              WORKSPACE <span>/</span>{" "}
              {pages.find((item) => item.id === page)!.title.toUpperCase()}
            </span>
          </div>
          <div className="tl-topbar-actions">
            <span className="tl-preview-pill">
              <i /> DESIGN PREVIEW
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
              AT
            </button>
          </div>
        </header>
        <main className="tl-main">
          <div className="tl-preview-notice">
            <span>TOUCHLINE / 01</span>
            <p>
              An alternate vision for Match Forecast. Every fixture, statistic
              and forecast below is illustrative.
            </p>
            <a href="/">
              Back to your app <Icon name="external" size={13} />
            </a>
          </div>

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
                <button
                  className="tl-outline-button"
                  onClick={() => {
                    setExploreLeague(league);
                    const teams = demoTeams.filter(
                      (team) => team.league === league,
                    );
                    setExploreHome(teams[0].name);
                    setExploreAway(teams[1].name);
                    setExploreError("");
                    setExploreOpen(true);
                  }}
                >
                  <Icon name="swap" size={17} /> Explore a matchup{" "}
                  <Icon name="arrow" size={17} />
                </button>
              </section>

              <section
                className="tl-matchday"
                aria-label="Browse example fixtures"
              >
                <div className="tl-matchday-toolbar">
                  <div className="tl-matchday-date">
                    <span className="tl-mini-label">MATCHDAY</span>
                    <button
                      className="tl-icon-button"
                      aria-label="Previous matchday"
                      onClick={() => setDay((value) => value - 1)}
                    >
                      <Icon name="back" size={16} />
                    </button>
                    <button
                      className="tl-date-button"
                      aria-expanded={calendarOpen}
                      onClick={() => setCalendarOpen((value) => !value)}
                    >
                      <Icon name="calendar" size={17} /> {formattedDate(day)}
                      <Icon name="chevron" size={13} />
                    </button>
                    <button
                      className="tl-icon-button"
                      aria-label="Next matchday"
                      onClick={() => setDay((value) => value + 1)}
                    >
                      <Icon name="arrow" size={16} />
                    </button>
                  </div>
                  <div className="tl-segmented" aria-label="Fixture filter">
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
                      Choose an example matchday
                      <input
                        type="date"
                        value={demoDate(day)}
                        onChange={(event) => {
                          if (event.target.value)
                            setDay(dayForDate(event.target.value));
                        }}
                      />
                    </label>
                    <small>
                      Demo fixtures are available on 17–19 October 2026.
                    </small>
                    <button
                      onClick={() => {
                        setDay(0);
                        setCalendarOpen(false);
                      }}
                    >
                      17 October <Icon name="arrow" size={14} />
                    </button>
                  </div>
                )}
                <div className="tl-fixture-strip">
                  {visibleFixtures.map((fixture) => (
                    <button
                      key={fixture.id}
                      className={`tl-fixture ${fixture.id === selected.id ? "tl-fixture-selected" : ""}`}
                      onClick={() => chooseFixture(fixture)}
                      aria-pressed={fixture.id === selected.id}
                    >
                      <div className="tl-fixture-time">
                        <span>
                          {fixture.time} <small>LOCAL DEMO</small>
                        </span>
                        {(favorites.includes(fixture.home) ||
                          favorites.includes(fixture.away)) && (
                          <Icon name="star" size={12} filled />
                        )}
                      </div>
                      <div className="tl-fixture-clubs">
                        <span>
                          <Club team={teamById[fixture.home]} />
                          {teamById[fixture.home].short}
                        </span>
                        <span className="tl-fixture-vs">—</span>
                        <span>
                          <Club team={teamById[fixture.away]} />
                          {teamById[fixture.away].short}
                        </span>
                      </div>
                      <div className="tl-fixture-footer">
                        <span>
                          {fixture.id === selected.id
                            ? "IN FOCUS"
                            : "View forecast"}
                        </span>
                        <Icon name="arrow" size={14} />
                      </div>
                    </button>
                  ))}
                  {!visibleFixtures.length && (
                    <div className="tl-fixture-empty">
                      <Icon name="calendar" size={24} />
                      <div>
                        <strong>No sample fixtures in this view.</strong>
                        <p>
                          {onlyFavorites
                            ? "Follow a club in this league or view all matches."
                            : "Try 17–19 October to explore the preview."}
                        </p>
                      </div>
                      <button
                        className="tl-text-button"
                        onClick={() => {
                          setDay(0);
                          setOnlyFavorites(false);
                        }}
                      >
                        Show demo matchday <Icon name="arrow" size={14} />
                      </button>
                    </div>
                  )}
                </div>
              </section>

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
                        : `${formattedDate(selected.day, true).toUpperCase()} · ${selected.time}`}
                    </span>
                  </div>
                  <div className="tl-match-teams">
                    <div className="tl-match-team">
                      <button
                        className={`tl-follow-hero ${favorites.includes(home.id) ? "is-following" : ""}`}
                        onClick={() => toggleFavorite(home.id)}
                        aria-label={`${favorites.includes(home.id) ? "Unfollow" : "Follow"} ${home.name}`}
                      >
                        <Icon
                          name="star"
                          size={15}
                          filled={favorites.includes(home.id)}
                        />
                      </button>
                      <Club team={home} large />
                      <span className="tl-team-role">HOME</span>
                      <h2>{home.name}</h2>
                    </div>
                    <div className="tl-versus-art">
                      <span />
                      <strong>vs</strong>
                      <span />
                    </div>
                    <div className="tl-match-team">
                      <button
                        className={`tl-follow-hero ${favorites.includes(away.id) ? "is-following" : ""}`}
                        onClick={() => toggleFavorite(away.id)}
                        aria-label={`${favorites.includes(away.id) ? "Unfollow" : "Follow"} ${away.name}`}
                      >
                        <Icon
                          name="star"
                          size={15}
                          filled={favorites.includes(away.id)}
                        />
                      </button>
                      <Club team={away} large />
                      <span className="tl-team-role">AWAY</span>
                      <h2>{away.name}</h2>
                    </div>
                  </div>
                  <div className="tl-match-hero-bottom">
                    <div>
                      <span className="tl-mini-label">RECENT FORM</span>
                      <FormPills team={home} />
                    </div>
                    <span className="tl-venue">
                      <Icon name="pin" size={13} /> {selected.venue}
                    </span>
                    <div>
                      <span className="tl-mini-label">RECENT FORM</span>
                      <FormPills team={away} />
                    </div>
                  </div>
                </article>

                <article
                  className={`tl-forecast ${generating ? "tl-generating" : ""}`}
                >
                  <div className="tl-panel-heading">
                    <span className="tl-mini-label">THE MODEL FORECAST</span>
                    <button
                      className={`tl-icon-button ${selectedSaved ? "tl-saved" : ""}`}
                      onClick={save}
                      disabled={selected.hypothetical}
                      title={
                        selected.hypothetical
                          ? "Hypothetical matchups are not saved to the scorecard"
                          : selectedSaved
                            ? "Remove from demo scorecard"
                            : "Save to demo scorecard"
                      }
                      aria-label={
                        selectedSaved
                          ? "Remove forecast from demo scorecard"
                          : "Save forecast to demo scorecard"
                      }
                    >
                      <Icon
                        name={selectedSaved ? "check" : "bookmark"}
                        size={18}
                      />
                    </button>
                  </div>
                  <div className="tl-forecast-pick">
                    <span className="tl-pick-label">
                      <i />{" "}
                      {winner === 1
                        ? "Draw is most likely"
                        : `${winner === 0 ? home.name : away.name} to win`}
                    </span>
                    <div className="tl-jumbo-probability">
                      {(p[winner] * 100).toFixed(1)}
                      <span>%</span>
                    </div>
                    <p>Most likely outcome · sample estimate</p>
                  </div>
                  <div className="tl-probability-rail" aria-hidden="true">
                    {p.map((value, i) => (
                      <span
                        className={`tl-outcome-${i}`}
                        style={{ width: pct(value) }}
                        key={i}
                      />
                    ))}
                  </div>
                  <div className="tl-outcome-values">
                    {[home.short, "DRAW", away.short].map((name, index) => (
                      <div key={name}>
                        <span>
                          <i className={`tl-outcome-${index}`} />
                          {name}
                        </span>
                        <strong>{pct(p[index])}</strong>
                      </div>
                    ))}
                  </div>
                  <button
                    className="tl-orange-button"
                    onClick={generate}
                    disabled={generating}
                  >
                    <Icon name="bolt" size={17} />
                    <span>
                      {generating
                        ? "Reading the game…"
                        : generated
                          ? "Regenerate demo forecast"
                          : "Generate demo forecast"}
                    </span>
                    <Icon name="arrow" size={18} />
                  </button>
                  <div className="tl-forecast-foot">
                    <span>
                      <i />{" "}
                      {generated
                        ? "DEMO FORECAST READY"
                        : "ILLUSTRATIVE FORECAST"}
                    </span>
                    <button onClick={() => setInsight("market")}>
                      Compare odds <Icon name="arrow" size={12} />
                    </button>
                  </div>
                </article>
              </section>

              <div className="tl-insights-nav">
                <div role="tablist" aria-label="Match analysis">
                  {(
                    [
                      { id: "overview", label: "The bigger picture" },
                      { id: "market", label: "Market comparison" },
                      { id: "form", label: "Team performance" },
                      { id: "h2h", label: "Head to head" },
                    ] as { id: InsightTab; label: string }[]
                  ).map((tab) => (
                    <button
                      role="tab"
                      aria-selected={insight === tab.id}
                      id={`tl-tab-${tab.id}`}
                      aria-controls={`tl-panel-${tab.id}`}
                      key={tab.id}
                      className={insight === tab.id ? "tl-insight-active" : ""}
                      onClick={() => setInsight(tab.id)}
                    >
                      {tab.label}
                      {tab.id === "market" && <span className="tl-small-dot" />}
                    </button>
                  ))}
                </div>
                <span className="tl-analysis-label">
                  <Icon name="layers" size={14} /> THE DETAILS BEHIND THE
                  NUMBERS
                </span>
              </div>
              <section
                role="tabpanel"
                id={`tl-panel-${insight}`}
                aria-labelledby={`tl-tab-${insight}`}
                className="tl-insight-content"
              >
                {insight === "overview" && (
                  <div className="tl-detail-grid">
                    <article className="tl-panel tl-story">
                      <div className="tl-panel-heading">
                        <h3>What shapes the forecast</h3>
                        <span className="tl-number-tag">01 — 03</span>
                      </div>
                      <p className="tl-panel-copy">
                        A little context goes a long way.
                      </p>
                      <div className="tl-story-row">
                        <span className="tl-story-number">01</span>
                        <div>
                          <strong>Strength over time</strong>
                          <p>
                            {home.rating > away.rating ? home.name : away.name}{" "}
                            holds the higher sample Elo rating.
                          </p>
                        </div>
                        <span className="tl-story-stat">
                          {Math.abs(home.rating - away.rating)}
                          <small>ELO GAP</small>
                        </span>
                      </div>
                      <div className="tl-story-row">
                        <span className="tl-story-number">02</span>
                        <div>
                          <strong>The recent picture</strong>
                          <p>
                            {home.name} collected {points(home)} points in the
                            example last five.
                          </p>
                        </div>
                        <span className="tl-story-stat">
                          {points(home)}
                          <small>OF 15 PTS</small>
                        </span>
                      </div>
                      <div className="tl-story-row">
                        <span className="tl-story-number">03</span>
                        <div>
                          <strong>Home ground matters</strong>
                          <p>
                            The home setting is reflected in the sample goal
                            estimates.
                          </p>
                        </div>
                        <span className="tl-story-stat">
                          <Icon name="pin" size={23} />
                          <small>HOME</small>
                        </span>
                      </div>
                      <small className="tl-context-note">
                        Illustrative context, not a measured breakdown of
                        probability effects.
                      </small>
                    </article>
                    {renderScorelines()}
                  </div>
                )}
                {insight === "market" && (
                  <div className="tl-market-layout">
                    <article className="tl-panel">
                      <div className="tl-panel-heading">
                        <h3>Model meets market.</h3>
                        <span className="tl-chip">INDEPENDENT VIEWS</span>
                      </div>
                      <p className="tl-panel-copy">
                        See where the forecast and bookmaker prices tell a
                        different story.
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
                      {[home.name, "Draw", away.name].map((name, i) => (
                        <div className="tl-market-row" key={name}>
                          <div className="tl-market-row-label">
                            <strong>{name}</strong>
                            {market && (
                              <span
                                className={
                                  p[i] - market[i] > 0
                                    ? "tl-positive"
                                    : "tl-negative"
                                }
                              >
                                {p[i] - market[i] > 0 ? "+" : ""}
                                {((p[i] - market[i]) * 100).toFixed(1)} pp
                              </span>
                            )}
                          </div>
                          <div className="tl-market-bars">
                            <div>
                              <i style={{ width: pct(p[i]) }} />
                              <span>{pct(p[i])}</span>
                            </div>
                            <div className="tl-market-bar-secondary">
                              <i
                                style={{
                                  width: market ? pct(market[i]) : "0%",
                                }}
                              />
                              <span>{market ? pct(market[i]) : "—"}</span>
                            </div>
                          </div>
                        </div>
                      ))}
                      <small className="tl-context-note">
                        The difference is in percentage points. A positive model
                        gap is not proof of betting value; these are example
                        probabilities.
                      </small>
                    </article>
                    <article className="tl-panel tl-odds-panel">
                      <div className="tl-kicker">A SECOND POINT OF VIEW</div>
                      <h3>Add the market.</h3>
                      <p>
                        Try the example prices, or enter three decimal odds to
                        explore the comparison.
                      </p>
                      <form onSubmit={compareOdds}>
                        <div className="tl-odds-inputs">
                          {["Home", "Draw", "Away"].map((label, i) => (
                            <label key={label}>
                              {label}
                              <input
                                type="number"
                                min="1.01"
                                step="0.01"
                                value={prices[i]}
                                onChange={(event) =>
                                  setPrices((current) =>
                                    current.map((value, j) =>
                                      i === j ? event.target.value : value,
                                    ),
                                  )
                                }
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
                          {market
                            ? "Update comparison"
                            : "Compare example odds"}
                          <Icon name="arrow" size={18} />
                        </button>
                      </form>
                      <small>
                        Bookmaker margin is removed. The independent model
                        forecast stays the same.
                      </small>
                      <span className="tl-demo-stamp">
                        DEMO PRICES · ZERO API CALLS
                      </span>
                    </article>
                  </div>
                )}
                {insight === "form" && (
                  <div className="tl-detail-grid">
                    <article className="tl-panel">
                      <div className="tl-panel-heading">
                        <h3>The form guide</h3>
                        <span className="tl-chip">LAST 5 · DEMO</span>
                      </div>
                      <p className="tl-panel-copy">
                        A side-by-side look at recent performance.
                      </p>
                      <div className="tl-form-comparison">
                        {[home, away].map((team) => (
                          <div key={team.id}>
                            <span className="tl-form-team">
                              <Club team={team} />
                              <strong>{team.name}</strong>
                            </span>
                            <FormPills team={team} />
                            <div className="tl-form-stat">
                              <span>Points per match</span>
                              <strong>{(points(team) / 5).toFixed(1)}</strong>
                            </div>
                            <div className="tl-form-stat">
                              <span>Sample Elo</span>
                              <strong>{team.rating}</strong>
                            </div>
                            <div className="tl-form-stat">
                              <span>Goal estimate</span>
                              <strong>
                                {(team.id === home.id
                                  ? forecast.homeGoals
                                  : forecast.awayGoals
                                ).toFixed(2)}
                              </strong>
                            </div>
                          </div>
                        ))}
                      </div>
                      <small className="tl-context-note">
                        Form is shown oldest to newest. All statistics in this
                        preview are example data.
                      </small>
                    </article>
                    {renderScorelines()}
                  </div>
                )}
                {insight === "h2h" && (
                  <div className="tl-detail-grid">
                    <article className="tl-panel">
                      <div className="tl-panel-heading">
                        <h3>The shared history</h3>
                        <span className="tl-chip">EXAMPLE MEETINGS</span>
                      </div>
                      <p className="tl-panel-copy">
                        Context for the rivalry. A small piece of a bigger
                        picture.
                      </p>
                      <div className="tl-h2h-summary">
                        <span>
                          <strong>2</strong>
                          {home.short} wins
                        </span>
                        <span>
                          <strong>2</strong>Draws
                        </span>
                        <span>
                          <strong>1</strong>
                          {away.short} win
                        </span>
                      </div>
                      {[
                        ["14 MAR 2026", home, away, "2 — 1"],
                        ["09 NOV 2025", away, home, "1 — 1"],
                        ["16 FEB 2025", home, away, "1 — 0"],
                      ].map(([date, h, a, score]) => (
                        <div className="tl-h2h-row" key={String(date)}>
                          <span>{String(date)}</span>
                          <span>{(h as DemoTeam).short}</span>
                          <strong>{String(score)}</strong>
                          <span>{(a as DemoTeam).short}</span>
                        </div>
                      ))}
                      <small className="tl-context-note">
                        These illustrative meetings are not real results and do
                        not alter the demo forecast.
                      </small>
                    </article>
                    {renderScorelines()}
                  </div>
                )}
              </section>
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

          {page === "teams" && (
            <>
              <section className="tl-page-heading">
                <div>
                  <div className="tl-kicker">
                    <span /> YOUR SIDE OF THE GAME
                  </div>
                  <h1>
                    Keep them <em>close.</em>
                  </h1>
                  <p>
                    Your clubs. Their next matches. One place to follow it all.
                  </p>
                </div>
                <span className="tl-follow-count">
                  <Icon name="star" filled size={19} />
                  {favorites.length} teams followed
                </span>
              </section>
              <div className="tl-section-title">
                <h2>Coming up for you</h2>
                <span>EXAMPLE FIXTURES</span>
              </div>
              <div className="tl-follow-fixtures">
                {demoFixtures
                  .filter(
                    (fixture) =>
                      fixture.day === 0 &&
                      (favorites.includes(fixture.home) ||
                        favorites.includes(fixture.away)),
                  )
                  .map((fixture) => (
                    <button
                      className="tl-panel"
                      key={fixture.id}
                      onClick={() => {
                        chooseFixture(fixture);
                        setDay(fixture.day);
                      }}
                    >
                      <span className="tl-mini-label">
                        {
                          demoLeagues.find(
                            (item) => item.id === teamById[fixture.home].league,
                          )!.name
                        }{" "}
                        · {fixture.time}
                      </span>
                      <span className="tl-follow-fixture-teams">
                        <Club team={teamById[fixture.home]} />
                        {teamById[fixture.home].short}
                        <small>vs</small>
                        <Club team={teamById[fixture.away]} />
                        {teamById[fixture.away].short}
                      </span>
                      <span className="tl-text-button">
                        Open forecast <Icon name="arrow" size={16} />
                      </span>
                    </button>
                  ))}
              </div>
              {!favorites.length && (
                <div className="tl-panel tl-empty-panel">
                  Follow a club below to put its example fixtures here.
                </div>
              )}
              <div className="tl-section-title">
                <h2>Build your following</h2>
                <label className="tl-search">
                  <Icon name="search" size={17} />
                  <input
                    placeholder="Find a club…"
                    aria-label="Search clubs"
                    value={teamQuery}
                    onChange={(event) => setTeamQuery(event.target.value)}
                  />
                </label>
              </div>
              <div className="tl-club-grid">
                {demoTeams
                  .filter((team) =>
                    team.name.toLowerCase().includes(teamQuery.toLowerCase()),
                  )
                  .map((team) => (
                    <article className="tl-team-card" key={team.id}>
                      <Club team={team} />
                      <div>
                        <strong>{team.name}</strong>
                        <small>
                          {
                            demoLeagues.find((item) => item.id === team.league)!
                              .name
                          }
                        </small>
                      </div>
                      <button
                        className={`tl-icon-button ${favorites.includes(team.id) ? "tl-favorited" : ""}`}
                        aria-label={`${favorites.includes(team.id) ? "Unfollow" : "Follow"} ${team.name}`}
                        onClick={() => toggleFavorite(team.id)}
                      >
                        <Icon
                          name="star"
                          filled={favorites.includes(team.id)}
                          size={18}
                        />
                      </button>
                    </article>
                  ))}
              </div>
              <p className="tl-page-footnote">
                Preview favourites stay in this page session. Your real app’s
                favourites are preserved.
              </p>
            </>
          )}

          {page === "scorecard" && (
            <>
              <section className="tl-page-heading">
                <div>
                  <div className="tl-kicker">
                    <span /> KEEP THE MODEL HONEST
                  </div>
                  <h1>
                    The long <em>game.</em>
                  </h1>
                  <p>
                    Track the forecasts. Learn from the results. See the whole
                    picture.
                  </p>
                </div>
                <button className="tl-outline-button" onClick={exportScorecard}>
                  <Icon name="download" size={17} /> Export demo CSV
                </button>
              </section>
              <div className="tl-scorecard-metrics">
                <article>
                  <span>FORECASTS TRACKED</span>
                  <strong>{records.length.toString().padStart(2, "0")}</strong>
                  <small>
                    {records.filter((record) => record.result === null).length}{" "}
                    pending example results
                  </small>
                </article>
                <article>
                  <span>SETTLED FORECASTS</span>
                  <strong>
                    {records
                      .filter((record) => record.result !== null)
                      .length.toString()
                      .padStart(2, "0")}
                  </strong>
                  <small>Example outcomes only</small>
                </article>
                <article>
                  <span>LOG LOSS</span>
                  <strong>{scorecardLogLoss(records).toFixed(3)}</strong>
                  <small>Lower is better · demo sample</small>
                </article>
                <article>
                  <span>TOP PICK ACCURACY</span>
                  <strong>
                    {scorecardAccuracy(records)}
                    <i>%</i>
                  </strong>
                  <small>Secondary to probability quality</small>
                </article>
              </div>
              <div className="tl-panel tl-scorecard-table">
                <div className="tl-panel-heading">
                  <h3>Your forecast journal</h3>
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
                <div className="tl-table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Match</th>
                        <th>Home</th>
                        <th>Draw</th>
                        <th>Away</th>
                        <th>Outcome</th>
                        <th>Review</th>
                      </tr>
                    </thead>
                    <tbody>
                      {records
                        .filter(
                          (record) =>
                            recordFilter === "all" ||
                            (recordFilter === "pending"
                              ? record.result === null
                              : record.result !== null),
                        )
                        .map((record) => (
                          <tr key={record.id}>
                            <td>
                              <span className="tl-table-clubs">
                                <Club team={teamById[record.fixture.home]} />
                                <strong>
                                  {teamById[record.fixture.home].name}
                                </strong>
                                <small>vs</small>
                                <Club team={teamById[record.fixture.away]} />
                                <strong>
                                  {teamById[record.fixture.away].name}
                                </strong>
                              </span>
                              <small className="tl-table-date">
                                {formattedDate(record.fixture.day, true)} · DEMO
                              </small>
                            </td>
                            {record.probabilities.map((value, i) => (
                              <td
                                className={
                                  i ===
                                  record.probabilities.indexOf(
                                    Math.max(...record.probabilities),
                                  )
                                    ? "tl-table-pick"
                                    : ""
                                }
                                key={i}
                              >
                                {pct(value)}
                              </td>
                            ))}
                            <td>
                              <span
                                className={`tl-status ${record.result === null ? "tl-pending" : ""}`}
                              >
                                {record.result === null
                                  ? "Pending"
                                  : ["Home win", "Draw", "Away win"][
                                      record.result
                                    ]}
                              </span>
                            </td>
                            <td>
                              {record.result === null ? (
                                <button
                                  className="tl-text-button"
                                  onClick={() => {
                                    setRecords((current) =>
                                      current.map((item) =>
                                        item.id === record.id
                                          ? {
                                              ...item,
                                              result:
                                                item.probabilities.indexOf(
                                                  Math.max(
                                                    ...item.probabilities,
                                                  ),
                                                ),
                                            }
                                          : item,
                                      ),
                                    );
                                    notify(
                                      "Example result simulated. No real result checked.",
                                    );
                                  }}
                                >
                                  Simulate result
                                </button>
                              ) : (
                                <span className="tl-settled-mark">
                                  <Icon name="check" size={16} /> Reviewed
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
                {!records.some(
                  (record) =>
                    recordFilter === "all" ||
                    (recordFilter === "pending"
                      ? record.result === null
                      : record.result !== null),
                ) && (
                  <p className="tl-empty-panel">
                    No demo forecasts in this view. Save a match forecast to add
                    one.
                  </p>
                )}
              </div>
              <div className="tl-scorecard-bottom">
                <article className="tl-panel">
                  <h3>Probability, with perspective.</h3>
                  <p>
                    A 60% forecast should succeed about six times in ten over a
                    large sample. The scorecard tracks probability quality over
                    time, including the games the model gets wrong.
                  </p>
                  <button
                    className="tl-text-button"
                    onClick={() => navigate("studio")}
                  >
                    Explore the methodology <Icon name="arrow" size={17} />
                  </button>
                </article>
                <div className="tl-journal-art">
                  <span>
                    Every result
                    <br />
                    is a <em>lesson.</em>
                  </span>
                  <svg viewBox="0 0 220 100" fill="none" aria-hidden="true">
                    <path
                      d="M0 90 30 65 60 78 90 32 120 44 150 12 180 26 220 2"
                      stroke="currentColor"
                      strokeWidth="2"
                    />
                    <path
                      d="M0 100h220"
                      stroke="currentColor"
                      strokeOpacity=".2"
                    />
                  </svg>
                </div>
              </div>
              <p className="tl-page-footnote">
                The journal uses a small fabricated sample to demonstrate the
                interface. It is not evidence of model performance.
              </p>
            </>
          )}

          {page === "studio" && (
            <>
              <section className="tl-page-heading">
                <div>
                  <div className="tl-kicker">
                    <span /> NOTHING UP OUR SLEEVE
                  </div>
                  <h1>
                    Inside the <em>engine.</em>
                  </h1>
                  <p>
                    Clear methods. Honest evaluation. Football intelligence you
                    can inspect.
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
                    A good prediction does more than pick a winner. It gives
                    probabilities that reflect uncertainty, then lets the
                    results test them.
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
                    text: "Elo ratings summarize team strength, opponent quality and results over time. Home advantage is part of the comparison.",
                  },
                  {
                    n: "02",
                    icon: "grid" as IconName,
                    title: "A picture in goals",
                    text: "The app estimates goal probabilities and possible scorelines. The production combination varies by league and evaluation evidence.",
                  },
                  {
                    n: "03",
                    icon: "layers" as IconName,
                    title: "Context, clearly shown",
                    text: "Recent form, venue performance and head-to-head context are visible alongside the estimate. Context is not an exact causal explanation.",
                  },
                  {
                    n: "04",
                    icon: "swap" as IconName,
                    title: "A market perspective",
                    text: "Bookmaker prices are converted into fair probabilities. Compare them with the independent model to see the differences.",
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
              <div className="tl-panel tl-method-note">
                <Icon name="clock" size={26} />
                <div>
                  <h3>Always before kickoff.</h3>
                  <p>
                    Historical evaluation must use chronological splits and
                    inputs available before the predicted match. Production
                    changes should be supported by repeatable improvement in log
                    loss, calibration and other probability metrics.
                  </p>
                </div>
              </div>
              <p className="tl-page-footnote">
                This is a UI concept. The preview uses a simple goal simulator
                and illustrative data; it does not run the production prediction
                engine.
              </p>
            </>
          )}
        </main>
        <footer className="tl-footer">
          <span>
            MATCH FORECAST <i>/</i> TOUCHLINE EDITION
          </span>
          <span>
            Designed for the beautiful game.{" "}
            <span className="tl-footer-ball">◉</span>
          </span>
          <a href="/">
            Original dashboard <Icon name="external" size={12} />
          </a>
        </footer>
      </div>

      <dialog
        ref={dialogRef}
        className="tl-explore-dialog"
        onCancel={() => setExploreOpen(false)}
        onClose={() => setExploreOpen(false)}
        aria-labelledby="tl-explore-title"
      >
        <div className="tl-dialog-heading">
          <span className="tl-kicker">THE MATCHUP LAB</span>
          <button
            className="tl-icon-button"
            onClick={() => setExploreOpen(false)}
            aria-label="Close matchup explorer"
          >
            <Icon name="close" />
          </button>
        </div>
        <h2 id="tl-explore-title">
          What <em>if?</em>
        </h2>
        <p>
          Two clubs. Your curiosity. Explore a matchup even when it isn’t on the
          calendar.
        </p>
        <form onSubmit={explore}>
          <label className="tl-field-label">
            Competition
            <select
              value={exploreLeague}
              onChange={(event) => {
                const value = event.target.value as LeagueId;
                setExploreLeague(value);
                const teams = demoTeams.filter((team) => team.league === value);
                setExploreHome(teams[0].name);
                setExploreAway(teams[1].name);
              }}
            >
              {demoLeagues.map((item) => (
                <option value={item.id} key={item.id}>
                  {item.name} · {item.country}
                </option>
              ))}
            </select>
          </label>
          <div className="tl-explore-teams">
            <label className="tl-field-label">
              Home team
              <input
                value={exploreHome}
                list="tl-demo-home-teams"
                onChange={(event) => {
                  setExploreHome(event.target.value);
                  setExploreError("");
                }}
                placeholder="Search a club…"
                required
              />
              <datalist id="tl-demo-home-teams">
                {demoTeams
                  .filter(
                    (team) =>
                      team.league === exploreLeague &&
                      team.name !== exploreAway,
                  )
                  .map((team) => (
                    <option value={team.name} key={team.id} />
                  ))}
              </datalist>
            </label>
            <button
              type="button"
              className="tl-icon-button"
              aria-label="Swap home and away teams"
              onClick={() => {
                setExploreHome(exploreAway);
                setExploreAway(exploreHome);
              }}
            >
              <Icon name="swap" />
            </button>
            <label className="tl-field-label">
              Away team
              <input
                value={exploreAway}
                list="tl-demo-away-teams"
                onChange={(event) => {
                  setExploreAway(event.target.value);
                  setExploreError("");
                }}
                placeholder="Search a club…"
                required
              />
              <datalist id="tl-demo-away-teams">
                {demoTeams
                  .filter(
                    (team) =>
                      team.league === exploreLeague &&
                      team.name !== exploreHome,
                  )
                  .map((team) => (
                    <option value={team.name} key={team.id} />
                  ))}
              </datalist>
            </label>
          </div>
          {exploreError && (
            <p className="tl-error" role="alert">
              {exploreError}
            </p>
          )}
          <button className="tl-orange-button" type="submit">
            <Icon name="bolt" size={18} />
            Explore demo forecast
            <Icon name="arrow" size={18} />
          </button>
          <small>
            Hypothetical forecasts aren’t added to the scorecard. Demo data
            only.
          </small>
        </form>
      </dialog>
      {toast && (
        <div className="tl-toast" role="status">
          <Icon name="check" size={18} />
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

  function renderScorelines() {
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
          >
            Goal map <Icon name="grid" size={12} />
          </button>
        </div>
        {scoreView === "scores" ? (
          <div className="tl-scoreline-list">
            {forecast.topScores.map((score, index) => (
              <div
                className={`tl-scoreline-row ${index === 0 ? "tl-scoreline-first" : ""}`}
                key={`${score.home}-${score.away}`}
              >
                <span className="tl-scoreline-order">0{index + 1}</span>
                <strong>
                  {score.home}
                  <i>—</i>
                  {score.away}
                </strong>
                <div>
                  <i
                    style={{
                      width: `${(score.probability / forecast.topScores[0].probability) * 100}%`,
                    }}
                  />
                </div>
                <span>{pct(score.probability)}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="tl-goal-map">
            <span className="tl-map-direction">
              {home.short} goals → · {away.short} goals ↓
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
                    const value = forecast.scores.find(
                      (score) => score.home === h && score.away === a,
                    )!.probability;
                    return (
                      <span
                        key={h}
                        className="tl-map-cell"
                        style={
                          {
                            "--cell-opacity": 0.08 + value * 5,
                          } as CSSProperties
                        }
                        title={`${home.short} ${h}–${a} ${away.short}: ${pct(value)}`}
                      >
                        {(value * 100).toFixed(1)}
                        <small>%</small>
                      </span>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="tl-goal-rates">
          <span>
            <small>{home.short} GOAL ESTIMATE</small>
            <strong>{forecast.homeGoals.toFixed(2)}</strong>
          </span>
          <div className="tl-goal-rates-divider" />
          <span>
            <small>{away.short} GOAL ESTIMATE</small>
            <strong>{forecast.awayGoals.toFixed(2)}</strong>
          </span>
        </div>
        <small className="tl-context-note">
          Example score probabilities. The likeliest score is still only one
          possibility.
        </small>
      </article>
    );
  }
}

function scorecardLogLoss(records: DemoRecord[]): number {
  const settled = records.filter((record) => record.result !== null);
  return settled.length
    ? -settled.reduce(
        (sum, record) =>
          sum + Math.log(Math.max(1e-12, record.probabilities[record.result!])),
        0,
      ) / settled.length
    : 0;
}
function scorecardAccuracy(records: DemoRecord[]): string {
  const settled = records.filter((record) => record.result !== null);
  return settled.length
    ? (
        (settled.filter(
          (record) =>
            record.probabilities.indexOf(Math.max(...record.probabilities)) ===
            record.result,
        ).length /
          settled.length) *
        100
      ).toFixed(0)
    : "0";
}
