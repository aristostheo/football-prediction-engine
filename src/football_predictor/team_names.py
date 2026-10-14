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
    Competition.LA_LIGA: {
        "Athletic Club": ("Athletic Bilbao",),
        "CA Osasuna": ("Osasuna",),
        "Club Atlético de Madrid": ("Atlético Madrid", "Atletico Madrid", "Atletico de Madrid"),
        "Deportivo Alavés": ("Alavés", "Alaves"),
        "Elche CF": ("Elche",),
        "FC Barcelona": ("Barcelona", "Barça"),
        "Getafe CF": ("Getafe",),
        "Levante UD": ("Levante",),
        "RC Celta de Vigo": ("Celta Vigo", "Celta de Vigo", "Celta"),
        "RC Deportivo La Coruña": ("Deportivo de La Coruña", "Deportivo de A Coruña"),
        "RCD Espanyol de Barcelona": ("Espanyol", "RCD Espanyol"),
        "Rayo Vallecano de Madrid": ("Rayo Vallecano",),
        "Real Betis Balompié": ("Real Betis", "Betis"),
        "Real Madrid CF": ("Real Madrid",),
        "Real Sociedad de Fútbol": ("Real Sociedad",),
        "Real Racing Club de Santander": ("Racing de Santander", "Racingde Santander"),
        "Sevilla FC": ("Sevilla",),
        "Valencia CF": ("Valencia",),
        "Villarreal CF": ("Villarreal",),
    },
    Competition.BUNDESLIGA: {
        "FC Bayern München": ("Bayern Munich", "Bayern München", "Bayern"),
        "Borussia Mönchengladbach": ("Gladbach", "Borussia Monchengladbach"),
        "1. FC Köln": ("FC Koln", "Cologne", "Köln"),
        "1. FC Union Berlin": ("Union Berlin",),
        "1. FSV Mainz 05": ("Mainz", "Mainz 05"),
        "Bayer 04 Leverkusen": ("Bayer Leverkusen", "Leverkusen"),
        "Borussia Dortmund": ("Dortmund",),
        "Eintracht Frankfurt": ("Frankfurt",),
        "FC Augsburg": ("Augsburg",),
        "FC Schalke 04": ("Schalke", "Schalke 04"),
        "Hamburger SV": ("Hamburg",),
        "RB Leipzig": ("Leipzig",),
        "SC Freiburg": ("Freiburg",),
        "SC Paderborn 07": ("Paderborn",),
        "SV 07 Elversberg": ("Elversberg", "SV Elversberg"),
        "SV Werder Bremen": ("Werder Bremen", "Bremen"),
        "TSG 1899 Hoffenheim": ("Hoffenheim",),
        "VfB Stuttgart": ("Stuttgart",),
    },
    Competition.SERIE_A: {
        "AC Milan": ("Milan",),
        "AC Monza": ("Monza",),
        "ACF Fiorentina": ("Fiorentina",),
        "AS Roma": ("Roma",),
        "Atalanta BC": ("Atalanta",),
        "Bologna FC 1909": ("Bologna",),
        "Cagliari Calcio": ("Cagliari",),
        "Como 1907": ("Como",),
        "FC Internazionale Milano": ("Inter", "Internazionale", "Inter Milan"),
        "Frosinone Calcio": ("Frosinone",),
        "Genoa CFC": ("Genoa",),
        "Juventus FC": ("Juventus",),
        "Parma Calcio 1913": ("Parma",),
        "SS Lazio": ("Lazio",),
        "SSC Napoli": ("Napoli",),
        "Torino FC": ("Torino",),
        "US Lecce": ("Lecce",),
        "US Sassuolo Calcio": ("Sassuolo",),
        "Udinese Calcio": ("Udinese",),
        "Venezia FC": ("Venezia",),
    },
    Competition.LIGUE_1: {
        "AJ Auxerre": ("Auxerre",),
        "AS Monaco FC": ("Monaco",),
        "Angers SCO": ("Angers",),
        "FC Lorient": ("Lorient",),
        "ESTAC Troyes": ("Troyes",),
        "Le Havre AC": ("Le Havre",),
        "Lille OSC": ("Lille",),
        "OGC Nice": ("Nice",),
        "Olympique Lyonnais": ("Lyon",),
        "Olympique de Marseille": ("Marseille",),
        "Paris FC": ("Paris",),
        "Paris Saint-Germain FC": ("PSG", "Paris Saint Germain"),
        "RC Strasbourg Alsace": ("Strasbourg",),
        "Racing Club de Lens": ("Lens",),
        "Stade Brestois 29": ("Brest",),
        "Stade Rennais FC 1901": ("Rennes",),
        "Toulouse FC": ("Toulouse",),
    },
    Competition.PRIMEIRA_LIGA: {
        "Académico de Viseu FC": ("Academico Viseu", "Academico de Viseu"),
        "CD Nacional": ("Nacional",),
        "CD Santa Clara": ("Santa Clara",),
        "CF Estrela da Amadora": ("Estrela Amadora", "Estrela da Amadora", "Estrela"),
        "CS Marítimo": ("Maritimo",),
        "Casa Pia AC": ("Casa Pia",),
        "FC Alverca": ("Alverca",),
        "FC Arouca": ("Arouca",),
        "FC Famalicão": ("Famalicao",),
        "FC Porto": ("Porto",),
        "GD Estoril Praia": ("Estoril", "Estoril Praia"),
        "Gil Vicente FC": ("Gil Vicente",),
        "Moreirense FC": ("Moreirense",),
        "Rio Ave FC": ("Rio Ave",),
        "Sport Lisboa e Benfica": ("Benfica",),
        "Sporting Clube de Braga": ("Braga", "Sporting Braga"),
        "Sporting Clube de Portugal": ("Sporting CP", "Sporting Lisbon", "Sporting"),
        "Vitória Guimarães": ("Vitoria Guimaraes", "Vitória SC", "Vitoria SC"),
    },
}


def _register_historical_labels(
    competition: Competition, labels: dict[str, tuple[str, ...]]
) -> None:
    for label, aliases in labels.items():
        TEAM_ALIASES[competition].setdefault(label, aliases)


# Keep every historical canonical label registered, including clubs that have
# since left the top division. These entries intentionally add no guessed
# aliases; known live-provider variants are listed explicitly above.
_register_historical_labels(
    Competition.BUNDESLIGA,
    {
        "1. FC Heidenheim 1846": (),
        "1. FC Nürnberg": (),
        "1899 Hoffenheim": (),
        "Arminia Bielefeld": (),
        "Bor. Mönchengladbach": (),
        "Borussia M'gladbach": (),
        "FC St. Pauli 1910": (),
        "Fortuna Düsseldorf": (),
        "Hannover 96": (),
        "Heidenheim": (),
        "Hertha BSC": (),
        "Holstein Kiel": (),
        "SC Paderborn 07": (),
        "SV 07 Elversberg": (),
        "SV Darmstadt 98": (),
        "SpVgg Greuther Fürth 1903": (),
        "St. Pauli": (),
        "VfL Bochum 1848": (),
        "VfL Wolfsburg": (),
        "Wolfsburg": (),
    },
)
_register_historical_labels(
    Competition.LA_LIGA,
    {
        "CD Alavés": (),
        "CD Leganés": (),
        "Cádiz CF": (),
        "Espanyol Barcelona": (),
        "Girona FC": (),
        "Granada CF": (),
        "Málaga CF": (),
        "RC Celta": (),
        "RC Deportivo La Coruña": (),
        "RCD Mallorca": (),
        "Real Oviedo": (),
        "Real Racing Club de Santander": (),
        "Real Valladolid": (),
        "SD Eibar": (),
        "SD Huesca": (),
        "UD Almería": (),
        "UD Las Palmas": (),
    },
)
_register_historical_labels(
    Competition.LIGUE_1,
    {
        "AC Ajaccio": (),
        "AS Saint-Étienne": (),
        "Amiens SC": (),
        "Clermont Foot 63": (),
        "Dijon FCO": (),
        "EA Guingamp": (),
        "ES Troyes AC": (),
        "ESTAC Troyes": (),
        "FC Metz": (),
        "FC Nantes": (),
        "Girondins Bordeaux": (),
        "Le Mans FC": (),
        "Montpellier HSC": (),
        "Nîmes Olympique": (),
        "Olympique Marseille": (),
        "RC Lens": (),
        "RC Strasbourg": (),
        "SM Caen": (),
        "Stade Brestois": (),
        "Stade Rennais": (),
        "Stade de Reims": (),
    },
)
_register_historical_labels(
    Competition.PRIMEIRA_LIGA,
    {
        "AVS": (),
        "Belenenses SAD": (),
        "Boavista": (),
        "CD Aves": (),
        "CD Feirense": (),
        "CD Tondela": (),
        "FC Vizela": (),
        "GD Chaves": (),
        "GD Estoril": (),
        "Paços de Ferreira": (),
        "Portimonense SC": (),
        "SC Farense": (),
        "SL Benfica": (),
        "Vitória Setúbal": (),
    },
)
_register_historical_labels(
    Competition.SERIE_A,
    {
        "Benevento Calcio": (),
        "Brescia Calcio": (),
        "Chievo Verona": (),
        "Cremonese": (),
        "Empoli FC": (),
        "FC Crotone": (),
        "Frosinone Calcio": (),
        "Hellas Verona": (),
        "Lazio Roma": (),
        "Pisa": (),
        "SPAL 2013 Ferrara": (),
        "Sampdoria": (),
        "Sassuolo Calcio": (),
        "Spezia Calcio": (),
        "UC Sampdoria": (),
        "US Cremonese": (),
        "US Salernitana 1919": (),
    },
)

# Explicit same-club labels, not fuzzy matches: preserve one rating/form stream
# when archives and current providers use different names for the same club.
_HISTORICAL_CLUB_IDENTITIES = {
    Competition.BUNDESLIGA: {
        "Borussia Mönchengladbach": ("Bor. Mönchengladbach", "Borussia M'gladbach"),
        "TSG 1899 Hoffenheim": ("1899 Hoffenheim",),
        "1. FC Heidenheim 1846": ("Heidenheim",),
        "FC St. Pauli 1910": ("St. Pauli",),
        "VfL Wolfsburg": ("Wolfsburg",),
    },
    Competition.LA_LIGA: {
        "Deportivo Alavés": ("CD Alavés",),
        "RCD Espanyol de Barcelona": ("Espanyol Barcelona",),
        "RC Celta de Vigo": ("RC Celta",),
    },
    Competition.LIGUE_1: {
        "Olympique de Marseille": ("Olympique Marseille",),
        "Racing Club de Lens": ("RC Lens",),
        "RC Strasbourg Alsace": ("RC Strasbourg",),
        "Stade Brestois 29": ("Stade Brestois",),
        "Stade Rennais FC 1901": ("Stade Rennais",),
        "ESTAC Troyes": ("ES Troyes AC",),
    },
    Competition.PRIMEIRA_LIGA: {
        "Sport Lisboa e Benfica": ("SL Benfica",),
        "GD Estoril Praia": ("GD Estoril",),
    },
    Competition.SERIE_A: {
        "SS Lazio": ("Lazio Roma",),
        "US Sassuolo Calcio": ("Sassuolo Calcio",),
        "UC Sampdoria": ("Sampdoria",),
        "US Cremonese": ("Cremonese",),
    },
}
for _competition, _clubs in _HISTORICAL_CLUB_IDENTITIES.items():
    for _canonical, _labels in _clubs.items():
        _aliases = TEAM_ALIASES[_competition].get(_canonical, ())
        for _label in _labels:
            TEAM_ALIASES[_competition].pop(_label, None)
        TEAM_ALIASES[_competition][_canonical] = tuple(dict.fromkeys((*_aliases, *_labels)))


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
