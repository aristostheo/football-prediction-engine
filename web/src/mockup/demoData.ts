// Isolated, illustrative fixtures and estimates. Never imported by the live predictor.
export type LeagueId =
  | "england"
  | "spain"
  | "germany"
  | "italy"
  | "france"
  | "portugal"
  | "greece";
export type DemoTeam = {
  id: string;
  name: string;
  short: string;
  league: LeagueId;
  color: string;
  rating: number;
  form: string[];
};
export type DemoFixture = {
  id: string;
  home: string;
  away: string;
  day: number;
  time: string;
  venue: string;
  hypothetical?: boolean;
};

export const demoLeagues: {
  id: LeagueId;
  name: string;
  country: string;
  code: string;
  color: string;
}[] = [
  {
    id: "england",
    name: "Premier League",
    country: "England",
    code: "PL",
    color: "#674695",
  },
  {
    id: "spain",
    name: "La Liga",
    country: "Spain",
    code: "LL",
    color: "#eb5947",
  },
  {
    id: "germany",
    name: "Bundesliga",
    country: "Germany",
    code: "BL",
    color: "#cf3a45",
  },
  {
    id: "italy",
    name: "Serie A",
    country: "Italy",
    code: "SA",
    color: "#3071b4",
  },
  {
    id: "france",
    name: "Ligue 1",
    country: "France",
    code: "L1",
    color: "#38644c",
  },
  {
    id: "portugal",
    name: "Primeira Liga",
    country: "Portugal",
    code: "LP",
    color: "#a98737",
  },
  {
    id: "greece",
    name: "Super League",
    country: "Greece",
    code: "SL",
    color: "#3e709c",
  },
];

export const demoTeams: DemoTeam[] = [
  {
    id: "arsenal",
    name: "Arsenal",
    short: "ARS",
    league: "england",
    color: "#ed3b3a",
    rating: 1846,
    form: ["W", "W", "D", "W", "W"],
  },
  {
    id: "chelsea",
    name: "Chelsea",
    short: "CHE",
    league: "england",
    color: "#527fec",
    rating: 1722,
    form: ["W", "D", "L", "W", "D"],
  },
  {
    id: "man-city",
    name: "Manchester City",
    short: "MCI",
    league: "england",
    color: "#75c3ea",
    rating: 1858,
    form: ["W", "W", "W", "D", "W"],
  },
  {
    id: "liverpool",
    name: "Liverpool",
    short: "LIV",
    league: "england",
    color: "#ee5353",
    rating: 1834,
    form: ["W", "L", "W", "W", "W"],
  },
  {
    id: "tottenham",
    name: "Tottenham",
    short: "TOT",
    league: "england",
    color: "#e8edf5",
    rating: 1660,
    form: ["L", "W", "D", "L", "W"],
  },
  {
    id: "brighton",
    name: "Brighton",
    short: "BHA",
    league: "england",
    color: "#8caaf4",
    rating: 1640,
    form: ["D", "W", "D", "W", "L"],
  },
  {
    id: "real-madrid",
    name: "Real Madrid",
    short: "RMA",
    league: "spain",
    color: "#f4f1e7",
    rating: 1870,
    form: ["W", "W", "D", "W", "W"],
  },
  {
    id: "barcelona",
    name: "Barcelona",
    short: "BAR",
    league: "spain",
    color: "#e79cac",
    rating: 1850,
    form: ["W", "W", "W", "L", "W"],
  },
  {
    id: "atletico",
    name: "Atlético Madrid",
    short: "ATM",
    league: "spain",
    color: "#f57575",
    rating: 1750,
    form: ["W", "D", "W", "D", "W"],
  },
  {
    id: "betis",
    name: "Real Betis",
    short: "BET",
    league: "spain",
    color: "#8ccd9f",
    rating: 1630,
    form: ["W", "L", "D", "W", "D"],
  },
  {
    id: "bayern",
    name: "Bayern München",
    short: "FCB",
    league: "germany",
    color: "#e97878",
    rating: 1870,
    form: ["W", "W", "W", "D", "W"],
  },
  {
    id: "dortmund",
    name: "Dortmund",
    short: "BVB",
    league: "germany",
    color: "#e9cf47",
    rating: 1740,
    form: ["W", "D", "W", "L", "W"],
  },
  {
    id: "leipzig",
    name: "RB Leipzig",
    short: "RBL",
    league: "germany",
    color: "#e8adad",
    rating: 1700,
    form: ["D", "W", "L", "W", "W"],
  },
  {
    id: "frankfurt",
    name: "Frankfurt",
    short: "SGE",
    league: "germany",
    color: "#ef8282",
    rating: 1665,
    form: ["W", "L", "W", "D", "D"],
  },
  {
    id: "inter",
    name: "Inter",
    short: "INT",
    league: "italy",
    color: "#83a7ef",
    rating: 1820,
    form: ["W", "W", "D", "W", "W"],
  },
  {
    id: "milan",
    name: "AC Milan",
    short: "MIL",
    league: "italy",
    color: "#e77a7a",
    rating: 1730,
    form: ["D", "W", "L", "W", "W"],
  },
  {
    id: "juventus",
    name: "Juventus",
    short: "JUV",
    league: "italy",
    color: "#deded5",
    rating: 1720,
    form: ["W", "D", "W", "D", "W"],
  },
  {
    id: "napoli",
    name: "Napoli",
    short: "NAP",
    league: "italy",
    color: "#86c9ed",
    rating: 1780,
    form: ["W", "W", "W", "L", "D"],
  },
  {
    id: "psg",
    name: "Paris Saint-Germain",
    short: "PSG",
    league: "france",
    color: "#8d9ce7",
    rating: 1875,
    form: ["W", "W", "W", "W", "D"],
  },
  {
    id: "marseille",
    name: "Marseille",
    short: "OM",
    league: "france",
    color: "#8cd9ef",
    rating: 1700,
    form: ["W", "D", "W", "L", "W"],
  },
  {
    id: "monaco",
    name: "Monaco",
    short: "ASM",
    league: "france",
    color: "#ea8a8a",
    rating: 1690,
    form: ["W", "L", "W", "W", "D"],
  },
  {
    id: "lille",
    name: "Lille",
    short: "LOSC",
    league: "france",
    color: "#e58c99",
    rating: 1670,
    form: ["D", "W", "D", "W", "L"],
  },
  {
    id: "benfica",
    name: "Benfica",
    short: "SLB",
    league: "portugal",
    color: "#ed8b83",
    rating: 1785,
    form: ["W", "W", "D", "W", "W"],
  },
  {
    id: "porto",
    name: "FC Porto",
    short: "FCP",
    league: "portugal",
    color: "#87b2e9",
    rating: 1770,
    form: ["W", "W", "W", "D", "L"],
  },
  {
    id: "sporting",
    name: "Sporting CP",
    short: "SCP",
    league: "portugal",
    color: "#86caa3",
    rating: 1790,
    form: ["W", "W", "D", "W", "W"],
  },
  {
    id: "braga",
    name: "Braga",
    short: "SCB",
    league: "portugal",
    color: "#f08d8d",
    rating: 1630,
    form: ["W", "L", "D", "W", "D"],
  },
  {
    id: "olympiacos",
    name: "Olympiacos",
    short: "OLY",
    league: "greece",
    color: "#ed8a8a",
    rating: 1750,
    form: ["W", "W", "D", "W", "W"],
  },
  {
    id: "panathinaikos",
    name: "Panathinaikos",
    short: "PAO",
    league: "greece",
    color: "#83c6a3",
    rating: 1690,
    form: ["D", "W", "W", "L", "W"],
  },
  {
    id: "paok",
    name: "PAOK",
    short: "PAOK",
    league: "greece",
    color: "#d3d3cf",
    rating: 1730,
    form: ["W", "D", "W", "W", "L"],
  },
  {
    id: "aek",
    name: "AEK Athens",
    short: "AEK",
    league: "greece",
    color: "#ead473",
    rating: 1720,
    form: ["W", "W", "D", "L", "W"],
  },
];

export const teamById = Object.fromEntries(
  demoTeams.map((team) => [team.id, team]),
) as Record<string, DemoTeam>;
export const demoFixtures: DemoFixture[] = [
  {
    id: "ars-che",
    home: "arsenal",
    away: "chelsea",
    day: 0,
    time: "17:30",
    venue: "Emirates Stadium · London",
  },
  {
    id: "mci-liv",
    home: "man-city",
    away: "liverpool",
    day: 0,
    time: "15:00",
    venue: "Etihad Stadium · Manchester",
  },
  {
    id: "bha-tot",
    home: "brighton",
    away: "tottenham",
    day: 0,
    time: "12:30",
    venue: "Amex Stadium · Brighton",
  },
  {
    id: "che-bha",
    home: "chelsea",
    away: "brighton",
    day: 1,
    time: "14:00",
    venue: "Stamford Bridge · London",
  },
  {
    id: "liv-tot",
    home: "liverpool",
    away: "tottenham",
    day: 2,
    time: "20:00",
    venue: "Anfield · Liverpool",
  },
  {
    id: "rma-bar",
    home: "real-madrid",
    away: "barcelona",
    day: 0,
    time: "20:00",
    venue: "Santiago Bernabéu · Madrid",
  },
  {
    id: "atm-bet",
    home: "atletico",
    away: "betis",
    day: 0,
    time: "17:30",
    venue: "Metropolitano · Madrid",
  },
  {
    id: "bar-atm",
    home: "barcelona",
    away: "atletico",
    day: 1,
    time: "20:00",
    venue: "Camp Nou · Barcelona",
  },
  {
    id: "fcb-bvb",
    home: "bayern",
    away: "dortmund",
    day: 0,
    time: "18:30",
    venue: "Allianz Arena · Munich",
  },
  {
    id: "rbl-sge",
    home: "leipzig",
    away: "frankfurt",
    day: 0,
    time: "15:30",
    venue: "Red Bull Arena · Leipzig",
  },
  {
    id: "bvb-rbl",
    home: "dortmund",
    away: "leipzig",
    day: 1,
    time: "17:30",
    venue: "Signal Iduna Park · Dortmund",
  },
  {
    id: "int-mil",
    home: "inter",
    away: "milan",
    day: 0,
    time: "20:45",
    venue: "San Siro · Milan",
  },
  {
    id: "juv-nap",
    home: "juventus",
    away: "napoli",
    day: 0,
    time: "18:00",
    venue: "Allianz Stadium · Turin",
  },
  {
    id: "nap-int",
    home: "napoli",
    away: "inter",
    day: 1,
    time: "20:45",
    venue: "Stadio Diego Armando Maradona · Naples",
  },
  {
    id: "psg-om",
    home: "psg",
    away: "marseille",
    day: 0,
    time: "21:00",
    venue: "Parc des Princes · Paris",
  },
  {
    id: "asm-los",
    home: "monaco",
    away: "lille",
    day: 0,
    time: "17:00",
    venue: "Stade Louis II · Monaco",
  },
  {
    id: "om-asm",
    home: "marseille",
    away: "monaco",
    day: 1,
    time: "20:45",
    venue: "Orange Vélodrome · Marseille",
  },
  {
    id: "slb-fcp",
    home: "benfica",
    away: "porto",
    day: 0,
    time: "20:30",
    venue: "Estádio da Luz · Lisbon",
  },
  {
    id: "scp-scb",
    home: "sporting",
    away: "braga",
    day: 0,
    time: "18:00",
    venue: "Estádio José Alvalade · Lisbon",
  },
  {
    id: "fcp-scp",
    home: "porto",
    away: "sporting",
    day: 1,
    time: "20:30",
    venue: "Estádio do Dragão · Porto",
  },
  {
    id: "oly-pao",
    home: "olympiacos",
    away: "panathinaikos",
    day: 0,
    time: "20:00",
    venue: "Georgios Karaiskakis · Piraeus",
  },
  {
    id: "paok-aek",
    home: "paok",
    away: "aek",
    day: 0,
    time: "19:00",
    venue: "Toumba Stadium · Thessaloniki",
  },
  {
    id: "aek-oly",
    home: "aek",
    away: "olympiacos",
    day: 1,
    time: "20:00",
    venue: "OPAP Arena · Athens",
  },
];

export function demoDate(day: number): string {
  return new Date(Date.UTC(2026, 9, 17 + day)).toISOString().slice(0, 10);
}
export function dayForDate(value: string): number {
  return Math.round(
    (Date.parse(`${value}T12:00:00Z`) - Date.parse("2026-10-17T12:00:00Z")) /
      86400000,
  );
}
export function formattedDate(day: number, short = false): string {
  return new Date(`${demoDate(day)}T12:00:00Z`).toLocaleDateString("en-GB", {
    weekday: short ? "short" : "long",
    day: "numeric",
    month: "long",
    timeZone: "UTC",
  });
}
export function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}
export function points(team: DemoTeam): number {
  return team.form.reduce(
    (total, result) => total + (result === "W" ? 3 : result === "D" ? 1 : 0),
    0,
  );
}

// A small deterministic simulator for UI interactions, NOT the production model.
export function sampleForecast(fixture: DemoFixture) {
  const home = teamById[fixture.home];
  const away = teamById[fixture.away];
  const difference = (home.rating - away.rating) / 500;
  const homeGoals = Math.max(0.45, Math.min(2.9, 1.56 + difference));
  const awayGoals = Math.max(0.35, Math.min(2.5, 1.12 - difference * 0.65));
  const poisson = (goals: number, rate: number) => {
    let value = Math.exp(-rate);
    for (let n = 1; n <= goals; n++) value *= rate / n;
    return value;
  };
  const scores = Array.from({ length: 10 }, (_, h) =>
    Array.from({ length: 10 }, (_, a) => ({
      home: h,
      away: a,
      probability: poisson(h, homeGoals) * poisson(a, awayGoals),
    })),
  ).flat();
  const total = scores.reduce((sum, score) => sum + score.probability, 0);
  scores.forEach((score) => {
    score.probability /= total;
  });
  const probabilities: [number, number, number] = [0, 0, 0];
  scores.forEach((score) => {
    probabilities[
      score.home > score.away ? 0 : score.home === score.away ? 1 : 2
    ] += score.probability;
  });
  return {
    probabilities,
    homeGoals,
    awayGoals,
    scores,
    topScores: [...scores]
      .sort((a, b) => b.probability - a.probability)
      .slice(0, 4),
  };
}

export type DemoRecord = {
  id: string;
  fixture: DemoFixture;
  probabilities: [number, number, number];
  result: number | null;
};
export const initialDemoRecords: DemoRecord[] = demoFixtures
  .filter((fixture) =>
    ["ars-che", "fcb-bvb", "oly-pao", "rma-bar", "int-mil"].includes(
      fixture.id,
    ),
  )
  .map((fixture, index) => ({
    id: `example-${fixture.id}`,
    fixture: { ...fixture, day: -7 },
    probabilities: sampleForecast(fixture).probabilities,
    result: [0, 1, 0, 2, 0][index],
  }));
