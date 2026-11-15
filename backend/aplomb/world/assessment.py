"""Source evidence used to screen every globe record against the active holdings.

Country names and explicit corporate aliases come from the retained source fields.
Theme rules are disclosed relevance proxies. Coordinates alone never imply an
issuer relationship, and unknown geography stays unknown.
"""

from __future__ import annotations

import re

from .geo import UNKNOWN_COUNTRY, resolve_place_country
from .ingest import POLICY_THEMES, related_tickers

# FIPS country codes retained by GDELT are not ISO alpha-2. Only explicit,
# unambiguous mappings are used; other records can still resolve a source place.
GDELT_FIPS_COUNTRIES = {
    "US": "USA", "CA": "CAN", "UK": "GBR", "FR": "FRA", "GM": "DEU",
    "AS": "AUS", "NZ": "NZL", "JA": "JPN", "CH": "CHN", "RS": "RUS",
    "UP": "UKR", "IN": "IND", "PK": "PAK", "IT": "ITA", "SP": "ESP",
    "MX": "MEX", "BR": "BRA", "SF": "ZAF", "TU": "TUR", "KS": "KOR",
}
ELECTRICITY_DATASETS = {
    "energy_wri_plants", "world_energy_charts_de_power",
    "world_ember_monthly_generation_2026", "world_climate_trace_canada_electricity_co2",
}
THEME_RULES = {
    "ai": r"\bartificial intelligence\b",
    "semiconductors": r"\bsemiconductors?\b|\bchip manufacturing\b",
    "software": r"\bsoftware\b",
    "cloud": r"\bcloud computing\b",
    "ecommerce": r"\be[- ]commerce\b",
    "electric_vehicles": r"\belectric vehicles?\b",
    "banks": r"\bcommercial bank(?:ing|s)?\b|\bbanking sector\b",
    "insurance": r"\binsurance\b",
    "fossil_energy": r"\bcrude oil\b|\bpetroleum\b|\bnatural gas\b|\bcoal\b",
    "pipelines": r"\bpipelines?\b",
    "utilities": r"\bpower (?:plants?|stations?)\b|\belectricity generation\b",
    "rail_transport": r"\brail(?:way|road) transport\b",
    "healthcare": r"\bhealthcare\b|\bpharmaceuticals?\b",
    "esg_screened": r"\bgreenhouse gas\b|\bcarbon emissions\b|\bclimate change\b",
    "gold": r"\bgold (?:min(?:e|ing)|production|prices?|reserves?|bullion)\b|\bbullion\b",
    "crypto": r"\bbitcoin\b|\bcrypto(?:currency|currencies)?\b",
}
POLICY_WORDS = re.compile(r"\bpolicy rate\b|\binterest rate\b|\bfederal funds\b|\bfomc\b", re.I)


def source_context(record: dict, *, properties: dict | None = None) -> dict:
    """Return named tickers, disclosed theme proxies and source-supported countries."""
    props = properties or {}
    title = record.get("title", record.get("name", ""))
    source_id = record.get("datasetId", record.get("sourceId", ""))
    countries = set(record.get("relatedCountries") or []) - {UNKNOWN_COUNTRY}
    country = record.get("countryIso3") or (record.get("location") or {}).get("countryIso3")
    if country and country != UNKNOWN_COUNTRY:
        countries.add(country)
    for key in ("sourceLocationName", "place", "sourceCountry", "sourceCountryName", "country"):
        value = props.get(key)
        if isinstance(value, str):
            resolved = resolve_place_country(value)
            if resolved:
                countries.add(resolved)
    for value in props.get("sourceCountries") or []:
        if isinstance(value, str):
            resolved = resolve_place_country(value)
            if resolved:
                countries.add(resolved)
    if source_id.startswith("world_gdelt_"):
        mapped = GDELT_FIPS_COUNTRIES.get(props.get("sourceCountryFips"))
        if mapped:
            countries.add(mapped)

    # A registry's reported owner/company is a name mention, not proof of ownership
    # or a reviewed issuer-to-security relationship.
    names = [title]
    for value in (record.get("operator"), props.get("reportedOwner")):
        if isinstance(value, str):
            names.append(value)
    tickers = set(record.get("relatedTickers") or [])
    tickers.update(related_tickers(" ".join(names)))

    text_parts = [title]
    for key in ("primaryFuel", "sector", "product", "electricitySource", "productionType"):
        if isinstance(props.get(key), str):
            text_parts.append(props[key])
    text = " ".join(text_parts)
    themes = set(record.get("relatedThemes") or [])
    themes.update(theme for theme, pattern in THEME_RULES.items() if re.search(pattern, text, re.I))
    if isinstance(props.get("commodity"), str) and props["commodity"].casefold() == "gold":
        themes.add("gold")
    if source_id in ELECTRICITY_DATASETS:
        themes.add("utilities")
    if source_id == "energy_wri_plants" and props.get("primaryFuel") in {"Coal", "Gas", "Oil", "Petcoke"}:
        themes.add("fossil_energy")
    if POLICY_WORDS.search(title):
        for iso3 in countries:
            themes.update(POLICY_THEMES.get(iso3, ()))
    return {
        "relatedTickers": sorted(tickers),
        "relatedThemes": sorted(themes),
        "relatedCountries": sorted(countries),
    }
