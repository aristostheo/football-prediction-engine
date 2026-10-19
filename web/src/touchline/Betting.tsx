import { useState } from "react";
import type { ReactNode, FormEvent } from "react";
import type { BettingMarket, Prediction } from "../api";
import { pct, teamShort } from "./live";
import { comparePair, derivedMarket, difference, price } from "./bettingMath";
import { Icon } from "./Visuals";

type Section = "result" | "goals" | "teams" | "scores";
const sections: { id: Section; label: string }[] = [
  { id: "result", label: "Result" },
  { id: "goals", label: "Goals" },
  { id: "teams", label: "Team totals" },
  { id: "scores", label: "Scores" },
];

function MarketCard({
  market,
  title = market.title,
  manual = false,
  derived = null,
}: {
  market: BettingMarket;
  title?: string;
  manual?: boolean;
  derived?: number[] | null;
}) {
  const [prices, setPrices] = useState(["", ""]);
  const [focused, setFocused] = useState(-1);
  const [comparison, setComparison] = useState<[number, number] | null>(null);
  const [error, setError] = useState("");
  const values = derived ?? comparison;
  function compare(event: FormEvent) {
    event.preventDefault();
    try {
      setComparison(comparePair(prices));
      setError("");
    } catch (e) {
      setComparison(null);
      setError(e instanceof Error ? e.message : "Check both prices.");
    }
  }
  return (
    <article className="tl-panel tl-bet-card" aria-label={title}>
      <div className="tl-bet-card-heading">
        <div>
          <span className="tl-kicker">
            {market.source === "goal_model" ? "GOAL MODEL" : "RESULT FORECAST"}
          </span>
          <h3>{title}</h3>
        </div>
        {market.line != null && (
          <span className="tl-bet-line">{market.line.toFixed(1)}</span>
        )}
      </div>
      {market.key === "draw_no_bet" && (
        <p className="tl-bet-help">
          A draw returns the stake. Chances below are conditional on no draw.
        </p>
      )}
      <div className="tl-bet-outcomes">
        {market.outcomes.map((outcome, index) => (
          <div className="tl-bet-outcome" key={outcome.key}>
            <span className="tl-bet-selection">
              {outcome.label}
              {market.line != null ? ` ${market.line.toFixed(1)}` : ""}
            </span>
            <span className="tl-bet-chance">{pct(outcome.probability)}</span>
            <div className="tl-bet-meter">
              <i style={{ width: pct(outcome.probability) }} />
            </div>
            <span className="tl-bet-fair">
              Model fair odds <strong>{price(outcome.fair_odds)}</strong>
            </span>
            {outcome.push_probability > 0 && (
              <small>Draw refund: {pct(outcome.push_probability)}</small>
            )}
            {values && (
              <div className="tl-bet-comparison">
                <span>
                  Market <strong>{pct(values[index])}</strong>
                </span>
                <span>
                  Difference{" "}
                  <strong>
                    {difference(outcome.probability, values[index])}
                  </strong>
                </span>
              </div>
            )}
          </div>
        ))}
      </div>
      {derived && (
        <p className="tl-bet-help">
          Market chances derived from your margin-free 1X2 comparison, not
          direct quotes for this line.
        </p>
      )}
      {!manual && !derived && market.source === "result_forecast" && (
        <p className="tl-bet-help">
          Load or enter 1X2 odds above to derive the market comparison.
        </p>
      )}
      {manual && (
        <details className="tl-bet-manual">
          <summary>
            Enter bookmaker odds <Icon name="chevron" size={15} />
          </summary>
          <p className="tl-bet-help">
            Enter both prices from the same bookmaker for this exact line. The
            comparison removes their margin.
          </p>
          <form onSubmit={compare} noValidate aria-label={`Compare ${title}`}>
            <div className="tl-bet-inputs">
              {market.outcomes.map((outcome, index) => (
                <label key={outcome.key}>
                  {outcome.label} odds
                  <input
                    type="number"
                    inputMode="decimal"
                    step="any"
                    min="1.000001"
                    value={
                      focused === index ||
                      !prices[index] ||
                      !Number.isFinite(Number(prices[index]))
                        ? prices[index]
                        : price(Number(prices[index]))
                    }
                    onFocus={() => setFocused(index)}
                    onBlur={() => setFocused(-1)}
                    placeholder="e.g. 1.90"
                    onChange={(event) => {
                      const value = event.target.value;
                      setPrices((current) =>
                        current.map((p, i) => (i === index ? value : p)),
                      );
                      setComparison(null);
                      setError("");
                    }}
                  />
                </label>
              ))}
            </div>
            {error && (
              <p className="tl-error" role="alert">
                {error}
              </p>
            )}
            <button type="submit" className="tl-dark-button">
              Compare this line <Icon name="arrow" size={16} />
            </button>
          </form>
        </details>
      )}
      {comparison && (
        <p className="tl-bet-help" role="status">
          Manual comparison · margin removed · kept for this view only.
        </p>
      )}
    </article>
  );
}

export default function Betting({
  prediction,
  home,
  away,
  market,
  resultView,
  generate,
  generating,
  canGenerate,
}: {
  prediction: Prediction | null;
  home: string;
  away: string;
  market: [number, number, number] | null;
  resultView: ReactNode;
  generate: () => void;
  generating: boolean;
  canGenerate: boolean;
}) {
  const [section, setSection] = useState<Section>("result");
  const [totalLine, setTotalLine] = useState(2.5);
  const [teamLine, setTeamLine] = useState(1.5);
  const forecast = prediction?.betting;
  const markets = forecast?.markets ?? [];
  const goalsReady = forecast?.goal_status === "experimental";
  const scores = markets.find((m) => m.key === "correct_score");
  return (
    <div className="tl-betting">
      <div className="tl-betting-heading">
        <div>
          <div className="tl-kicker">A CLOSER LOOK AT THE MATCH</div>
          <h2>Betting, with perspective.</h2>
          <p>Model probabilities, fair prices and a view of the market.</p>
        </div>
        <span className="tl-chip">90 MIN + STOPPAGE TIME</span>
      </div>
      <div
        className="tl-betting-sections"
        role="group"
        aria-label="Betting sections"
      >
        {sections.map((item) => (
          <button
            key={item.id}
            aria-pressed={section === item.id}
            onClick={() => setSection(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {section === "result" ? (
        <>
          {resultView}
          {forecast && (
            <div className="tl-bet-grid tl-bet-result-derived">
              {markets
                .filter((m) => ["double_chance", "draw_no_bet"].includes(m.key))
                .map((m) => (
                  <MarketCard
                    key={`${prediction?.forecasted_at}|${m.key}`}
                    market={m}
                    derived={derivedMarket(m, market)}
                  />
                ))}
            </div>
          )}
        </>
      ) : !prediction ? (
        <div className="tl-panel tl-bet-empty">
          <h3>Start with the forecast.</h3>
          <p>
            {canGenerate
              ? "Calculate this matchup to explore its goal lines, team totals and possible scores."
              : "Only upcoming fixtures and hypothetical matchups can be forecast."}
          </p>
          <button
            className="tl-orange-button"
            onClick={generate}
            disabled={generating || !canGenerate}
          >
            {!canGenerate
              ? "Forecast unavailable"
              : generating
                ? "Calculating…"
                : "Calculate these markets"}
            <Icon name="arrow" size={16} />
          </button>
        </div>
      ) : !goalsReady ? (
        <div className="tl-panel tl-bet-empty">
          <h3>Goal estimates unavailable.</h3>
          <p>
            {forecast?.goal_note ??
              "Regenerate this forecast to load the additional market estimates."}
          </p>
        </div>
      ) : (
        <>
          <div className="tl-bet-source-note">
            <span className="tl-chip">EXPERIMENTAL · GOAL MODEL</span>
            <p>
              {forecast.goal_note} Live odds currently cover 1X2; you can enter
              goal-line prices below.
            </p>
            <details>
              <summary>About these estimates</summary>
              <p>
                They use the same score distribution as the existing scoreline
                feature. Historical testing found mixed results for totals and
                both teams to score, particularly in Greece. No extra
                calibration or bookmaker inputs are applied.
              </p>
              {forecast.goal_result_probabilities && (
                <p>
                  Goal-model result chances: Home{" "}
                  {pct(forecast.goal_result_probabilities[0])} · Draw{" "}
                  {pct(forecast.goal_result_probabilities[1])} · Away{" "}
                  {pct(forecast.goal_result_probabilities[2])}.
                </p>
              )}
            </details>
          </div>
          {section === "goals" && (
            <>
              <div className="tl-bet-controls">
                <label>
                  Total goals line
                  <select
                    value={totalLine}
                    onChange={(e) => setTotalLine(Number(e.target.value))}
                  >
                    {[0.5, 1.5, 2.5, 3.5, 4.5].map((line) => (
                      <option key={line} value={line}>
                        {line.toFixed(1)} goals
                      </option>
                    ))}
                  </select>
                </label>
                <span>Over and under include both teams’ goals.</span>
              </div>
              <div className="tl-bet-grid">
                {markets
                  .filter(
                    (m) => m.key === `total_${totalLine}` || m.key === "btts",
                  )
                  .map((m) => (
                    <MarketCard
                      key={`${prediction?.forecasted_at}|${m.key}`}
                      market={m}
                      manual
                    />
                  ))}
              </div>
            </>
          )}
          {section === "teams" && (
            <>
              <div className="tl-bet-controls">
                <label>
                  Team goals line
                  <select
                    value={teamLine}
                    onChange={(e) => setTeamLine(Number(e.target.value))}
                  >
                    {[0.5, 1.5, 2.5].map((line) => (
                      <option key={line} value={line}>
                        {line.toFixed(1)} goals
                      </option>
                    ))}
                  </select>
                </label>
                <span>Each line counts only that team’s goals.</span>
              </div>
              <div className="tl-bet-grid">
                {markets
                  .filter((m) => m.group === "teams" && m.line === teamLine)
                  .map((m) => (
                    <MarketCard
                      key={`${prediction?.forecasted_at}|${m.key}`}
                      market={m}
                      title={`${teamShort(m.team === "home" ? home : away)} goals`}
                      manual
                    />
                  ))}
              </div>
            </>
          )}
          {section === "scores" && scores && (
            <article className="tl-panel tl-bet-scores">
              <div className="tl-panel-heading">
                <h3>Possible scores. Fair prices.</h3>
                <span className="tl-chip">HOME – AWAY</span>
              </div>
              <p className="tl-bet-help">
                The nine most likely scores, with their individual
                probabilities. Other scorelines retain the remaining
                probability.
              </p>
              <div className="tl-bet-score-grid">
                {scores.outcomes.map((outcome, index) => (
                  <div
                    key={outcome.key}
                    className={index === 0 ? "tl-bet-score-top" : ""}
                  >
                    <span>
                      {index === 0
                        ? "MOST LIKELY"
                        : `SCORE ${String(index + 1).padStart(2, "0")}`}
                    </span>
                    <strong>{outcome.label}</strong>
                    <p>
                      {pct(outcome.probability)} <span>probability</span>
                    </p>
                    <small>
                      Fair odds <b>{price(outcome.fair_odds)}</b>
                    </small>
                  </div>
                ))}
              </div>
              <p className="tl-bet-help">
                All other scores:{" "}
                {pct(
                  Math.max(
                    0,
                    1 -
                      scores.outcomes.reduce(
                        (sum, outcome) => sum + outcome.probability,
                        0,
                      ),
                  ),
                )}
                . Fair odds are model estimates, not bookmaker offers. A partial
                list of bookmaker score prices is insufficient to remove the
                whole market’s margin.
              </p>
            </article>
          )}
        </>
      )}
      <p className="tl-bet-footnote">
        Fair odds are calculated from model probabilities and shown to two
        decimals. A probability difference is measured in percentage points, not
        a guaranteed betting edge. Extra time and penalties are excluded.
      </p>
    </div>
  );
}
