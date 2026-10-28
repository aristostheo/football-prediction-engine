import { useEffect, useMemo, useState } from "react";
import type { Competition } from "../api";
import type { StoredForecast } from "../scorecard";
import { Icon } from "./Visuals";
import { leagues, pct } from "./live";

type Destination = "center" | "teams" | "scorecard" | "insights" | "studio";
const APP_BOOT_TIME = Date.now();

function signedPoints(value: number) {
  const points = value * 100;
  return `${points > 0 ? "+" : points < 0 ? "−" : ""}${Math.abs(points).toFixed(1)} pp`;
}

function largestGap(record: StoredForecast) {
  if (!record.market_probabilities) return null;
  return Math.max(
    ...record.model_probabilities.map((value, index) =>
      Math.abs(value - record.market_probabilities![index]),
    ),
  );
}

function probabilityName(index: number, home: string, away: string) {
  return index === 0 ? home : index === 1 ? "Draw" : away;
}

function snapshotLabel(record: StoredForecast) {
  if (record.market_source === "manual") {
    return `Manually entered · ${new Date(record.market_compared_at ?? "").toLocaleString()}`;
  }
  const snapshot = record.market_snapshot;
  if (!snapshot) return "Market comparison saved";
  const time = new Date(snapshot.fetched_at).toLocaleString();
  const books = snapshot.bookmaker_count === 1 ? "1 bookmaker" : `${snapshot.bookmaker_count} bookmakers`;
  return `${snapshot.source} · ${books} · loaded ${time}`;
}

export default function BettingInsights({
  records,
  onNavigate,
}: {
  records: StoredForecast[];
  onNavigate: (page: Destination) => void;
}) {
  const [competition, setCompetition] = useState<Competition | "all">("all");
  const [now, setNow] = useState(APP_BOOT_TIME);
  useEffect(() => {
    const refreshTime = () => setNow(Date.now());
    window.addEventListener("focus", refreshTime);
    document.addEventListener("visibilitychange", refreshTime);
    return () => {
      window.removeEventListener("focus", refreshTime);
      document.removeEventListener("visibilitychange", refreshTime);
    };
  }, []);
  const upcoming = useMemo(
    () =>
      records
        .filter((record) => Date.parse(record.kickoff_at) > now)
        .filter((record) => competition === "all" || record.competition === competition)
        .sort((left, right) => {
          const leftGap = largestGap(left) ?? -1;
          const rightGap = largestGap(right) ?? -1;
          return rightGap - leftGap || left.kickoff_at.localeCompare(right.kickoff_at);
        }),
    [competition, now, records],
  );
  const compared = upcoming.filter((record) => record.market_probabilities);
  const withoutMarket = upcoming.length - compared.length;

  return (
    <div className="tl-betting-insights">
      <section className="tl-page-heading">
        <div>
          <div className="tl-kicker"><span /> MODEL AND MARKET, SIDE BY SIDE</div>
          <h1>Bet with <em>context.</em></h1>
          <p>Compare your saved forecasts with the market. A difference is something to investigate, not a promise of value.</p>
        </div>
        <button className="tl-outline-button" onClick={() => onNavigate("center")}>
          <Icon name="grid" size={17} /> Open match center <Icon name="arrow" size={17} />
        </button>
      </section>

      <div className="tl-scorecard-metrics tl-insights-metrics">
        <article>
          <span>UPCOMING FORECASTS</span>
          <strong>{upcoming.length}</strong>
          <small>Saved before kickoff in this browser</small>
        </article>
        <article>
          <span>WITH MARKET COMPARISON</span>
          <strong>{compared.length}</strong>
          <small>Live or manually entered odds</small>
        </article>
        <article>
          <span>MODEL ONLY</span>
          <strong>{withoutMarket}</strong>
          <small>Market prices have not been loaded</small>
        </article>
      </div>

      <div className="tl-insights-explainer">
        <div className="tl-insights-explainer-mark"><Icon name="swap" size={20} /></div>
        <div>
          <strong>What does the difference mean?</strong>
          <p>The model probability is independent of the bookmaker odds. The market probability removes the bookmaker margin. Their difference is shown in percentage points; it is not a guaranteed edge, expected return, or betting recommendation.</p>
        </div>
      </div>

      <section className="tl-insights-list-section">
        <div className="tl-section-title">
          <div>
            <h2>Your upcoming comparisons</h2>
            <span>Matches with the largest model–market gaps appear first.</span>
          </div>
          <label className="tl-insights-filter">
            <span>COMPETITION</span>
            <select aria-label="Filter betting insights by competition" value={competition} onChange={(event) => setCompetition(event.target.value as Competition | "all")}>
              <option value="all">All competitions</option>
              {leagues.map((league) => <option key={league.id} value={league.id}>{league.name}</option>)}
            </select>
          </label>
        </div>

        {upcoming.length ? (
          <div className="tl-insights-cards">
            {upcoming.map((record) => {
              const gap = largestGap(record);
              const league = leagues.find((item) => item.id === record.competition)?.name ?? record.competition;
              return (
                <article className="tl-panel tl-insight-match" key={record.id}>
                  <header>
                    <div>
                      <span className="tl-kicker">{league} · {new Date(record.kickoff_at).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</span>
                      <h3>{record.home_team} <span>vs</span> {record.away_team}</h3>
                    </div>
                    {gap !== null ? <span className="tl-insight-gap">Largest gap <strong>{(gap * 100).toFixed(1)} pp</strong></span> : <span className="tl-insight-no-market">Model only</span>}
                  </header>
                  <div className="tl-insight-outcomes" aria-label="Model and market probabilities">
                    {[0, 1, 2].map((index) => {
                      const model = record.model_probabilities[index];
                      const market = record.market_probabilities?.[index];
                      const difference = market == null ? null : model - market;
                      return (
                        <div className="tl-insight-outcome" key={index}>
                          <span>{probabilityName(index, record.home_team, record.away_team)}</span>
                          <div><small>MODEL</small><strong>{pct(model)}</strong></div>
                          <div><small>MARKET</small><strong>{market == null ? "—" : pct(market)}</strong></div>
                          <div className={`tl-insight-difference ${difference == null ? "is-empty" : difference > 0 ? "is-model-higher" : difference < 0 ? "is-market-higher" : "is-even"}`}>
                            <small>DIFFERENCE</small><strong>{difference == null ? "Load odds" : signedPoints(difference)}</strong>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <footer>
                    {record.market_probabilities ? (
                      <span>{snapshotLabel(record)}</span>
                    ) : (
                      <span>No market prices saved for this forecast.</span>
                    )}
                    <button className="tl-text-button" onClick={() => onNavigate("scorecard")}>
                      View forecast journal <Icon name="arrow" size={15} />
                    </button>
                  </footer>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="tl-panel tl-empty-panel tl-insights-empty">
            <h3>No upcoming forecasts to compare yet.</h3>
            <p>In Match center, choose an upcoming game, optionally load its market odds, then generate a forecast. We’ll keep the independent model and market probabilities separate here.</p>
            <button className="tl-dark-button" onClick={() => onNavigate("center")}>
              Go to Match center <Icon name="arrow" size={16} />
            </button>
          </div>
        )}
        <p className="tl-page-footnote">Forecasts and comparisons are stored in this browser only. This page never requests odds in bulk; it displays only snapshots you chose to load or manually enter.</p>
      </section>
    </div>
  );
}
