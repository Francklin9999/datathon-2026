"""Dataset passports (schemas.md §12) and the starter-trap register (api.md §8.1).

Passports are built from the snapshot manifest: row counts, coverage, checks and their
``checkedAt`` come from the ingestion that actually ran. Static text below describes roles,
processing and availability rules. Datasets in the catalog that are not loaded are ``planned``
(data SPEC: "Register all optional datasets from the catalog as planned until loaded and
checked"). A passport is wire-shaped (camelCase dict) so T01's Pydantic model can validate it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .constants import (
    DATASET_IDS,
    LIM_CALENDAR_INTERSECTION,
    LIM_CNQ_FACTOR,
    LIM_ETF_NO_LOOKTHROUGH,
    LIM_FX_FFILL,
    LIM_MACRO_LAG_ASSUMED,
    LIM_MACRO_REVISED,
    LIM_NO_CONTROVERSY_DATA,
    LIM_SAMPLE_WINDOW,
    LIM_SECTOR_LABELS,
    LIM_SURVIVORSHIP,
    LIM_THEME_TAGS,
    LIM_YAHOO_NOT_CERTIFIED,
)
from .schemas import NORMALIZED, PLANNED_COLUMNS, Column

PASSPORT_KEYS: tuple[str, ...] = (
    "datasetId", "name", "role", "status", "source", "sourceUrl", "accessMethod", "licence", "licenceUrl",
    "retrievedOn", "coverage", "frequency", "rowCount", "dataVersion", "schema", "processing", "limitations",
    "availabilityRule", "checks", "rejectedReason",
)


def t(en: str, fr: str) -> dict[str, str]:
    return {"en": en, "fr": fr}


@dataclass(frozen=True)
class Descriptor:
    name: dict
    role: dict
    frequency: str
    access_method: str
    processing: tuple[dict, ...]
    limitations: tuple[str, ...]
    availability_rule: dict
    # For planned datasets only (loaded ones take these from the organizer metadata).
    planned_source: str = "Not selected yet"
    planned_owner: str = ""


_STARTER_FILE = {
    "assets_universe": "assets_universe.csv",
    "prices_daily": "prices_daily.csv",
    "corporate_actions": "corporate_actions.csv",
    "fx_usdcad_daily": "fx_usdcad_daily.csv",
    "macro_rates": "macro_rates.csv",
}

DESCRIPTORS: dict[str, Descriptor] = {
    "assets_universe": Descriptor(
        t("Asset universe", "Univers d'actifs"),
        t("List of assets Aplomb can analyse, with class, listing market, currency and sector.",
          "Liste des actifs qu'Aplomb peut analyser, avec classe, marché de cotation, devise et secteur."),
        "static",
        "local CSV (organizer starter pack)",
        (
            t("Header and closed lists validated; ticker and asset_id unique.",
              "En-tête et listes fermées validés; ticker et asset_id uniques."),
            t("Asset group derived from asset class (equity and equity ETFs -> equity, bond ETFs -> fixed income, gold ETF -> commodity, crypto -> crypto).",
              "Groupe d'actifs dérivé de la classe (actions et FNB d'actions -> actions, FNB obligataires -> revenu fixe, FNB d'or -> matières premières, crypto -> crypto)."),
            t("Country from listing market (TSX -> CAN, U.S. exchanges -> USA, crypto -> none). GICS sector kept only when the label is one of the 11 GICS names.",
              "Pays tiré du marché de cotation (TSX -> CAN, bourses américaines -> USA, crypto -> aucun). Secteur GICS conservé seulement si l'étiquette est l'un des 11 noms GICS."),
            t("ZST.TO is a bond ETF, not cash. Cash is modelled only by the CASH.CAD and CASH.USD pseudo-assets.",
              "ZST.TO est un FNB obligataire, pas de l'encaisse. L'encaisse est modélisée seulement par les pseudo-actifs CASH.CAD et CASH.USD."),
        ),
        (LIM_SURVIVORSHIP, LIM_SECTOR_LABELS, LIM_ETF_NO_LOOKTHROUGH, LIM_NO_CONTROVERSY_DATA),
        t("An asset is known from its first available price row. The selection itself was made in 2026 (survivorship).",
          "Un actif est connu à partir de sa première ligne de prix disponible. La sélection elle-même date de 2026 (biais du survivant)."),
    ),
    "prices_daily": Descriptor(
        t("Daily prices", "Prix quotidiens"),
        t("Adjusted closes used for every return, volatility, drawdown and stress figure.",
          "Clôtures ajustées utilisées pour chaque rendement, volatilité, perte maximale et test de crise."),
        "daily (trading days per market; crypto 7 days/week)",
        "local CSV (organizer starter pack)",
        (
            t("Rows kept exactly as reported: no forward-fill, no interpolation, no calendar alignment in storage.",
              "Lignes conservées telles quelles : aucun report, aucune interpolation, aucun alignement de calendrier au stockage."),
            t("adj_close (split- and dividend-adjusted) is used for returns; corporate actions are never re-applied (M_PRICE_ADJ_CLOSE).",
              "adj_close (ajusté pour fractionnements et dividendes) sert aux rendements; les opérations sur titres ne sont jamais réappliquées (M_PRICE_ADJ_CLOSE)."),
            t("Rejected at ingestion: duplicate (date, ticker), malformed dates, non-finite values, unknown ticker or currency, non-positive adjusted close.",
              "Rejeté à l'ingestion : doublons (date, ticker), dates invalides, valeurs non finies, ticker ou devise inconnus, clôture ajustée non positive."),
            t("Flagged and retained: zero volume, calendar mismatch, one-day moves above 40%, gaps above 5 days (1 for crypto), inconsistent OHLC.",
              "Signalé et conservé : volume nul, écart de calendrier, variations quotidiennes de plus de 40 %, trous de plus de 5 jours (1 pour la crypto), OHLC incohérent."),
            t("Master calendar = days with both an XIU.TO and a SPY price; crypto is sampled on those days (M_CAL_INTERSECTION).",
              "Calendrier maître = jours avec un prix XIU.TO et un prix SPY; la crypto est échantillonnée ces jours-là (M_CAL_INTERSECTION)."),
        ),
        (LIM_YAHOO_NOT_CERTIFIED, LIM_CALENDAR_INTERSECTION, LIM_CNQ_FACTOR, LIM_SURVIVORSHIP, LIM_SAMPLE_WINDOW),
        t("A TSX or U.S. row dated D is available from 21:00 UTC on D (16:00 EST close; one hour later than the close in summer). A crypto row dated D is available from 23:59:59.999 UTC on D, when its UTC day ends. An as-of date shows rows available before 00:00 UTC the next day. Adjusted closes are today's back-adjusted values, not the values published at the time.",
          "Une ligne TSX ou américaine datée J est disponible à partir de 21 h UTC le jour J (clôture de 16 h HNE; une heure après la clôture en été). Une ligne crypto datée J est disponible à 23 h 59 min 59,999 s UTC le jour J, à la fin de sa journée UTC. Une date de référence montre les lignes disponibles avant 0 h UTC le lendemain. Les clôtures ajustées sont les valeurs rajustées d'aujourd'hui, pas celles publiées à l'époque."),
    ),
    "corporate_actions": Descriptor(
        t("Dividends and splits", "Dividendes et fractionnements"),
        t("Reference annotations explaining adjusted prices; never applied to prices again.",
          "Annotations de référence qui expliquent les prix ajustés; jamais réappliquées aux prix."),
        "event",
        "local CSV (organizer starter pack)",
        (
            t("Ex-date normalized to a date; unit retained as reported.",
              "Date ex normalisée en date; unité conservée telle que publiée."),
            t("Split ratios that are not ordinary ratios are flagged (CNQ.TO 1.021 on 2022-08-22).",
              "Les ratios de fractionnement inhabituels sont signalés (CNQ.TO 1,021 le 2022-08-22)."),
        ),
        (LIM_CNQ_FACTOR, LIM_YAHOO_NOT_CERTIFIED),
        t("Readable from 00:00 UTC on the ex-date. Reference only.",
          "Lisible à partir de 0 h UTC à la date ex. Référence seulement."),
    ),
    "fx_usdcad_daily": Descriptor(
        t("USD/CAD exchange rate", "Taux de change USD/CAD"),
        t("Converts U.S.-dollar prices into Canadian dollars and back.",
          "Convertit les prix en dollars américains en dollars canadiens et inversement."),
        "business daily (Canadian business days)",
        "local CSV (organizer starter pack)",
        (
            t("Dates unique; rates finite and positive; cadusd checked against 1/usdcad.",
              "Dates uniques; taux finis et positifs; cadusd vérifié par rapport à 1/usdcad."),
            t("On a day without a published rate, conversion uses the last rate published before it, never a later one (M_FX_BOC_FFILL).",
              "Un jour sans taux publié, la conversion utilise le dernier taux publié avant ce jour, jamais un taux ultérieur (M_FX_BOC_FFILL)."),
        ),
        (LIM_FX_FFILL,),
        t("A rate dated D is available from 21:30 UTC on D (published around 16:30 Eastern time; stamp one hour late in summer). Reads may include the last available rate before the requested window.",
          "Un taux daté J est disponible à partir de 21 h 30 UTC le jour J (publié vers 16 h 30, heure de l'Est; une heure de retard en été). Une lecture peut inclure le dernier taux disponible avant la période demandée."),
    ),
    "macro_rates": Descriptor(
        t("Macro rates and inflation", "Taux et inflation"),
        t("Context for explanations and the rate-cycle scenario (policy rates, bond yields, CPI, unemployment).",
          "Contexte des explications et du scénario de cycle de taux (taux directeurs, rendements obligataires, IPC, chômage)."),
        "daily / monthly",
        "local CSV (organizer starter pack)",
        (
            t("Long format kept; one row per (reference date, series). Reference date kept separate from release and vintage times.",
              "Format long conservé; une ligne par (date de référence, série). La date de référence reste distincte des dates de publication et de millésime."),
            t("Series classes and revision status come from data/metadata/macro_series.csv, based on the organizer metadata.",
              "Classes de séries et statut de révision tirés de data/metadata/macro_series.csv, d'après les métadonnées des organisateurs."),
            t("Missing reference months are flagged, not filled (CPIAUCSL and UNRATE have no 2025-10 value in the starter file).",
              "Les mois de référence manquants sont signalés, pas comblés (CPIAUCSL et UNRATE n'ont pas de valeur 2025-10 dans le fichier de départ)."),
        ),
        (LIM_MACRO_REVISED, LIM_MACRO_LAG_ASSUMED, LIM_SAMPLE_WINDOW),
        t("Current runs: a real release time when loaded; otherwise (assumption A-22) daily values are usable from the next business day and monthly values 45 days after the end of their reference month. Historical runs: monthly values need a real release date, and revised series (FRED, latest vintage) also need the vintage date of the stored value; without them the row is withheld. Nothing is carried back from a later observation.",
          "Exécutions courantes : heure de publication réelle si chargée; sinon (hypothèse A-22) les valeurs quotidiennes sont utilisables le jour ouvrable suivant et les valeurs mensuelles 45 jours après la fin de leur mois de référence. Exécutions historiques : une valeur mensuelle exige une vraie date de publication, et une série révisée (FRED, dernier millésime) exige aussi la date du millésime stocké; sinon la ligne est retenue. Rien n'est reporté à partir d'une observation ultérieure."),
    ),
    "asset_themes": Descriptor(
        t("Theme tags", "Étiquettes thématiques"),
        t("Links assets to themes such as AI, banks or gold for exposure goals and alternatives.",
          "Relie les actifs à des thèmes comme l'IA, les banques ou l'or pour les objectifs d'exposition et les solutions de rechange."),
        "static (team assignment)",
        "local CSV (team metadata, data/metadata/asset_themes.csv)",
        (
            t("One row per (ticker, theme) with a one-line justification; tags restricted to the catalog list.",
              "Une ligne par (ticker, thème) avec une justification d'une ligne; étiquettes limitées à la liste du catalogue."),
            t("Assignments rest on the organizer universe file (names and sectors) and team judgement; they are assumptions, not an official classification.",
              "Les attributions reposent sur le fichier d'univers des organisateurs (noms et secteurs) et le jugement de l'équipe; ce sont des hypothèses, pas une classification officielle."),
        ),
        (LIM_THEME_TAGS,),
        t("Current runs: always readable. Historical runs: readable only after the assignment date, because a 2026 team assignment is not historical evidence.",
          "Exécutions courantes : toujours lisibles. Exécutions historiques : lisibles seulement après la date d'attribution, car une attribution d'équipe de 2026 n'est pas une preuve historique."),
    ),
    "default_profiles": Descriptor(
        t("Default personas", "Personas par défaut"),
        t("The three fictional investors (Amira, Mateo, Robert), their portfolios and rules.",
          "Les trois investisseurs fictifs (Amira, Mateo, Robert), leurs portefeuilles et leurs règles."),
        "static",
        "provided by the profiles module (T06)",
        (t("Registered by T06; not ingested by the datastore.", "Enregistré par T06; non ingéré par le magasin de données."),),
        ("LIM_SIMULATION_ONLY",),
        t("Fictional assumptions; not time-gated.", "Hypothèses fictives; non filtrées dans le temps."),
        planned_source="backend/aplomb/profiles (T06), fictional personas (A-13)",
        planned_owner="T06",
    ),
    "macro_release_dates": Descriptor(
        t("Macro release dates", "Dates de publication macro"),
        t("Actual publication and vintage times of monthly macro values, needed for point-in-time Time Machine runs.",
          "Heures réelles de publication et de millésime des valeurs macro mensuelles, nécessaires aux exécutions historiques."),
        "event",
        "planned: official release calendars and vintage archives (O-05)",
        (t("Not loaded: no source selected yet (O-05).", "Non chargé : aucune source choisie (O-05)."),),
        (LIM_MACRO_LAG_ASSUMED,),
        t("A record is available from its publication time.", "Un enregistrement est disponible à partir de son heure de publication."),
        planned_source="Not selected yet (open item O-05)",
        planned_owner="T04",
    ),
    "etf_holdings": Descriptor(
        t("ETF holdings", "Composition des FNB"),
        t("Fund constituents and weights for optional look-through exposure.", "Titres et pondérations des fonds pour la transparence facultative."),
        "per issuer report",
        "planned: issuer holdings files (per-fund URL required)",
        (t("Not loaded.", "Non chargé."),),
        (LIM_ETF_NO_LOOKTHROUGH,),
        t("Available from the issuer publication time; partial coverage preserved.", "Disponible à partir de la publication de l'émetteur; couverture partielle conservée."),
        planned_source="ETF issuer holdings documents (planned, T09)",
        planned_owner="T09",
    ),
    "world_events": Descriptor(
        t("World events", "Événements mondiaux"),
        t("Geolocated events for the World Explorer.", "Événements géolocalisés pour l'explorateur mondial."),
        "batch",
        "planned: cached GDELT batch, official releases, curated set",
        (t("Not loaded.", "Non chargé."),),
        (),
        t("Occurrence, publication and retrieval times kept separate.", "Heures d'occurrence, de publication et de récupération distinctes."),
        planned_source="GDELT and official releases (planned, T11)",
        planned_owner="T11",
    ),
    "attention_pageviews": Descriptor(
        t("Wikipedia page views", "Consultations Wikipédia"),
        t("Public-attention signal (hype meter), informational only.", "Signal d'attention du public (indice d'engouement), à titre informatif."),
        "daily",
        "planned: Wikimedia analytics API",
        (t("Not loaded.", "Non chargé."),),
        ("LIM_ATTENTION_PROXY",),
        t("A day's count is available after that UTC day ends.", "Le décompte d'un jour est disponible après la fin de ce jour UTC."),
        planned_source="Wikimedia analytics API (planned, T09)",
        planned_owner="T09",
    ),
    "emissions_facilities": Descriptor(
        t("Facility emissions", "Émissions des installations"),
        t("Government-reported facility emissions (ECCC, EPA) for the globe layer.", "Émissions déclarées des installations (ECCC, EPA) pour la couche du globe."),
        "annual",
        "planned: ECCC and EPA GHGRP downloads",
        (t("Not loaded.", "Non chargé."),),
        ("LIM_REGISTRY_MATCH",),
        t("Available from the registry publication date.", "Disponible à partir de la date de publication du registre."),
        planned_source="ECCC GHG reporting and EPA GHGRP (planned, T11)",
        planned_owner="T11",
    ),
    "natural_hazards": Descriptor(
        t("Natural hazards", "Aléas naturels"),
        t("Earthquakes and wildfire detections for the globe layer.", "Séismes et feux détectés pour la couche du globe."),
        "near real time",
        "planned: USGS feeds, NASA FIRMS",
        (t("Not loaded.", "Non chargé."),),
        (),
        t("Available from the feed publication time.", "Disponible à partir de l'heure de publication du flux."),
        planned_source="USGS earthquake feeds and NASA FIRMS (planned, T11)",
        planned_owner="T11",
    ),
    "research_documents": Descriptor(
        t("Research documents", "Documents de recherche"),
        t("Cached text of documents cited as evidence.", "Texte en cache des documents cités en preuve."),
        "on demand",
        "planned: research adapters cache",
        (t("Not loaded.", "Non chargé."),),
        ("LIM_EVIDENCE_TIER",),
        t("Publication date kept separately from retrieval; unknown publication dates are not invented.",
          "Date de publication distincte de la récupération; une date inconnue n'est pas inventée."),
        planned_source="Research adapters (planned, T09)",
        planned_owner="T09",
    ),
    "filings_index": Descriptor(
        t("SEC filings index", "Index des dépôts SEC"),
        t("Filing metadata fetched by the researcher.", "Métadonnées des dépôts récupérées par le chercheur."),
        "on demand",
        "planned: SEC EDGAR APIs",
        (t("Not loaded.", "Non chargé."),),
        (),
        t("Available from the filing date.", "Disponible à partir de la date de dépôt."),
        planned_source="SEC EDGAR APIs (planned, T09)",
        planned_owner="T09",
    ),
}

_URL = re.compile(r"https?://[^\s;,)]+")


def _schema(columns: tuple[Column, ...]) -> list[dict]:
    return [{"name": c.name, "type": c.type, "description": c.description} for c in columns if not c.name.startswith("available_at")]


def build_passport(dataset_id: str, manifest: dict | None) -> dict:
    """Wire-shaped DatasetPassport for one catalog dataset under a manifest (or none)."""
    desc = DESCRIPTORS[dataset_id]
    loaded = manifest is not None and dataset_id in manifest.get("datasets", {})
    if not loaded:
        columns = PLANNED_COLUMNS.get(dataset_id, ())
        return {
            "datasetId": dataset_id, "name": desc.name, "role": desc.role, "status": "planned",
            "source": desc.planned_source, "sourceUrl": None, "accessMethod": desc.access_method,
            "licence": "unknown (not yet reviewed)", "licenceUrl": None, "retrievedOn": None, "coverage": None,
            "frequency": desc.frequency, "rowCount": None, "dataVersion": None, "schema": _schema(columns),
            "processing": list(desc.processing), "limitations": list(desc.limitations),
            "availabilityRule": desc.availability_rule, "checks": [], "rejectedReason": None,
        }
    meta = manifest["datasets"][dataset_id]
    source, source_url, licence, licence_url, retrieved = _provenance(dataset_id, manifest)
    processing = list(desc.processing)
    if manifest.get("onDemand") and dataset_id in ("assets_universe", "prices_daily"):
        for od in manifest["onDemand"]:
            processing.append(t(
                f"On-demand asset {od['ticker']} appended from {od['provider']} (retrieved {od['retrievedAt']}).",
                f"Actif à la demande {od['ticker']} ajouté depuis {od['provider']} (récupéré le {od['retrievedAt']})."))
    coverage = None
    if meta.get("firstDate") and meta.get("lastDate"):
        coverage = {"start": meta["firstDate"], "end": meta["lastDate"]}
    return {
        "datasetId": dataset_id, "name": desc.name, "role": desc.role, "status": "in_use",
        "source": source, "sourceUrl": source_url, "accessMethod": desc.access_method,
        "licence": licence, "licenceUrl": licence_url, "retrievedOn": retrieved, "coverage": coverage,
        "frequency": desc.frequency, "rowCount": meta["rowCount"], "dataVersion": manifest["dataVersion"],
        "schema": _schema(NORMALIZED[dataset_id].columns), "processing": processing,
        "limitations": list(desc.limitations), "availabilityRule": desc.availability_rule,
        "checks": [dict(c) for c in meta["checks"]], "rejectedReason": None,
    }


def _provenance(dataset_id: str, manifest: dict) -> tuple[str, str | None, str, str | None, str | None]:
    if dataset_id == "asset_themes":
        dates = manifest["datasets"]["asset_themes"].get("details", {}).get("assignedAt", [])
        return ("Aplomb team assignment (assumptions) based on the organizer universe file", None,
                "Team-authored metadata; no third-party content", None, max(dates) if dates else None)
    if dataset_id == "macro_release_dates":
        return ("Team-supplied release calendar (see sourceUrl per row)", None, "per row source", None, None)
    rows = manifest.get("sourceMetadata", {}).get(_STARTER_FILE[dataset_id], [])
    if not rows:
        return ("unknown", None, "unknown", None, None)
    if len(rows) == 1:
        r = dict(rows[0])
        same = re.match(r"^Same as (\S+\.csv)$", r["terms_of_use"].strip())
        if same and len(manifest["sourceMetadata"].get(same.group(1), [])) == 1:
            r["terms_of_use"] = manifest["sourceMetadata"][same.group(1)][0]["terms_of_use"]
        url = r["source_url"] if r["source_url"].startswith("http") else None
        lic_urls = _URL.findall(r["terms_of_use"])
        source = r["source"]
        if manifest.get("onDemand") and dataset_id in ("assets_universe", "prices_daily"):
            providers = sorted({od["provider"] for od in manifest["onDemand"]})
            source += "; on-demand additions: " + ", ".join(providers)
        return (source, url, r["terms_of_use"], lic_urls[0] if len(lic_urls) == 1 else None, r["retrieved_on"] or None)
    # Several publishers for one file (macro_rates: Bank of Canada and FRED).
    source = "; ".join(f"{r['source']} ({r['source_url']})" for r in rows)
    licence = "; ".join(r["terms_of_use"] for r in rows)
    retrieved = sorted({r["retrieved_on"] for r in rows if r["retrieved_on"]})
    return (source, None, licence, None, retrieved[-1] if len(retrieved) == 1 else None)


def build_passports(manifest: dict | None) -> list[dict]:
    return [build_passport(ds_id, manifest) for ds_id in DATASET_IDS]


# Starter pitfalls (data/SOURCES.md "Pitfalls mapped to implementation"), for GET /datasets.
# Statuses reflect what this repository has verified: "handled" only where a datastore test
# covers the treatment. Owners flip "open" to "handled" when their listed tests pass.
TRAPS: tuple[dict, ...] = (
    {"code": LIM_FX_FFILL, "status": "open",
     "handledBy": "CAD/USD mismatch and FX holiday gaps: the datastore returns only the last rate published on or before a day, never a later one (tested); conversion of every USD figure is quant M_FX_BOC_FFILL (T05), pending QNT-01/QNT-06."},
    {"code": LIM_CALENDAR_INTERSECTION, "status": "handled",
     "handledBy": "Master calendar XIU.TO ∩ SPY with crypto sampled on those days and no price fill (datastore DS-02, DS-07)."},
    {"code": LIM_YAHOO_NOT_CERTIFIED, "status": "disclosed",
     "handledBy": "adj_close used as published; splits and dividends are annotations and never re-applied; checksums pin the snapshot. Original price vintages are not available."},
    {"code": LIM_CNQ_FACTOR, "status": "disclosed",
     "handledBy": "Split anomaly flagged at ingestion; limitation attached to CNQ.TO reads spanning 2022-08-22; not applied twice."},
    {"code": LIM_MACRO_LAG_ASSUMED, "status": "open",
     "handledBy": "No real release dates loaded (O-05): current runs use the A-22 lag; historical runs withhold monthly values."},
    {"code": LIM_MACRO_REVISED, "status": "disclosed",
     "handledBy": "FRED values are latest vintages; withheld from historical runs unless vintage dates are supplied."},
    {"code": LIM_SURVIVORSHIP, "status": "disclosed",
     "handledBy": "Universe selected in 2026; disclosed on every universe and price passport."},
    {"code": LIM_NO_CONTROVERSY_DATA, "status": "disclosed",
     "handledBy": "No ESG, news or fundamentals dataset loaded; evidence rules stay 'insufficient data'."},
    {"code": LIM_ETF_NO_LOOKTHROUGH, "status": "disclosed",
     "handledBy": "Funds are single diversified positions; sector and single-name caps use direct equities only."},
)


def traps() -> list[dict]:
    return [dict(x) for x in TRAPS]
