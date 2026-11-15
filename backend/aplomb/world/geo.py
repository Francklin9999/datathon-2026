"""Country reference table and source-place resolution (world SPEC §3).

Centroids are approximate display anchors for ``precision = "country"``; they are never used
as a claim about where something happened inside the country. A place that cannot be mapped
to a country keeps ``countryIso3 = None`` instead of a guess.
"""

from __future__ import annotations

from dataclasses import dataclass

# ISO 3166-1 user-assigned code used for the "no listing country" exposure bucket.
UNKNOWN_COUNTRY = "ZZZ"


@dataclass(frozen=True)
class Country:
    iso3: str
    en: str
    fr: str
    lat: float
    lon: float


# iso3, English name, French name, approximate centroid latitude, longitude.
_ROWS: tuple[tuple[str, str, str, float, float], ...] = (
    ("CAN", "Canada", "Canada", 56.1, -106.3),
    ("USA", "United States", "États-Unis", 39.8, -98.6),
    ("MEX", "Mexico", "Mexique", 23.6, -102.6),
    ("GTM", "Guatemala", "Guatemala", 15.8, -90.2),
    ("SLV", "El Salvador", "Salvador", 13.8, -88.9),
    ("HND", "Honduras", "Honduras", 15.2, -86.2),
    ("NIC", "Nicaragua", "Nicaragua", 12.9, -85.2),
    ("CRI", "Costa Rica", "Costa Rica", 9.7, -83.8),
    ("PAN", "Panama", "Panama", 8.5, -80.8),
    ("COL", "Colombia", "Colombie", 4.6, -74.3),
    ("VEN", "Venezuela", "Venezuela", 6.4, -66.6),
    ("ECU", "Ecuador", "Équateur", -1.8, -78.2),
    ("PER", "Peru", "Pérou", -9.2, -75.0),
    ("BOL", "Bolivia", "Bolivie", -16.3, -63.6),
    ("CHL", "Chile", "Chili", -35.7, -71.5),
    ("ARG", "Argentina", "Argentine", -38.4, -63.6),
    ("BRA", "Brazil", "Brésil", -14.2, -51.9),
    ("CUB", "Cuba", "Cuba", 21.5, -77.8),
    ("HTI", "Haiti", "Haïti", 19.0, -72.3),
    ("DOM", "Dominican Republic", "République dominicaine", 18.7, -70.2),
    ("JAM", "Jamaica", "Jamaïque", 18.1, -77.3),
    ("PRI", "Puerto Rico", "Porto Rico", 18.2, -66.5),
    ("GBR", "United Kingdom", "Royaume-Uni", 55.4, -3.4),
    ("IRL", "Ireland", "Irlande", 53.4, -8.2),
    ("FRA", "France", "France", 46.2, 2.2),
    ("DEU", "Germany", "Allemagne", 51.2, 10.5),
    ("ITA", "Italy", "Italie", 41.9, 12.6),
    ("ESP", "Spain", "Espagne", 40.5, -3.7),
    ("PRT", "Portugal", "Portugal", 39.4, -8.2),
    ("NLD", "Netherlands", "Pays-Bas", 52.1, 5.3),
    ("BEL", "Belgium", "Belgique", 50.5, 4.5),
    ("CHE", "Switzerland", "Suisse", 46.8, 8.2),
    ("AUT", "Austria", "Autriche", 47.5, 14.6),
    ("SWE", "Sweden", "Suède", 60.1, 18.6),
    ("NOR", "Norway", "Norvège", 60.5, 8.5),
    ("DNK", "Denmark", "Danemark", 56.3, 9.5),
    ("FIN", "Finland", "Finlande", 61.9, 25.7),
    ("ISL", "Iceland", "Islande", 65.0, -19.0),
    ("POL", "Poland", "Pologne", 51.9, 19.1),
    ("GRC", "Greece", "Grèce", 39.1, 21.8),
    ("TUR", "Turkey", "Turquie", 39.0, 35.2),
    ("RUS", "Russia", "Russie", 61.5, 105.3),
    ("UKR", "Ukraine", "Ukraine", 48.4, 31.2),
    ("ROU", "Romania", "Roumanie", 45.9, 25.0),
    ("ISR", "Israel", "Israël", 31.0, 34.9),
    ("SAU", "Saudi Arabia", "Arabie saoudite", 23.9, 45.1),
    ("ARE", "United Arab Emirates", "Émirats arabes unis", 23.4, 53.8),
    ("IRN", "Iran", "Iran", 32.4, 53.7),
    ("IRQ", "Iraq", "Irak", 33.2, 43.7),
    ("AFG", "Afghanistan", "Afghanistan", 33.9, 67.7),
    ("PAK", "Pakistan", "Pakistan", 30.4, 69.3),
    ("IND", "India", "Inde", 20.6, 79.0),
    ("NPL", "Nepal", "Népal", 28.4, 84.1),
    ("BGD", "Bangladesh", "Bangladesh", 23.7, 90.4),
    ("MMR", "Myanmar", "Myanmar", 21.9, 96.0),
    ("THA", "Thailand", "Thaïlande", 15.9, 101.0),
    ("VNM", "Vietnam", "Viêt Nam", 14.1, 108.3),
    ("MYS", "Malaysia", "Malaisie", 4.2, 102.0),
    ("SGP", "Singapore", "Singapour", 1.35, 103.8),
    ("IDN", "Indonesia", "Indonésie", -0.8, 113.9),
    ("PHL", "Philippines", "Philippines", 12.9, 121.8),
    ("CHN", "China", "Chine", 35.9, 104.2),
    ("TWN", "Taiwan", "Taïwan", 23.7, 121.0),
    ("KOR", "South Korea", "Corée du Sud", 35.9, 127.8),
    ("PRK", "North Korea", "Corée du Nord", 40.3, 127.5),
    ("JPN", "Japan", "Japon", 36.2, 138.3),
    ("MNG", "Mongolia", "Mongolie", 46.9, 103.8),
    ("KAZ", "Kazakhstan", "Kazakhstan", 48.0, 66.9),
    ("KGZ", "Kyrgyzstan", "Kirghizistan", 41.2, 74.8),
    ("TJK", "Tajikistan", "Tadjikistan", 38.9, 71.3),
    ("AUS", "Australia", "Australie", -25.3, 133.8),
    ("NZL", "New Zealand", "Nouvelle-Zélande", -40.9, 174.9),
    ("PNG", "Papua New Guinea", "Papouasie-Nouvelle-Guinée", -6.3, 144.0),
    ("SLB", "Solomon Islands", "Îles Salomon", -9.6, 160.2),
    ("VUT", "Vanuatu", "Vanuatu", -15.4, 167.0),
    ("FJI", "Fiji", "Fidji", -17.7, 178.1),
    ("TON", "Tonga", "Tonga", -21.2, -175.2),
    ("WSM", "Samoa", "Samoa", -13.8, -172.1),
    ("NCL", "New Caledonia", "Nouvelle-Calédonie", -20.9, 165.6),
    ("TLS", "Timor-Leste", "Timor oriental", -8.9, 125.7),
    ("ZAF", "South Africa", "Afrique du Sud", -30.6, 22.9),
    ("EGY", "Egypt", "Égypte", 26.8, 30.8),
    ("MAR", "Morocco", "Maroc", 31.8, -7.1),
    ("DZA", "Algeria", "Algérie", 28.0, 1.7),
    ("NGA", "Nigeria", "Nigéria", 9.1, 8.7),
    ("ETH", "Ethiopia", "Éthiopie", 9.1, 40.5),
    ("KEN", "Kenya", "Kenya", 0.0, 37.9),
    ("TZA", "Tanzania", "Tanzanie", -6.4, 34.9),
    ("COD", "Democratic Republic of the Congo", "République démocratique du Congo", -4.0, 21.8),
)

COUNTRIES: dict[str, Country] = {r[0]: Country(*r) for r in _ROWS}

# Extra spellings seen in source place strings (lower case) -> ISO3.
_ALIASES: dict[str, str] = {
    "türkiye": "TUR", "turkiye": "TUR", "burma": "MMR", "burma (myanmar)": "MMR", "russian federation": "RUS",
    "united states of america": "USA", "u.s.": "USA", "us": "USA", "republic of korea": "KOR",
    "viet nam": "VNM", "timor leste": "TLS", "east timor": "TLS", "dr congo": "COD",
    "fiji islands": "FJI", "the philippines": "PHL", "great britain": "GBR", "england": "GBR",
}
# U.S. states and territories as written by USGS (full names and postal codes).
_US_STATES: tuple[str, ...] = (
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut", "delaware",
    "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas", "kentucky",
    "louisiana", "maine", "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
    "missouri", "montana", "nebraska", "nevada", "new hampshire", "new jersey", "new mexico",
    "new york", "north carolina", "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania",
    "rhode island", "south carolina", "south dakota", "tennessee", "texas", "utah", "vermont",
    "virginia", "washington", "west virginia", "wisconsin", "wyoming",
    "ak", "ca", "hi", "nv", "wa", "or", "id", "mt", "wy", "ut", "ok", "tx", "tn", "mo", "ks", "nm",
    "az", "co", "sc", "nc", "ny", "nj", "pa", "va", "ky", "ar", "al", "ms", "il",
)
_NAMES: dict[str, str] = {c.en.lower(): c.iso3 for c in COUNTRIES.values()}
_NAMES.update(_ALIASES)
# "Georgia" is both a U.S. state and a country: ambiguous, so it resolves to nothing.
_AMBIGUOUS = {"georgia"}


def country(iso3: str) -> Country | None:
    return COUNTRIES.get(iso3)


def country_name(iso3: str) -> dict[str, str]:
    """Bilingual name; an ISO3 outside the reference table is shown as its code, not guessed."""
    if iso3 == UNKNOWN_COUNTRY:
        return {"en": "No listing country (crypto, cash, unknown)", "fr": "Sans pays de cotation (crypto, liquidités, inconnu)"}
    c = COUNTRIES.get(iso3)
    return {"en": c.en, "fr": c.fr} if c else {"en": iso3, "fr": iso3}


def resolve_place_country(place: str | None) -> str | None:
    """ISO3 of the country named at the end of a source place string, else ``None``.

    ``"12 km W of Petrolia, CA"`` -> USA; ``"Bonin Islands, Japan region"`` -> JPN;
    ``"central Mid-Atlantic Ridge"`` -> None. Ambiguous names are rejected, never guessed.
    """
    if not place:
        return None
    tail = place.rsplit(",", 1)[-1].strip().lower()
    for suffix in (" region",):
        if tail.endswith(suffix):
            tail = tail[: -len(suffix)].strip()
    if tail in _AMBIGUOUS:
        return None
    if tail in _NAMES:
        return _NAMES[tail]
    if "," in place and tail in _US_STATES:
        return "USA"
    return None


def in_bbox(lat: float, lon: float, bbox: tuple[float, float, float, float]) -> bool:
    """``bbox`` = (minLon, minLat, maxLon, maxLat). A box whose minLon exceeds its maxLon crosses
    the dateline and is evaluated as two boxes (world SPEC §2)."""
    min_lon, min_lat, max_lon, max_lat = bbox
    if not min_lat <= lat <= max_lat:
        return False
    if min_lon <= max_lon:
        return min_lon <= lon <= max_lon
    return lon >= min_lon or lon <= max_lon
