import type { Competition } from "./api";

const STORAGE_KEY = "match-forecast.favorite-teams.v1";

export type FavoriteTeams = Partial<Record<Competition, string[]>>;

export function loadFavoriteTeams(): FavoriteTeams {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    const value = parsed as Record<string, unknown>;
    return {
      premier_league: cleanTeamList(value.premier_league),
      super_league_greece: cleanTeamList(value.super_league_greece),
    };
  } catch {
    return {};
  }
}

export function saveFavoriteTeams(favorites: FavoriteTeams): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites));
  } catch {
    // Favorite selection remains available for this page session.
  }
}

function cleanTeamList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.filter((team): team is string => typeof team === "string" && team.trim().length > 0))];
}
