"""Reproducible ingestion of the project's initial OpenFootball dataset."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd

from football_predictor.dataset import build_match_dataframe
from football_predictor.domain import Competition, HistoricalMatch
from football_predictor.sources.openfootball import parse_openfootball_results
from football_predictor.validation import validate_completed_season, validate_match_collection

OPENFOOTBALL_ENGLAND_RAW = "https://raw.githubusercontent.com/openfootball/england/master"
OPENFOOTBALL_EUROPE_RAW = "https://raw.githubusercontent.com/openfootball/europe/master"

PREMIER_LEAGUE_FIRST_SEASON = 2000
GREEK_SUPER_LEAGUE_ARCHIVE_SEASONS = (
    "2018-19",
    "2019-20",
    "2020-21",
    "2023-24",
    "2024-25",
)
GREEK_MATCHES_PER_TEAM = {
    "2018-19": 30,
    "2019-20": 26,
    "2020-21": 26,
    "2023-24": 26,
    "2024-25": 26,
}
GREEK_TEAMS_PER_SEASON = {
    "2018-19": 16,
    "2019-20": 14,
    "2020-21": 14,
    "2023-24": 14,
    "2024-25": 14,
}


@dataclass(frozen=True)
class OpenFootballFile:
    """One local OpenFootball result file and the provenance stored with its rows."""

    competition: Competition
    season: str
    path: Path
    source_url: str
    expected_matches_per_team: int | None = None
    expected_team_count: int | None = None


def initial_openfootball_files(
    *, england_root: Path, europe_root: Path, as_of: date | None = None
) -> tuple[OpenFootballFile, ...]:
    """Return all archived seasons plus the current season for both leagues."""
    current_season = _football_season(as_of or datetime.now(UTC).date())
    current_start_year = int(current_season[:4])
    premier_league_seasons = tuple(
        f"{year}-{str(year + 1)[-2:]}"
        for year in range(PREMIER_LEAGUE_FIRST_SEASON, current_start_year)
    )
    premier_league_completed = tuple(
        OpenFootballFile(
            competition=Competition.PREMIER_LEAGUE,
            season=season,
            path=england_root / season / "1-premierleague.txt",
            source_url=f"{OPENFOOTBALL_ENGLAND_RAW}/{season}/1-premierleague.txt",
            expected_matches_per_team=38,
            expected_team_count=20,
        )
        for season in premier_league_seasons
    )
    premier_league_current = OpenFootballFile(
        competition=Competition.PREMIER_LEAGUE,
        season=current_season,
        path=england_root / current_season / "1-premierleague.txt",
        source_url=(
            f"{OPENFOOTBALL_ENGLAND_RAW}/{current_season}/1-premierleague.txt"
        ),
    )
    greek_seasons = list(GREEK_SUPER_LEAGUE_ARCHIVE_SEASONS)
    greek_seasons.extend(
        f"{year}-{str(year + 1)[-2:]}"
        for year in range(2025, current_start_year + 1)
        if f"{year}-{str(year + 1)[-2:]}" not in greek_seasons
    )
    super_league_greece = tuple(
        OpenFootballFile(
            competition=Competition.SUPER_LEAGUE_GREECE,
            season=season,
            path=europe_root / "greece" / f"{season}_gr1.txt",
            source_url=f"{OPENFOOTBALL_EUROPE_RAW}/greece/{season}_gr1.txt",
            expected_matches_per_team=GREEK_MATCHES_PER_TEAM.get(season),
            expected_team_count=GREEK_TEAMS_PER_SEASON.get(season),
        )
        for season in greek_seasons
    )
    return premier_league_completed + (premier_league_current,) + super_league_greece


def _football_season(as_of: date) -> str:
    """Return the season label for a European football season in progress."""
    start_year = as_of.year if as_of.month >= 7 else as_of.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def parse_openfootball_files(
    source_files: Iterable[OpenFootballFile], *, retrieved_at: datetime
) -> list[HistoricalMatch]:
    """Parse local source files with one consistent retrieval timestamp."""
    matches: list[HistoricalMatch] = []
    for source_file in source_files:
        if not source_file.path.is_file():
            raise FileNotFoundError(f"missing source file: {source_file.path}")
        parsed = _parse_source_text(
            source_file,
            source_file.path.read_text(encoding="utf-8"),
            retrieved_at=retrieved_at,
        )
        matches.extend(parsed)
    return matches


def _parse_source_text(
    source_file: OpenFootballFile, text: str, *, retrieved_at: datetime
) -> list[HistoricalMatch]:
    parsed = parse_openfootball_results(
        text,
        competition=source_file.competition,
        season=source_file.season,
        source_url=source_file.source_url,
        retrieved_at=retrieved_at,
    )
    if not parsed:
        raise ValueError(f"OpenFootball source has no scored matches: {source_file.source_url}")
    if source_file.expected_matches_per_team is not None:
        return validate_completed_season(
            parsed,
            expected_matches_per_team=source_file.expected_matches_per_team,
            expected_team_count=source_file.expected_team_count,
        )
    return validate_match_collection(parsed)


def fetch_openfootball_text(url: str, *, timeout: float = 30.0) -> str:
    """Download one public OpenFootball source file with a bounded timeout."""
    request = Request(url, headers={"User-Agent": "football-prediction-engine/0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise ValueError(f"OpenFootball returned HTTP {response.status} for {url}")
            return response.read().decode("utf-8-sig")
    except (HTTPError, URLError, TimeoutError) as error:
        raise RuntimeError(f"could not download OpenFootball source {url}: {error}") from error


def refresh_openfootball_dataset(
    *,
    output_path: Path,
    manifest_path: Path,
    as_of: date | None = None,
    fetch_text: Callable[[str], str] = fetch_openfootball_text,
    allow_removed_matches: bool = False,
    source_files: Iterable[OpenFootballFile] | None = None,
) -> dict[str, object]:
    """Fetch, validate, and atomically replace the bundled results snapshot.

    Existing fixture identities may not disappear unless the caller explicitly
    accepts removals. All downloads and validation finish before files are replaced.
    """
    retrieved_at = datetime.now(UTC)
    sources = source_files or initial_openfootball_files(
        england_root=Path("."), europe_root=Path("."), as_of=as_of
    )
    matches: list[HistoricalMatch] = []
    source_manifest: list[dict[str, object]] = []
    for source_file in sources:
        text = fetch_text(source_file.source_url)
        parsed = _parse_source_text(source_file, text, retrieved_at=retrieved_at)
        matches.extend(parsed)
        source_manifest.append(
            {
                "competition": source_file.competition.value,
                "season": source_file.season,
                "source_url": source_file.source_url,
                "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "match_count": len(parsed),
                "expected_matches_per_team": source_file.expected_matches_per_team,
                "expected_team_count": source_file.expected_team_count,
                "complete_season": source_file.expected_matches_per_team is not None,
            }
        )
    dataframe = build_match_dataframe(matches)

    previous = pd.read_csv(output_path) if output_path.is_file() else None
    change_summary = _check_refresh_regressions(
        previous, dataframe, allow_removed_matches=allow_removed_matches
    )
    keep_existing_dataset = _dataset_payload_is_unchanged(previous, dataframe)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_csv_path: Path | None = None
    temporary_manifest_path: Path | None = None
    try:
        if keep_existing_dataset:
            dataset_sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()
        else:
            with NamedTemporaryFile(
                dir=output_path.parent,
                prefix=f".{output_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_csv:
                temporary_csv_path = Path(temporary_csv.name)
            dataframe.to_csv(temporary_csv_path, index=False, compression="gzip")
            dataset_sha256 = hashlib.sha256(temporary_csv_path.read_bytes()).hexdigest()
        counts = {
            str(key): int(value)
            for key, value in dataframe.groupby("competition").size().to_dict().items()
        }
        manifest = {
            "schema_version": 2,
            "generated_at": retrieved_at.isoformat(),
            "total_matches": len(dataframe),
            "dataset_sha256": dataset_sha256,
            "matches_by_competition": counts,
            "sources": source_manifest,
        }
        with NamedTemporaryFile(
            dir=manifest_path.parent,
            prefix=f".{manifest_path.name}.",
            suffix=".tmp",
            mode="w",
            encoding="utf-8",
            delete=False,
        ) as temporary_manifest:
            temporary_manifest_path = Path(temporary_manifest.name)
        temporary_manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if temporary_csv_path is not None:
            temporary_csv_path.replace(output_path)
        temporary_manifest_path.replace(manifest_path)
    finally:
        if temporary_csv_path is not None:
            temporary_csv_path.unlink(missing_ok=True)
        if temporary_manifest_path is not None:
            temporary_manifest_path.unlink(missing_ok=True)

    return {**manifest, **change_summary}


def _dataset_payload_is_unchanged(
    previous: pd.DataFrame | None, refreshed: pd.DataFrame
) -> bool:
    """Ignore retrieval timestamps when checking whether stored match data changed."""
    if previous is None or set(previous.columns) != set(refreshed.columns):
        return False
    # Retrieval metadata can change while the match facts remain identical.
    # Keep the checked-in dataset bytes stable in that case; the manifest still
    # records the current upstream URLs and their hashes.
    metadata_columns = {"retrieved_at", "source_url"}
    columns = [column for column in refreshed.columns if column not in metadata_columns]
    identity_columns = ["competition", "season", "match_date", "home_team", "away_team"]
    left = previous[columns].copy()
    right = refreshed[columns].copy()
    for frame in (left, right):
        frame["match_date"] = pd.to_datetime(frame["match_date"]).dt.strftime("%Y-%m-%d")
    left = left.sort_values(identity_columns, kind="stable").reset_index(drop=True)
    right = right.sort_values(identity_columns, kind="stable").reset_index(drop=True)
    return left.equals(right)


def _check_refresh_regressions(
    previous: pd.DataFrame | None,
    refreshed: pd.DataFrame,
    *,
    allow_removed_matches: bool,
) -> dict[str, int]:
    if previous is None:
        return {
            "added_matches": len(refreshed),
            "corrected_scores": 0,
            "removed_matches": 0,
        }
    identity_columns = ["competition", "season", "match_date", "home_team", "away_team"]
    previous = previous.copy()
    refreshed = refreshed.copy()
    previous["match_date"] = pd.to_datetime(previous["match_date"]).dt.strftime("%Y-%m-%d")
    refreshed["match_date"] = pd.to_datetime(refreshed["match_date"]).dt.strftime("%Y-%m-%d")
    previous_rows = previous.set_index(identity_columns)
    refreshed_rows = refreshed.set_index(identity_columns)
    removed = previous_rows.index.difference(refreshed_rows.index)
    if len(removed) and not allow_removed_matches:
        sample = list(removed[:5])
        raise ValueError(
            f"refresh would remove {len(removed)} existing matches; no files were replaced. "
            f"Review upstream changes first. Examples: {sample}"
        )
    shared = previous_rows.index.intersection(refreshed_rows.index)
    old_scores = previous_rows.loc[shared, ["home_goals", "away_goals"]]
    new_scores = refreshed_rows.loc[shared, ["home_goals", "away_goals"]]
    corrected = int((old_scores != new_scores).any(axis=1).sum())
    added = int(len(refreshed_rows.index.difference(previous_rows.index)))
    return {"added_matches": added, "corrected_scores": corrected, "removed_matches": len(removed)}


def write_initial_dataset(
    *,
    england_root: Path,
    europe_root: Path,
    output_path: Path,
    manifest_path: Path,
    retrieved_at: datetime | None = None,
) -> dict[str, object]:
    """Build the first two-competition CSV plus a small, auditable manifest."""
    retrieved_at = retrieved_at or datetime.now(UTC)
    source_files = initial_openfootball_files(england_root=england_root, europe_root=europe_root)
    matches = parse_openfootball_files(source_files, retrieved_at=retrieved_at)
    dataframe = build_match_dataframe(matches)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(output_path, index=False)

    counts = dataframe.groupby("competition").size().sort_index().to_dict()
    manifest = {
        "schema_version": 1,
        "generated_at": retrieved_at.isoformat(),
        "total_matches": len(dataframe),
        "matches_by_competition": counts,
        "sources": [
            {
                "competition": source_file.competition.value,
                "season": source_file.season,
                "source_url": source_file.source_url,
                "expected_matches_per_team": source_file.expected_matches_per_team,
                "expected_team_count": source_file.expected_team_count,
                "complete_season": source_file.expected_matches_per_team is not None,
            }
            for source_file in source_files
        ],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
