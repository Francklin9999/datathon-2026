"""Dataset passports (schemas.md §12) and the starter-trap register (api.md §8.1).

Passports are built from the snapshot manifest: row counts, coverage, checks and their
``checkedAt`` come from the ingestion that actually ran. Static text below describes roles,
processing and availability rules. Datasets in the catalog that are not loaded are ``planned``
(data SPEC: "Register all optional datasets from the catalog as planned until loaded and
checked"). ``default_profiles`` is not part of a snapshot: its passport is built from the personas
file shipped with the application, read and checked when the passport is built.
A passport is wire-shaped (camelCase dict) so T01's Pydantic model can validate it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

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
from .timeutil import utc_now_iso

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
    # Set where the text above describes the loaded dataset; a planned passport shows these instead.
    planned_access_method: str | None = None
    planned_processing: tuple[dict, ...] | None = None


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
    "fx_boc_global": Descriptor(
        t("Bank of Canada global FX", "Devises mondiales de la Banque du Canada"),
        t("Indicative daily Canadian-dollar exchange rates for available currencies.", "Taux de change indicatifs quotidiens en dollars canadiens."),
        "daily", "Bank of Canada Valet API, captured snapshot",
        (t("CAD per one currency unit. Cross rates divide the two CAD quotes; missing observations are never invented.",
           "CAD par unité de devise. Les taux croisés divisent les deux taux en CAD; les observations manquantes ne sont pas inventées."),
         t("Rates are indicative averages and may be revised or delayed.", "Taux indicatifs moyens, susceptibles de révision ou de retard.")),
        (LIM_FX_FFILL,),
        t("Current mode assumes publication by 21:30 UTC on the observation date; historic mode withholds rows before the actual capture because original vintages are unavailable.",
          "En mode courant, publication présumée à 21 h 30 UTC le jour observé; le mode historique exclut les lignes avant la capture faute de millésimes originaux."),
        planned_source="Bank of Canada Valet (not loaded)"),
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
        "local JSON shipped with the application (backend/aplomb/profiles/defaults.json)",
        (
            t("Read from the personas file shipped with the application; not part of the data snapshot, so it carries no data version.",
              "Lu dans le fichier de personas livré avec l'application; hors de l'instantané de données, donc sans version de données."),
            t("Persona descriptions follow the organizer brief (pages 5 to 7); portfolios, capital amounts and rule thresholds are fictional team assumptions (A-13).",
              "Les descriptions des personas suivent l'énoncé des organisateurs (pages 5 à 7); les portefeuilles, les capitaux et les seuils des règles sont des hypothèses fictives de l'équipe (A-13)."),
        ),
        ("LIM_SIMULATION_ONLY",),
        t("Fictional assumptions; not time-gated.", "Hypothèses fictives; non filtrées dans le temps."),
        planned_source="backend/aplomb/profiles (T06), fictional personas (A-13)",
        planned_owner="T06",
        planned_access_method="provided by the profiles module (T06)",
        planned_processing=(t("Personas file not readable; nothing is ingested by the datastore.",
                              "Fichier de personas illisible; rien n'est ingéré par le magasin de données."),),
    ),
    "macro_release_dates": Descriptor(
        t("Macro release dates", "Dates de publication macro"),
        t("Actual publication and vintage times of monthly macro values, needed for point-in-time Time Machine runs.",
          "Heures réelles de publication et de millésime des valeurs macro mensuelles, nécessaires aux exécutions historiques."),
        "event",
        "local CSV (team metadata, data/metadata/macro_release_dates.csv)",
        (
            t("One row per (series, reference month) with the release date and the URL of the release; each row must match a macro_rates observation and cannot precede its reference date.",
              "Une ligne par (série, mois de référence) avec la date de publication et l'URL de la publication; chaque ligne doit correspondre à une observation de macro_rates et ne peut précéder sa date de référence."),
            t("A monthly series without a row here has no real release date: current runs use the assumed lag (A-22) and historical runs withhold its values.",
              "Une série mensuelle sans ligne ici n'a pas de vraie date de publication : les exécutions courantes utilisent le délai supposé (A-22) et les exécutions historiques retiennent ses valeurs."),
        ),
        (LIM_MACRO_LAG_ASSUMED,),
        t("A record is available from its publication time.", "Un enregistrement est disponible à partir de son heure de publication."),
        planned_source="Not selected yet (open item O-05)",
        planned_owner="T04",
        planned_access_method="planned: official release calendars and vintage archives (O-05)",
        planned_processing=(t("Not loaded: no source selected yet (O-05).", "Non chargé : aucune source choisie (O-05)."),),
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
    "world_airports": Descriptor(
        t("OurAirports reference", "Référence OurAirports"),
        t("Large scheduled-service airport coordinates.", "Coordonnées des grands aéroports avec service régulier."),
        "batch", "versioned public CSV capture",
        (t("Current static reference only.", "Référence statique actuelle seulement."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time; original publication date unknown.", "Date de capture; publication originale inconnue."),
        planned_source="OurAirports; separate verified reference snapshot required"),
    "world_bank_indicators": Descriptor(
        t("World Bank country indicators", "Indicateurs nationaux de la Banque mondiale"),
        t("Annual worldwide economic context, separate from price history.", "Contexte économique mondial annuel, distinct des prix historiques."),
        "annual", "versioned public API capture",
        (t("Available only when the separately verified country snapshot is loaded.", "Disponible seulement lorsque l'instantané national vérifié est chargé."),),
        ("LIM_MACRO_REVISED",),
        t("Capture establishes availability; not an original historical vintage.", "La capture établit la disponibilité; ce n'est pas un millésime historique original."),
        planned_source="World Bank WDI; separate country snapshot not loaded in this datastore"),
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
    "world_aviation_weather": Descriptor(
        t("Aviation weather", "Météo aéronautique"),
        t("Bounded airport station observations.", "Observations bornées de stations aéroportuaires."),
        "batch", "versioned public API capture",
        (t("Only captured stations are represented.", "Seules les stations capturées sont représentées."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability.", "La capture établit la disponibilité."),
        planned_source="Aviation Weather Center; separate verified world capture"),
    "world_noaa_alerts": Descriptor(
        t("NOAA weather alerts", "Alertes météo NOAA"),
        t("Official United States weather alerts with source geometry.", "Alertes météo officielles des États-Unis avec géométrie source."),
        "batch", "versioned public API capture",
        (t("The capture is bounded and United States only.", "La capture est bornée et limitée aux États-Unis."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability.", "La capture établit la disponibilité."),
        planned_source="NOAA; separate verified world capture"),
    "world_gdacs_alerts": Descriptor(
        t("GDACS disaster alerts", "Alertes de catastrophe GDACS"),
        t("Bounded worldwide disaster alert records.", "Enregistrements mondiaux bornés d'alertes de catastrophe."),
        "batch", "versioned public API capture",
        (t("Representative coordinates are not impact footprints.", "Les coordonnées représentatives ne sont pas des emprises d'impact."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability.", "La capture établit la disponibilité."),
        planned_source="GDACS; separate verified world capture"),
    "world_usgs_geojson": Descriptor(
        t("USGS weekly earthquakes", "Séismes hebdomadaires de l'USGS"),
        t("Weekly captured earthquake epicenters with magnitude 4.5 to below 6.",
          "Épicentres de séismes hebdomadaires de magnitude 4,5 à moins de 6."),
        "batch", "versioned public GeoJSON capture",
        (t("Epicenter points do not show affected areas, damage or issuer exposure.",
           "Les épicentres ne montrent ni zones touchées, ni dommages, ni exposition d'émetteurs."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; USGS events may be revised.",
          "La capture établit la disponibilité; les événements de l'USGS peuvent être révisés."),
        planned_source="US Geological Survey; separate verified world capture"),
    "world_nasa_power": Descriptor(
        t("NASA POWER temperature", "Température NASA POWER"),
        t("Daily gridded temperature at six requested locations.", "Température maillée quotidienne à six lieux demandés."),
        "batch", "versioned public API capture",
        (t("Sample points and local solar dates are not global station coverage.", "Les points échantillons et dates solaires locales ne sont pas une couverture mondiale de stations."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability.", "La capture établit la disponibilité."),
        planned_source="NASA POWER; separate verified world capture"),
    "world_climate_trace_canada_electricity_co2": Descriptor(
        t("Climate TRACE Canada electricity CO2", "CO2 de l'électricité canadienne Climate TRACE"),
        t("Monthly 2025 Canada electricity-generation CO2 estimates.",
          "Estimations mensuelles du CO2 de la production d'électricité canadienne en 2025."),
        "batch", "versioned public API capture",
        (t("Modeled national estimates may be revised; no facility coordinates or issuer relationships.",
           "Les estimations nationales modélisées peuvent être révisées; aucun lieu d'installation ou lien d'émetteur."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; monthly dates are display anchors.",
          "La capture établit la disponibilité; les dates mensuelles sont des repères d'affichage."),
        planned_source="Climate TRACE; separate verified world capture"),
    "world_epa_sems_sites": Descriptor(
        t("EPA SEMS sites", "Sites SEMS de l'EPA"),
        t("Bounded official site location references in six US states.", "Références officielles bornées de sites dans six États américains."),
        "batch", "versioned public API capture",
        (t("A site listing does not establish current contamination, emissions, or an issuer link.",
           "Une inscription de site ne démontre ni contamination actuelle, ni émissions, ni lien avec un émetteur."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability.", "La capture établit la disponibilité."),
        planned_source="EPA Envirofacts SEMS; separate verified world capture"),
    "world_federal_register": Descriptor(
        t("Federal Register documents", "Documents du Federal Register"),
        t("United States policy publication observations.", "Observations de publications réglementaires des États-Unis."),
        "batch", "versioned public API capture",
        (t("Jurisdiction location does not prove a company effect.", "Le lieu de juridiction ne démontre aucun effet sur une entreprise."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability.", "La capture établit la disponibilité."),
        planned_source="Federal Register; separate verified world capture"),
    "world_ecb_press": Descriptor(
        t("ECB press releases", "Communiqués de presse de la BCE"),
        t("Current ECB RSS press release titles, dates and links.", "Titres, dates et liens des communiqués de presse du flux RSS actuel de la BCE."),
        "batch", "versioned public RSS capture",
        (t("The current feed is not a complete archive.", "Le flux actuel n'est pas une archive complète."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability.", "La capture établit la disponibilité."),
        planned_source="European Central Bank; separate verified world capture"),
    "world_uk_sanctions_updates": Descriptor(
        t("UK Sanctions List updates", "Mises à jour de la liste des sanctions du Royaume-Uni"),
        t("Bounded publication change notes for the UK Sanctions List.", "Notes de modification bornées de la publication de la liste des sanctions du Royaume-Uni."),
        "batch", "versioned public API capture",
        (t("Update notes are not the current list of designated persons, vessels or entities.",
           "Les notes de mise à jour ne constituent pas la liste actuelle des personnes, navires ou entités désignés."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability.", "La capture établit la disponibilité."),
        planned_source="UK government; separate verified world capture"),
    "world_usgs_minerals": Descriptor(
        t("USGS mineral production", "Production minérale de l'USGS"),
        t("Selected annual country mine-production estimates.", "Estimations annuelles sélectionnées de production minière par pays."),
        "annual", "versioned public data release capture",
        (t("Country totals are not mine locations or company output.",
           "Les totaux nationaux ne sont ni des emplacements de mines ni la production d'entreprises."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; source estimates may be revised.",
          "La capture établit la disponibilité; les estimations de la source peuvent être révisées."),
        planned_source="USGS Mineral Commodity Summaries; separate verified world capture"),
    "world_fda_drug_enforcement_counts": Descriptor(
        t("FDA drug enforcement record counts", "Nombre de dossiers réglementaires de médicaments FDA"),
        t("Four classification counts for a bounded 2026 report-date window.",
          "Quatre dénombrements par classification sur une période bornée de dates de rapport en 2026."),
        "batch", "versioned public openFDA aggregate capture",
        (t("Matching records are not unique recalls or current recall alerts; no product distribution geography.",
           "Les dossiers correspondants ne sont ni des rappels uniques ni des alertes actuelles; aucune géographie de distribution."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; FDA records may be revised.",
          "La capture établit la disponibilité; les dossiers FDA peuvent être révisés."),
        planned_source="U.S. Food and Drug Administration; separate verified world capture"),
    "world_crossref_climate_bibliography": Descriptor(
        t("Crossref climate bibliography sample", "Échantillon bibliographique climatique Crossref"),
        t("Five projected 2024 journal-article metadata records matching a climate-title query.",
          "Cinq notices de métadonnées d'articles de 2024 issues d'une requête de titres climatiques."),
        "batch", "versioned public Crossref metadata capture",
        (t("One relevance-ranked page; titles and deposited dates do not establish scientific validity or geography.",
           "Une page classée par pertinence; titres et dates déposées ne prouvent ni validité scientifique ni géographie."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; publication date parts preserve source precision.",
          "La capture établit la disponibilité; les éléments de date de publication conservent la précision source."),
        planned_source="Crossref; separate verified world capture"),
    "world_ted_published_notice_metadata": Descriptor(
        t("TED published procurement notice sample", "Échantillon d'avis de marchés publics TED"),
        t("Five published notice numbers, publication dates and source-reported buyer countries.",
          "Cinq numéros d'avis publiés, dates de publication et pays des acheteurs déclarés par la source."),
        "batch", "versioned public TED Search API metadata capture",
        (t("First page only; buyer country is not contract performance geography. No coordinates, awards or spending inferred.",
           "Première page seulement; le pays de l'acheteur n'est pas le lieu d'exécution. Aucune coordonnée, attribution ou dépense inférée."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; source publication dates have day precision.",
          "La capture établit la disponibilité; les dates de publication source ont une précision au jour."),
        planned_source="European Union Publications Office, TED; separate verified world capture"),
    "world_wikimedia_topic_pageviews": Descriptor(
        t("Wikimedia topic pageviews", "Pages vues par sujet Wikimedia"),
        t("Seven daily English Wikipedia article counts for Canada, Japan and Brazil.",
          "Sept dénombrements quotidiens des articles Wikipédia en anglais sur le Canada, le Japon et le Brésil."),
        "daily", "versioned public Wikimedia Analytics API capture",
        (t("Pageviews are not unique readers, sentiment or event confirmation; topic is not reader geography.",
           "Les pages vues ne sont ni des lecteurs uniques, ni un sentiment, ni une confirmation d'événement; le sujet n'indique pas la géographie des lecteurs."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; daily UTC timestamps are reporting-period anchors.",
          "La capture établit la disponibilité; les heures UTC quotidiennes sont des repères de période."),
        planned_source="Wikimedia Analytics API; CC0 numeric analytics capture"),
    "world_wikipedia_recent_changes": Descriptor(
        t("Wikipedia recent article edits", "Modifications récentes d'articles Wikipédia"),
        t("Ten factual English Wikipedia main-namespace edit metadata records.",
          "Dix notices factuelles de modifications d'articles Wikipédia en anglais."),
        "captured page", "versioned public Wikimedia API capture",
        (t("Edits are not confirmed news events; article titles do not establish location or issuer relationships.",
           "Les modifications ne sont pas des événements confirmés; les titres ne prouvent ni lieu ni relation avec un émetteur."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; edit timestamps are source activity times.",
          "La capture établit la disponibilité; les horodatages indiquent l'activité de la source."),
        planned_source="Wikimedia API; separate verified factual metadata capture"),
    "world_bls_us_cpi_2024": Descriptor(
        t("U.S. BLS 2024 consumer price index", "Indice des prix à la consommation des États-Unis 2024"),
        t("Twelve monthly CPI-U all-items index values for the United States.",
          "Douze valeurs mensuelles de l'indice CPI-U tous articles pour les États-Unis."),
        "monthly", "versioned public BLS API capture",
        (t("Index values are not monthly inflation rates; one series and one year only.",
           "Les valeurs de l'indice ne sont pas des taux d'inflation mensuels; une seule série et une seule année."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; source periods have month precision.",
          "La capture établit la disponibilité; les périodes source ont une précision mensuelle."),
        planned_source="U.S. Bureau of Labor Statistics; separate verified world capture"),
    "world_ilo_unemployment_2024": Descriptor(
        t("ILOSTAT 2024 unemployment rate", "Taux de chômage ILOSTAT 2024"),
        t("Annual unemployment rate for Canada, Japan and Brazil, total sex and age 15 or older.",
          "Taux de chômage annuel au Canada, au Japon et au Brésil, tous sexes et à partir de 15 ans."),
        "annual", "versioned public ILOSTAT CSV API capture",
        (t("Three countries and one year only; survey methods differ and SDMX transport is not covered.",
           "Trois pays et une année seulement; les enquêtes diffèrent et le transport SDMX n'est pas couvert."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; January 1 is an annual display anchor.",
          "La capture établit la disponibilité; le 1er janvier est un repère d'affichage annuel."),
        planned_source="International Labour Organization, ILOSTAT; CC BY 4.0 adaptation"),
    "world_bank_sdmx_gdp_2024": Descriptor(
        t("World Bank SDMX 2024 nominal GDP", "PIB nominal 2024 de la Banque mondiale via SDMX"),
        t("Annual GDP in current U.S. dollars for Canada, Japan and Brazil.",
          "PIB annuel en dollars américains courants au Canada, au Japon et au Brésil."),
        "annual", "versioned public World Bank SDMX capture",
        (t("Three countries and one indicator/year only; nominal level is not real growth.",
           "Trois pays et un indicateur/année seulement; le niveau nominal n'est pas une croissance réelle."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; January 1 is an annual display anchor.",
          "La capture établit la disponibilité; le 1er janvier est un repère d'affichage annuel."),
        planned_source="World Bank WDI SDMX; CC BY 4.0 with additional dataset terms"),
    "world_energy_charts_de_power": Descriptor(
        t("Germany selected electricity production power", "Puissance de production électrique choisie en Allemagne"),
        t("Fifteen-minute German national power values for four selected generation types.",
          "Valeurs nationales allemandes de puissance aux quinze minutes pour quatre types de production."),
        "15-minute", "versioned public Energy-Charts API capture",
        (t("One day and four types only; MW power is not MWh energy or plant-level production.",
           "Un jour et quatre types seulement; la puissance MW n'est ni l'énergie MWh ni la production d'une centrale."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; source intervals are reference periods.",
          "La capture établit la disponibilité; les intervalles source sont des périodes de référence."),
        planned_source="Fraunhofer ISE Energy-Charts; CC BY 4.0 selected capture"),
    "world_nasa_gibs_modis_tile": Descriptor(
        t("NASA GIBS MODIS overview tile", "Tuile d'aperçu MODIS de NASA GIBS"),
        t("One browse image reference and source tile footprint.",
          "Une référence d'image de consultation et l'empreinte de la tuile source."),
        "single captured tile", "versioned public NASA GIBS capture",
        (t("Footprint is not a cloud-free observation; full raster overlay is not implemented.",
           "L'empreinte ne prouve pas une observation sans nuage; la couche raster complète n'est pas réalisée."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; tile date is a source reference date.",
          "La capture établit la disponibilité; la date de la tuile est une date de référence."),
        planned_source="NASA Global Imagery Browse Services; separate verified capture"),
    "world_nominatim_eiffel_lookup": Descriptor(
        t("Cached Nominatim Eiffel Tower place", "Lieu Tour Eiffel en cache Nominatim"),
        t("One permanent Paris landmark lookup with source place metadata.",
          "Une recherche permanente d'un site parisien avec les métadonnées du lieu."),
        "static sample", "versioned ODbL Nominatim capture",
        (t("Single cached lookup; no public geocoder service, place coverage or operator assertion.",
           "Une seule recherche en cache; aucun service de géocodage public ni affirmation d'exploitant."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; OSM edits are not event times.",
          "La capture établit la disponibilité; les modifications OSM ne datent pas un événement."),
        planned_source="OpenStreetMap Nominatim; separate ODbL derived database"),
    "world_osm_eiffel_tower": Descriptor(
        t("OpenStreetMap Eiffel Tower footprint", "Empreinte Tour Eiffel OpenStreetMap"),
        t("One mapped landmark footprint and source identifiers.",
          "Une empreinte de site cartographié et ses identifiants source."),
        "static sample", "versioned ODbL OpenStreetMap API capture",
        (t("Single mapped landmark; no broad infrastructure coverage or verified operator link.",
           "Un seul site cartographié; aucune couverture générale ni relation vérifiée avec un exploitant."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; OSM edits are not event times.",
          "La capture établit la disponibilité; les modifications OSM ne datent pas un événement."),
        planned_source="OpenStreetMap API; separate ODbL derived database"),
    "world_global_carbon_budget_2026": Descriptor(
        t("Global Carbon Budget 2026 selected components", "Composantes choisies du budget carbone mondial 2026"),
        t("Seven annual global carbon-budget components for 1959 through 2025, GtC per year.",
          "Sept composantes annuelles mondiales de 1959 à 2025, en GtC par an."),
        "annual", "versioned ICOS Global Carbon Project workbook",
        (t("Revised global estimates; GtC is not GtCO2, and no country or facility is identified.",
           "Estimations mondiales révisées; GtC n'est pas GtCO2 et aucun pays ni installation n'est identifié."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; year starts are display anchors for revised estimates.",
          "La capture établit la disponibilité; le début d'année est un repère pour les estimations révisées."),
        planned_source="Global Carbon Project / ICOS RI, CC BY 4.0; separate verified capture"),
    "world_adsblol_heathrow_positions": Descriptor(
        t("ADS-B.lol Heathrow-area aircraft snapshot", "Instantané d'aéronefs près de Heathrow selon ADS-B.lol"),
        t("One captured source snapshot of recent aircraft reports near Heathrow.",
          "Un instantané source de signalements récents d'aéronefs près de Heathrow."),
        "single snapshot", "versioned public ADS-B.lol ODbL capture",
        (t("One area and instant; reception is incomplete and aircraft operators or issuers are not verified.",
           "Une zone et un instant; la réception est incomplète et les exploitants ou émetteurs ne sont pas vérifiés."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; position age is derived from the source snapshot.",
          "La capture établit la disponibilité; l'âge de position vient de l'instantané source."),
        planned_source="ADS-B.lol; separate ODbL derived database"),
    "trade_marinecadastre_ais_2024_samples": Descriptor(
        t("NOAA 2024 AIS raster sample cells", "Cellules d'échantillon du raster AIS 2024 de la NOAA"),
        t("Two U.S. coastal annual raster cell counts from fixed query anchors.",
          "Deux comptes annuels de cellules côtières américaines issus de points de requête fixes."),
        "annual", "versioned NOAA MarineCadastre CC0 raster query capture",
        (t("Raster counts are not unique vessels, current traffic, port boundaries or cargo.",
           "Les comptes raster ne sont ni des navires uniques, ni un trafic actuel, ni des limites portuaires ou cargaisons."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; 2024 is an annual reference period.",
          "La capture établit la disponibilité; 2024 est une période annuelle de référence."),
        planned_source="NOAA MarineCadastre AIS annual raster; CC0 selected capture"),
    "world_copernicus_activation_centroids": Descriptor(
        t("Copernicus EMS activation centroids", "Centroïdes d'activations du service Copernicus EMS"),
        t("Five public emergency mapping activation metadata records with source centroids.",
          "Cinq fiches publiques d'activation de cartographie d'urgence avec centroïdes source."),
        "bounded snapshot", "versioned public Copernicus EMS activation capture",
        (t("Centroids are not disaster epicenters or damage boundaries; catalogue is paginated.",
           "Les centroïdes ne sont ni des épicentres ni des limites de dommages; le catalogue est paginé."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; source activation times omit timezone.",
          "La capture établit la disponibilité; le fuseau des dates d'activation source est absent."),
        planned_source="Copernicus Emergency Management Service public metadata; attribution required"),
    "world_firms_modis_europe": Descriptor(
        t("NASA FIRMS MODIS Europe thermal detections", "Détections thermiques MODIS en Europe de NASA FIRMS"),
        t("Regional rolling 24-hour satellite thermal anomaly pixel centers.",
          "Centres de pixels d'anomalies thermiques satellitaires sur 24 heures en Europe."),
        "rolling 24-hour snapshot", "versioned public NASA FIRMS regional CSV capture",
        (t("Thermal anomalies do not confirm wildfires; cloud and satellite coverage is incomplete.",
           "Les anomalies thermiques ne confirment pas les incendies; la couverture satellitaire est incomplète."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes replay availability; detection times are sensor observation times.",
          "La capture établit la disponibilité; les dates de détection sont celles des observations du capteur."),
        planned_source="NASA FIRMS MODIS Collection 6.1; NASA Earthdata attribution"),
    "world_nyfed_sce_inflation_2024": Descriptor(
        t("New York Fed 2024 inflation expectations", "Anticipations d'inflation 2024 de la Fed de New York"),
        t("Twelve monthly national household survey median one-year inflation expectations.",
          "Douze médianes mensuelles nationales d'anticipations d'inflation à un an des ménages."),
        "monthly", "versioned public New York Fed SCE workbook capture",
        (t("Expectations are not measured CPI; 2024 monthly anchors and current workbook revision only.",
           "Les anticipations ne sont pas l'IPC mesuré; repères mensuels 2024 et révision actuelle du classeur seulement."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; first of month is a display anchor.",
          "La capture établit la disponibilité; le premier du mois est un repère d'affichage."),
        planned_source="Federal Reserve Bank of New York SCE; dataset-specific royalty-free reuse and required disclaimer"),
    "world_ember_monthly_generation_2026": Descriptor(
        t("Ember monthly electricity generation", "Production mensuelle d'électricité selon Ember"),
        t("Selected 2026 total electricity generation in TWh by country and month.",
          "Production électrique totale choisie en 2026, en TWh, par pays et mois."),
        "monthly", "versioned public Ember global monthly CSV capture",
        (t("One year and total generation only; country month coverage varies and no plants are identified.",
           "Une année et la production totale seulement; les mois varient selon le pays et aucune centrale n'est identifiée."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; month start is a display anchor.",
          "La capture établit la disponibilité; le début du mois est un repère d'affichage."),
        planned_source="Ember monthly electricity data; CC BY 4.0 selected capture"),
    "world_geofabrik_monaco_transport": Descriptor(
        t("Geofabrik Monaco transport points", "Points de transport Geofabrik de Monaco"),
        t("Mapped transport points in the Monaco OpenStreetMap extract.",
          "Points de transport cartographiés dans l'extrait OpenStreetMap de Monaco."),
        "static sample", "versioned public Geofabrik Monaco GeoPackage capture",
        (t("Extract can include neighboring France; no country, current service or operator is inferred.",
           "L'extrait peut inclure la France voisine; aucun pays, service actuel ou exploitant n'est inféré."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; mapped features have no event date.",
          "La capture établit la disponibilité; les éléments cartographiés n'ont pas de date d'événement."),
        planned_source="© OpenStreetMap contributors, processed by Geofabrik; separate ODbL derived database"),
    "world_hapi_inform_risk_2025": Descriptor(
        t("INFORM 2025 national humanitarian risk index", "Indice national INFORM 2025 de risque humanitaire"),
        t("Annual national humanitarian risk composite and source components for 191 countries.",
          "Indice national annuel de risque humanitaire et composantes source pour 191 pays."),
        "annual", "versioned HDX HAPI v2 INFORM capture",
        (t("A composite index, not a disaster event, forecast or financial risk estimate; no point coordinates.",
           "Un indice composite, ni catastrophe, ni prévision, ni estimation de risque financier; aucun point."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; January 1 is an annual display anchor.",
          "La capture établit la disponibilité; le 1er janvier est un repère d'affichage annuel."),
        planned_source="INFORM Risk Index via OCHA HDX HAPI; HDX dataset licence CC BY"),
    "world_statcan_cpi": Descriptor(
        t("Statistics Canada consumer price index", "Indice des prix à la consommation de Statistique Canada"),
        t("Latest twelve Canada all-items monthly CPI index observations.",
          "Douze dernières observations mensuelles de l'IPC d'ensemble du Canada."),
        "monthly", "versioned Statistics Canada WDS capture",
        (t("Index 2002=100, not seasonally adjusted; not a monthly inflation rate.",
           "Indice 2002=100, non désaisonnalisé; ce n'est pas un taux d'inflation mensuel."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; monthly values may be revised.",
          "La capture établit la disponibilité; les valeurs mensuelles peuvent être révisées."),
        planned_source="Statistics Canada WDS; separate verified world capture"),
    "world_wgi_political_stability_2024": Descriptor(
        t("World Bank 2024 political stability governance score", "Score de gouvernance de stabilité politique 2024 de la Banque mondiale"),
        t("Country-level annual WGI composite estimates on a 0 to 100 scale.",
          "Estimations composites annuelles WGI par pays sur une échelle de 0 à 100."),
        "annual", "versioned World Bank WGI API capture",
        (t("One indicator and year only; a composite estimate, not a current event or financial risk model.",
           "Un seul indicateur et une seule année ; estimation composite, pas un événement actuel ni un modèle de risque financier."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; January 1 is an annual display anchor.",
          "La capture établit la disponibilité ; le 1er janvier est un repère d'affichage annuel."),
        planned_source="World Bank Worldwide Governance Indicators; separate verified world capture"),
    "world_ecb_eurosystem_assets_2024": Descriptor(
        t("ECB Eurosystem assets and liabilities", "Actifs et passifs de l'Eurosystème de la BCE"),
        t("Fifty-two weekly 2024 records in millions of euros.", "Cinquante-deux relevés hebdomadaires de 2024 en millions d'euros."),
        "weekly", "versioned anonymous ECB statistical capture",
        (t("One 2024 series only; free ECB source and adapted attribution must stay visible.",
           "Une seule série pour 2024 ; la source gratuite de la BCE et la mention d'adaptation doivent rester visibles."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; weeks use display anchors.", "La capture établit la disponibilité ; les semaines utilisent des repères d'affichage."),
        planned_source="European Central Bank; separate verified world capture"),
    "world_bis_us_debt_service_2024": Descriptor(
        t("BIS U.S. debt-service sample", "Échantillon BIS du service de la dette américaine"),
        t("Four quarterly 2024 private nonfinancial debt-service records.", "Quatre relevés trimestriels de 2024 du service de la dette privée non financière."),
        "quarterly", "versioned anonymous BIS statistical capture",
        (t("One series and year only; BIS terms disallow an additional charge for data inclusion.",
           "Une seule série et année ; les conditions de la BIS interdisent un coût supplémentaire pour l'inclusion des données."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; quarters use display anchors.", "La capture établit la disponibilité ; les trimestres utilisent des repères d'affichage."),
        planned_source="Bank for International Settlements; separate verified world capture"),
    "world_fed_chargeoffs_2024": Descriptor(
        t("Federal Reserve bank charge-off sample", "Échantillon des radiations bancaires de la Réserve fédérale"),
        t("Four quarterly 2024 total-loan charge-off records for all U.S. banks.",
          "Quatre relevés trimestriels 2024 des radiations de prêts totaux pour toutes les banques américaines."),
        "quarterly", "versioned Federal Reserve statistical release capture",
        (t("One 2024 aggregate series only; no individual bank or security is identified.",
           "Une seule série agrégée 2024 ; aucune banque ou valeur mobilière individuelle n'est identifiée."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; quarters use display anchors.", "La capture établit la disponibilité ; les trimestres utilisent des repères d'affichage."),
        planned_source="Federal Reserve Board; separate verified world capture"),
    "world_gdelt_event_metadata": Descriptor(
        t("GDELT coded event location sample", "Échantillon des lieux d'événements codés GDELT"),
        t("Two hundred fifty selected action-location records from one update.", "Deux cent cinquante lieux d'action sélectionnés d'une mise à jour."),
        "batch", "versioned GDELT Event 2.0 bulk capture",
        (t("Machine-coded locations can be wrong; this is a selected sample, not complete world events.",
           "Les lieux codés automatiquement peuvent être erronés ; échantillon sélectionné, pas tous les événements mondiaux."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; event day does not establish publication vintage.",
          "La capture établit la disponibilité ; la date d'événement ne prouve pas la version publiée."),
        planned_source="GDELT Event 2.0; separate verified world capture"),
    "world_gdelt_gkg_locations": Descriptor(
        t("GDELT GKG article location sample", "Échantillon des lieux d'articles GKG de GDELT"),
        t("Two hundred fifty selected article-location records from one update.",
          "Deux cent cinquante lieux d'articles sélectionnés d'une mise à jour."),
        "batch", "versioned GDELT GKG 2.1 bulk capture",
        (t("A listed place is not necessarily the main article event location; publisher content is not loaded.",
           "Un lieu cité n'est pas nécessairement celui de l'événement principal ; le contenu de l'éditeur n'est pas chargé."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; indexing is not original publication.",
          "La capture établit la disponibilité ; l'indexation n'est pas la publication d'origine."),
        planned_source="GDELT GKG 2.1; separate verified world capture"),
    "world_gdelt_geographic_mentions": Descriptor(
        t("GDELT Geographic Graph mention sample", "Échantillon des mentions du graphe géographique GDELT"),
        t("Two hundred fifty selected article-location mentions from a daily archive.",
          "Deux cent cinquante mentions de lieux d'articles sélectionnées d'une archive quotidienne."),
        "daily", "versioned GDELT Geographic Graph metadata projection",
        (t("Location mentions are not event sites; source article text and images are excluded.",
           "Les lieux mentionnés ne sont pas des sites d'événements ; textes et images sont exclus."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; indexing is not original publication.",
          "La capture établit la disponibilité ; l'indexation n'est pas la publication d'origine."),
        planned_source="GDELT Global Geographic Graph; separate verified world capture"),
    "world_geoboundaries_fra_adm1": Descriptor(
        t("France regional boundaries", "Limites régionales de France"),
        t("Thirteen simplified 2022 metropolitan France administrative polygons.",
          "Treize polygones administratifs simplifiés de France métropolitaine pour 2022."),
        "static", "pinned geoBoundaries release capture",
        (t("Overseas regions excluded; simplified boundaries are unsuitable for legal or survey decisions.",
           "Régions ultramarines exclues ; limites simplifiées impropres aux décisions juridiques ou d'arpentage."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability.", "La capture établit la disponibilité."),
        planned_source="geoBoundaries and IGN-F; separate verified world capture"),
    "world_ucdp_ged_ukraine_2025": Descriptor(
        t("Ukraine conflict event sample", "Échantillon d'événements de conflit en Ukraine"),
        t("One hundred Ukraine 2025 events from UCDP GED version 26.1.",
          "Cent événements ukrainiens de 2025 tirés d'UCDP GED version 26.1."),
        "static", "checksum-verified UCDP GED 26.1 archive capture",
        (t("Bounded historical sample; fatality estimates and source date and location precision are retained.",
           "Échantillon historique borné ; estimations de décès et précision des dates et lieux conservées."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; event dates do not establish historical publication.",
          "La capture établit la disponibilité ; les dates d'événements ne prouvent pas une publication historique."),
        planned_source="Uppsala Conflict Data Program; separate verified world capture"),
    "world_nasa_cmr_modis_granules": Descriptor(
        t("NASA MODIS satellite coverage metadata", "Métadonnées de couverture satellite NASA MODIS"),
        t("Five MOD14A1.061 granule coverage polygons intersecting a European search region.",
          "Cinq polygones de couverture de granules MOD14A1.061 intersectant une région européenne."),
        "batch", "versioned anonymous NASA CMR metadata capture",
        (t("Coverage polygons are not fire detections; imagery and scientific pixels are not loaded.",
           "Les polygones de couverture ne sont pas des détections de feu; les images et pixels scientifiques ne sont pas chargés."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; product dates represent an eight-day interval.",
          "La capture établit la disponibilité; les dates du produit représentent une période de huit jours."),
        planned_source="NASA Terra MODIS / LP DAAC, NASA CMR; separate verified world capture"),
    "trade_un_comtrade_exports": Descriptor(
        t("UN Comtrade merchandise exports", "Exportations de marchandises de l'UN Comtrade"),
        t("Selected annual country merchandise exports to the world.", "Exportations annuelles sélectionnées de marchandises par pays vers le monde."),
        "annual", "versioned public API preview capture",
        (t("Selected reporters only; reuse is subject to UN Comtrade's licensing and re-dissemination rules.",
           "Pays déclarants sélectionnés seulement; la réutilisation est soumise aux règles de licence et de rediffusion de l'UN Comtrade."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; source values may be revised.",
          "La capture établit la disponibilité; les valeurs de la source peuvent être révisées."),
        planned_source="UN Comtrade; separate verified world capture"),
    "trade_wits_fuel_exports": Descriptor(
        t("WITS Canada fuel exports", "Exportations canadiennes de combustibles selon WITS"),
        t("One annual country fuel-export value sourced from UN Comtrade.",
          "Une valeur annuelle nationale d'exportations de combustibles tirée de l'UN Comtrade."),
        "annual", "versioned public WITS API capture",
        (t("Single country, year and product group; UN Comtrade redistribution conditions apply.",
           "Un seul pays, une seule année et un groupe de produits; les conditions de rediffusion de l'UN Comtrade s'appliquent."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; source values may be revised.",
          "La capture établit la disponibilité; les valeurs de la source peuvent être révisées."),
        planned_source="WITS/UN Comtrade; separate verified world capture"),
    "trade_unctad_concentration": Descriptor(
        t("UNCTAD export concentration", "Concentration des exportations selon la CNUCED"),
        t("Selected global annual exporter concentration indices.",
          "Indices annuels mondiaux sélectionnés de concentration des exportateurs."),
        "annual", "versioned public UNCTAD bulk capture",
        (t("Two global product groups only; the index is not trade value or port activity.",
           "Deux groupes de produits mondiaux seulement; l'indice n'est ni une valeur commerciale ni une activité portuaire."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; source values may be revised.",
          "La capture établit la disponibilité; les valeurs de la source peuvent être révisées."),
        planned_source="UNCTAD Data Hub; separate verified world capture"),
    "energy_wri_plants": Descriptor(
        t("WRI power plant reference", "Référence des centrales WRI"),
        t("Geolocated power plant reference; capacity and owner text are source fields.", "Référence géolocalisée des centrales; capacité et propriétaire déclarés par la source."),
        "batch", "versioned public CSV capture",
        (t("A facility is not a security or demonstrated issuer exposure.", "Une installation n'est ni un titre ni une exposition démontrée à un émetteur."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability.", "La capture établit la disponibilité."),
        planned_source="World Resources Institute; separate verified world capture"),
    "world_openflights_airport_reference": Descriptor(
        t("OpenFlights static airport reference", "Référence statique des aéroports OpenFlights"),
        t("Source airport coordinates and identifiers in six countries.",
          "Coordonnées et identifiants d'aéroports de la source dans six pays."),
        "static reference", "versioned public CSV capture",
        (t("Static reference; no aircraft tracking or current operating status. Derived database ODbL 1.0.",
           "Référence statique; aucun suivi d'aéronefs ni état opérationnel actuel. Base dérivée ODbL 1.0."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability; earlier replay excluded.",
          "La capture établit la disponibilité; les rejeux antérieurs sont exclus."),
        planned_source="OpenFlights; separate verified ODbL capture"),
    "trade_portwatch_ports": Descriptor(
        t("PortWatch port reference", "Référence des ports PortWatch"),
        t("IMF port locations; reference does not establish vessel activity.", "Emplacements des ports du FMI; la référence n'établit pas l'activité des navires."),
        "batch", "versioned public CSV capture",
        (t("Respect IMF reuse terms and incomplete coverage.", "Respecter les conditions de réutilisation du FMI et la couverture incomplète."),),
        ("LIM_IMPACT_NOT_ESTABLISHED",),
        t("Capture time establishes availability.", "La capture établit la disponibilité."),
        planned_source="IMF PortWatch; separate verified world capture"),
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

DEFAULT_PROFILES_PATH = Path(__file__).resolve().parents[1] / "profiles" / "defaults.json"
# The release-date file has no retrieval column. data/SOURCES.md records the day each published file
# was read, keyed here by the file's manifest SHA-256 so another file never inherits the date.
_RELEASE_DATES_READ_ON = {"fc82fd354db4fe9d6d0c57d827eda272418dd8270e4a1acf2572d6f0e636969b": "2026-11-14"}
_UNSOURCED_THEMES = re.compile(r"^(\d+) of (\d+) rest on the organizer universe file only")


def _schema(columns: tuple[Column, ...]) -> list[dict]:
    return [{"name": c.name, "type": c.type, "description": c.description} for c in columns if not c.name.startswith("available_at")]


def build_passport(dataset_id: str, manifest: dict | None) -> dict:
    """Wire-shaped DatasetPassport for one catalog dataset under a manifest (or none)."""
    desc = DESCRIPTORS[dataset_id]
    loaded = manifest is not None and dataset_id in manifest.get("datasets", {})
    if not loaded:
        columns = PLANNED_COLUMNS.get(dataset_id, ())
        planned = {
            "datasetId": dataset_id, "name": desc.name, "role": desc.role, "status": "planned",
            "source": desc.planned_source, "sourceUrl": None, "accessMethod": desc.planned_access_method or desc.access_method,
            "licence": "unknown (not yet reviewed)", "licenceUrl": None, "retrievedOn": None, "coverage": None,
            "frequency": desc.frequency, "rowCount": None, "dataVersion": None, "schema": _schema(columns),
            "processing": list(desc.planned_processing or desc.processing), "limitations": list(desc.limitations),
            "availabilityRule": desc.availability_rule, "checks": [], "rejectedReason": None,
        }
        personas = _default_personas() if dataset_id == "default_profiles" else None
        if personas is None:
            return planned
        return {
            **planned, "status": "in_use",
            "source": "Aplomb team: fictional personas; descriptions follow the organizer brief, portfolios, capital and rule thresholds are team assumptions (A-13)",
            "accessMethod": desc.access_method, "licence": "Team-authored, fictional (persona descriptions follow the organizer brief)",
            "rowCount": len(personas), "processing": list(desc.processing),
            "checks": [{"name": "Personas file read; each persona is a default with a fictional portfolio whose weights sum to 100%",
                        "ok": True, "detail": f"{len(personas)} personas: {', '.join(personas)}",
                        "checkedAt": utc_now_iso(datetime.now(timezone.utc))}],
        }
    meta = manifest["datasets"][dataset_id]
    source, source_url, licence, licence_url, retrieved = _provenance(dataset_id, manifest)
    processing = list(desc.processing)
    if dataset_id == "asset_themes" and _theme_sourcing(meta):
        processing[1] = t(
            "Where a row cites an issuer or project page, the assignment rests on that page (short quotation or summary in the justification); otherwise on the organizer universe file (names and sectors) and team judgement. All are assumptions, not an official classification.",
            "Lorsqu'une ligne cite une page de l'émetteur ou du projet, l'attribution repose sur cette page (courte citation ou résumé dans la justification); sinon sur le fichier d'univers des organisateurs (noms et secteurs) et le jugement de l'équipe. Ce sont toutes des hypothèses, pas une classification officielle.")
    if dataset_id == "macro_release_dates" and _statcan_only(meta):
        processing.insert(1, t(
            "Canada CPI: the release date is the 'Released' date of each article of The Daily (date only, no time of day); the 12-month change in each article was compared with the stored value when the dates were collected.",
            "IPC du Canada : la date de publication est la date de diffusion de chaque article du Quotidien (date seulement, sans heure); la variation sur 12 mois de chaque article a été comparée à la valeur stockée lors de la collecte des dates."))
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


def _default_personas() -> list[str] | None:
    """Ids of the personas shipped with the application, or ``None`` when the file fails the check."""
    try:
        personas = json.loads(DEFAULT_PROFILES_PATH.read_text(encoding="utf-8"))
        ids = [p["profileId"] for p in personas]
        ok = bool(ids) and len(set(ids)) == len(ids) and all(
            p["isDefault"] is True and p["portfolio"]["isFictional"] is True
            and abs(sum(pos["weightPct"] for pos in p["portfolio"]["positions"]) - 100.0) < 1e-6 for p in personas)
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return sorted(ids) if ok else None


def _theme_sourcing(meta: dict) -> tuple[int, int] | None:
    """(rows citing a page, all rows) when at least one assignment cites a page, from the ingestion check."""
    for check in meta["checks"]:
        found = _UNSOURCED_THEMES.match(check["detail"]) if check["name"] == "Assignments backed by a source URL" else None
        if found:
            unsourced, total = int(found.group(1)), int(found.group(2))
            return (total - unsourced, total) if unsourced < total else None
    return None


def _statcan_only(meta: dict) -> bool:
    hosts = meta.get("details", {}).get("sourceHosts", [])
    return bool(hosts) and all(h.endswith("statcan.gc.ca") for h in hosts)


def _provenance(dataset_id: str, manifest: dict) -> tuple[str, str | None, str, str | None, str | None]:
    if dataset_id == "fx_boc_global":
        meta = manifest["datasets"][dataset_id]
        details = meta.get("details", {})
        return ("Bank of Canada Valet, daily indicative FX rates", details.get("sourceUrl"),
                "Bank of Canada terms; indicative rates and potential third-party rights",
                "https://www.bankofcanada.ca/terms/", details.get("retrievedAt", "")[:10] or None)
    if dataset_id == "asset_themes":
        meta = manifest["datasets"]["asset_themes"]
        dates = meta.get("details", {}).get("assignedAt", [])
        retrieved = max(dates) if dates else None
        themes = _theme_sourcing(meta)
        if themes:
            return (f"Aplomb team assignment (assumptions); {themes[0]} of {themes[1]} supported by an issuer or project page "
                    "cited per row, the others by the organizer universe file", None,
                    "Team-authored tags; short quotations from the third-party pages cited per row (terms of those pages not reviewed)",
                    None, retrieved)
        return ("Aplomb team assignment (assumptions) based on the organizer universe file", None,
                "Team-authored metadata; no third-party content", None, retrieved)
    if dataset_id == "macro_release_dates":
        meta = manifest["datasets"]["macro_release_dates"]
        details = meta.get("details", {})
        hosts = details.get("sourceHosts", [])
        series = ", ".join(details.get("series", []))
        # Never the manifest build time: a date nobody recorded stays unknown.
        retrieved = details.get("retrievedOn") or next(
            (_RELEASE_DATES_READ_ON.get(src["sha256"]) for src in manifest.get("sources", []) if src["file"] == "macro_release_dates.csv"), None)
        if _statcan_only(meta):
            return (f"Statistics Canada, The Daily: official release date of each reference month ({series}); URL per row",
                    "https://www.statcan.gc.ca/dai-quo/index-eng.htm", "Statistics Canada Open Licence",
                    "https://www.statcan.gc.ca/en/terms-conditions/open-licence", retrieved)
        return (f"Release calendars cited per row ({', '.join(hosts)})", None, "see the source of each row", None, retrieved)
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
# Statuses reflect what this repository has verified: "handled" only where the tests named in
# ``handledBy`` cover the treatment. Owners flip "open" to "handled" when their listed tests pass.
TRAPS: tuple[dict, ...] = (
    {"code": LIM_FX_FFILL, "status": "handled",
     "handledBy": "CAD/USD mismatch and FX holiday gaps: the datastore returns only the last rate published on or before a day, never a later one (datastore tests: days without a same-day rate, no prior rate); every USD figure is converted by quant M_FX_BOC_FFILL (T05), checked against the CAD control values (QNT-02) and the no-prior-rate case (QNT-06)."},
    {"code": LIM_CALENDAR_INTERSECTION, "status": "handled",
     "handledBy": "Master calendar XIU.TO ∩ SPY with crypto sampled on those days and no price fill (datastore DS-02, DS-07)."},
    {"code": LIM_YAHOO_NOT_CERTIFIED, "status": "disclosed",
     "handledBy": "adj_close used as published; splits and dividends are annotations and never re-applied; checksums pin the snapshot. Original price vintages are not available."},
    {"code": LIM_CNQ_FACTOR, "status": "disclosed",
     "handledBy": "Split anomaly flagged at ingestion; limitation attached to CNQ.TO reads spanning 2022-08-22; not applied twice."},
    {"code": LIM_MACRO_LAG_ASSUMED, "status": "open",
     "handledBy": "Monthly values use real release dates when macro_release_dates covers them (Canada CPI from Statistics Canada in snap-20261114-sourced); otherwise current runs use the A-22 lag and historical runs withhold them. US monthly FRED series have no release/vintage data loaded."},
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
