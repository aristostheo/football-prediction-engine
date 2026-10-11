import { useState } from "react";
import type { Competition } from "../api";
import { localBadge } from "./live";
export function Club({
  name,
  competition,
  src,
  large = false,
}: {
  name: string;
  competition: Competition;
  src?: string | null;
  large?: boolean;
}) {
  const [failed, setFailed] = useState<string[]>([]);
  const fallback = localBadge(competition, name);
  const source = [src, fallback].find(
    (value) => value && !failed.includes(value),
  );
  return (
    <span
      className={`tl-club ${large ? "tl-club-large" : ""}`}
      aria-hidden="true"
    >
      {source ? (
        <img
          src={source}
          alt=""
          width={large ? 112 : 32}
          height={large ? 112 : 32}
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setFailed((current) => [...current, source])}
        />
      ) : (
        <span className="tl-crest-fallback">
          {name
            .split(/\s+/)
            .slice(0, 2)
            .map((word) => word[0])
            .join("")}
        </span>
      )}
    </span>
  );
}
export function FormPills({
  name,
  results,
}: {
  name: string;
  results: string[];
}) {
  return (
    <div
      className="tl-form-pills"
      aria-label={`${name} recent results, oldest first`}
    >
      {results.length ? (
        results.map((result, i) => (
          <span
            className={`tl-form-${result.toLowerCase()}`}
            key={i}
            title={result === "W" ? "Win" : result === "D" ? "Draw" : "Loss"}
          >
            {result}
          </span>
        ))
      ) : (
        <small>Not available yet</small>
      )}
    </div>
  );
}
