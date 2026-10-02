"""League-scoped aliases for live-provider and historical club names.

Canonical labels match the bundled historical dataset. No fuzzy matching is used:
similar names, reserve teams, and clubs without historical results stay distinct.
"""

from __future__ import annotations

import re
import unicodedata
from functools import cache

from football_predictor.domain import Competition

# Includes every real club in the bundled history, plus promoted Greek clubs
# whose aliases can be recognized once their historical results are imported.
TEAM_ALIASES: dict[Competition, dict[str, tuple[str, ...]]] = {
    Competition.PREMIER_LEAGUE: {
        "AFC Bournemouth": ("Bournemouth",),
        "Arsenal FC": (),
        "Aston Villa FC": (),
        "Birmingham City": ("Birmingham",),
        "Blackburn Rovers": ("Blackburn",),
        "Blackpool FC": (),
        "Bolton Wanderers": ("Bolton",),
        "Bradford City": ("Bradford",),
        "Brentford FC": (),
        "Brighton & Hove Albion FC": ("Brighton", "Brighton Hove Albion"),
        "Burnley FC": (),
        "Cardiff City": ("Cardiff",),
        "Charlton Athletic": ("Charlton",),
        "Chelsea FC": (),
        "Coventry City": ("Coventry",),
        "Crystal Palace FC": ("Palace",),
        "Derby County": ("Derby",),
        "Everton FC": (),
        "Fulham FC": (),
        "Huddersfield Town": ("Huddersfield",),
        "Hull City": ("Hull",),
        "Ipswich Town FC": ("Ipswich",),
        "Leeds United FC": ("Leeds",),
        "Leicester City FC": ("Leicester",),
        "Liverpool FC": (),
        "Luton Town FC": ("Luton",),
        "Manchester City FC": ("Man City",),
        "Manchester United FC": ("Man United", "Man Utd", "Manchester Utd"),
        "Middlesbrough FC": (),
        "Newcastle United FC": ("Newcastle", "Newcastle Utd"),
        "Norwich City FC": ("Norwich",),
        "Nottingham Forest FC": (
            "Nottingham",
            "Nottingham Forrest",
            "Nott'm Forest",
            "Nottm Forest",
        ),
        "Portsmouth FC": (),
        "Queens Park Rangers": ("QPR",),
        "Reading FC": (),
        "Sheffield United FC": ("Sheffield Utd", "Sheff Utd"),
        "Southampton FC": (),
        "Stoke City": ("Stoke",),
        "Sunderland AFC": (),
        "Swansea City": ("Swansea",),
        "Tottenham Hotspur FC": ("Tottenham", "Spurs"),
        "Watford FC": (),
        "West Bromwich Albion FC": ("West Brom", "West Bromwich", "WBA"),
        "West Ham United FC": ("West Ham",),
        "Wigan Athletic": ("Wigan",),
        "Wolverhampton Wanderers FC": ("Wolves", "Wolverhampton"),
    },
    Competition.SUPER_LEAGUE_GREECE: {
        "AE Kifisias": ("Kifisia", "Kifisias", "AE Kifisia", "Κηφισιά"),
        "AE Lárissa": ("AEL", "AEL Larissa", "Larissa", "Larisa", "AE Larisa", "ΑΕΛ"),
        "AEK Athen": ("AEK", "AEK Athens", "AEK Athina", "ΑΕΚ"),
        "Apollon Smyrnis": ("Apollon Smirnis", "Apollon Smyrna", "Απόλλων Σμύρνης"),
        "Aris Saloniki": ("Aris", "Aris Thessaloniki", "Άρης"),
        "Asteras Tripolis": ("Asteras", "Asteras Tripoli", "Asteras Aktor", "Αστέρας Τρίπολης"),
        "Atromitos": ("Atromitos Athens", "Atromitos Athinon", "Atromitos Ath.", "Ατρόμητος"),
        "GS Kallithea": ("Kallithea", "Athens Kallithea", "Καλλιθέα"),
        "Lamia": ("PAS Lamia", "Λαμία"),
        "Levadiakos": ("Levadia", "Λεβαδειακός"),
        "OFI Heraklion": ("OFI", "OFI Crete", "OFI Iraklio", "ΟΦΗ"),
        "Olympiakos Piraeus": (
            "Olympiacos",
            "Olympiakos",
            "Olympiacos Piraeus",
            "Olympiakos Piräus",
            "Ολυμπιακός",
        ),
        "PAOK Saloniki": ("PAOK", "PAOK Thessaloniki", "ΠΑΟΚ"),
        "PAS Giannina": ("Giannina", "ΠΑΣ Γιάννινα"),
        "Panathinaikos": ("Παναθηναϊκός",),
        "Panetolikos": ("Panaitolikos", "Παναιτωλικός"),
        "Panionios GSS": ("Panionios", "Πανιώνιος"),
        "Panserraikos": ("Πανσερραϊκός",),
        "Volos NFC": ("Volos", "NPS Volos", "Βόλος"),
        "Xanthi FC": ("Skoda Xanthi", "Ξάνθη"),
        "Iraklis": ("Iraklis Thessaloniki", "Iraklis 1908", "P.O.T. Iraklis", "Ηρακλής"),
        "Kalamata": ("Καλαμάτα",),
    },
}


def _identity(name: str) -> str:
    name = unicodedata.normalize("NFKD", name.casefold())
    name = "".join(character for character in name if not unicodedata.combining(character))
    name = name.replace("&", " and ")
    name = re.sub(r"[.'’]", "", name)
    tokens = re.sub(r"[^\w]+", " ", name).split()
    if tokens[-2:] == ["football", "club"]:
        tokens = tokens[:-2]
    designators = {"fc", "afc", "cf", "sc"}
    while tokens and tokens[0] in designators:
        tokens.pop(0)
    while tokens and tokens[-1] in designators:
        tokens.pop()
    return " ".join(tokens)


@cache
def _alias_index(competition: Competition) -> dict[str, str]:
    index: dict[str, str] = {}
    for canonical, aliases in TEAM_ALIASES[competition].items():
        for label in (canonical, *aliases):
            key = _identity(label)
            if key in index and index[key] != canonical:
                raise ValueError(f"ambiguous team alias {label!r} in {competition}")
            index[key] = canonical
    return index


def canonical_team_name(name: str, competition: Competition) -> str:
    """Return the registered club label, or preserve an unrecognized name."""
    return _alias_index(competition).get(_identity(name), name)


def is_registered_team(name: str, competition: Competition) -> bool:
    """Whether a name matches a known club or explicit alias for this league."""
    return _identity(name) in _alias_index(competition)


def resolve_team_name(name: str, competition: Competition, known_teams: set[str]) -> str:
    """Resolve aliases only to clubs with results in the selected competition."""
    canonical = canonical_team_name(name, competition)
    if canonical in known_teams:
        return canonical
    matches = {
        team
        for team in known_teams
        if canonical_team_name(team, competition) == canonical or _identity(team) == _identity(name)
    }
    if len(matches) == 1:
        return matches.pop()
    if name in known_teams:
        return name
    return canonical
