export type IconName =
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

export function Icon({
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
export function Brand() {
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
export function StadiumCanvas() {
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
