"""Dataset passports for the world bundle (data SPEC: a dataset is ``in_use`` only once loaded
and checked). Overlays the catalog's planned entries for ``world_events`` and ``natural_hazards``."""

from __future__ import annotations

from typing import Callable

from aplomb.contracts import api as a
from aplomb.contracts import models as m
from aplomb.datastore.service import DatastoreService

from .country_macro import SOURCE_ID
from .dataset import WorldDataError, WorldDataset
from .facilities import load_facilities
from .providers import load_provider_snapshots

PROVIDER_DATASET_IDS = frozenset({
    "world_nasa_power", "world_epa_sems_sites",
    "world_climate_trace_canada_electricity_co2",
    "world_federal_register", "world_ecb_press", "world_statcan_cpi",
    "world_fda_drug_enforcement_counts", "world_crossref_climate_bibliography",
    "world_bls_us_cpi_2024",
    "world_wgi_political_stability_2024",
    "world_ecb_eurosystem_assets_2024", "world_bis_us_debt_service_2024", "world_fed_chargeoffs_2024",
    "world_gdelt_event_metadata", "world_gdelt_gkg_locations", "world_gdelt_geographic_mentions",
    "world_wikimedia_topic_pageviews",
    "world_wikipedia_recent_changes",
    "world_ilo_unemployment_2024",
    "world_bank_sdmx_gdp_2024",
    "world_nasa_gibs_modis_tile",
    "world_global_carbon_budget_2026",
    "world_nyfed_sce_inflation_2024",
    "world_nasa_cmr_modis_granules",
    "world_openaq_defra_york_20260328",
})


def _t(en: str, fr: str) -> dict:
    return {"en": en, "fr": fr}


# Team decision (geo.PRESENTED_AS), stated in every passport whose served rows it can change.
PALESTINE_NOTE = _t(
    "Team decision: source codes and names for Israel, the West Bank and Gaza (ISR, Israel, West Bank, Gaza Strip) "
    "are presented as Palestine (PSE). Applied when the capture is loaded; the captured files and their checksums are unchanged.",
    "Décision de l'équipe : les codes et noms de source d'Israël, de la Cisjordanie et de Gaza (ISR, Israel, West Bank, "
    "Gaza Strip) sont présentés comme Palestine (PSE). Appliqué au chargement; les fichiers capturés et leurs empreintes sont inchangés.")


def world_passports(ds: WorldDataset) -> dict[str, dict]:
    """Fields that replace the planned passport of each loaded world dataset."""
    built = ds.built_at
    manifest = ds.manifest
    sources = {s["id"]: s for s in manifest["sources"]}
    failed = [s["name"] for s in manifest["sources"] if s["status"] != "ok"]
    not_loaded = "; ".join(f"{n['source']}: {n['reason']}" for n in manifest["notIngested"])
    out: dict[str, dict] = {}
    if ds.events:
        loaded = [f"{s['name']} ({s.get('items', 0)})" for s in manifest["sources"] if s["status"] == "ok"]
        out["world_events"] = {
            "status": "in_use", "source": "; ".join(loaded), "sourceUrl": None,
            "accessMethod": "HTTPS public feeds, no key; one batch fetch at build time",
            "licence": "Per source: U.S. Government works (USGS, Federal Reserve); Bank of Canada terms; "
                       "Statistics Canada Open Licence; NASA EONET metadata disclaimer (when loaded), linked content separate",
            "licenceUrl": None, "retrievedOn": built[:10], "coverage": ds.coverage, "frequency": "batch",
            "rowCount": len(ds.events), "dataVersion": ds.version,
            "schema": [{"name": "event", "type": "object", "description": "WorldEvent wire fields (contracts/schemas.md §10)"}],
            "processing": [
                _t("Titles, links and dates are kept verbatim from each source; an item without a link, a title, a date or "
                   "a source-supported location is rejected.",
                   "Les titres, liens et dates proviennent tels quels de chaque source; un élément sans lien, titre, date ou "
                   "lieu attesté par la source est rejeté."),
                _t("Event identity is a hash of the canonical source URL; items sharing a URL are merged, headlines alone never are.",
                   "L'identité d'un événement est une empreinte de l'URL canonique; les éléments de même URL sont fusionnés, "
                   "jamais sur le seul titre."),
                _t("Official releases are placed at the issuing country's centroid (country precision); earthquakes use the "
                   "catalog epicentre (point precision); EONET uses the first source-reported point, with no inferred country.",
                   "Les communiqués officiels sont placés au centroïde du pays émetteur (précision pays); les séismes "
                   "utilisent l'épicentre du catalogue (précision point); EONET utilise le premier point fourni par la source, "
                   "sans pays inféré."),
                _t("NASA EONET metadata is for visualization/general information. Spatial and temporal extents are approximations, not official event boundaries; original linked publishers have separate rights.",
                   "Les métadonnées NASA EONET servent à la visualisation et à l'information générale. Les emprises spatiales et temporelles sont approximatives, sans valeur officielle; les éditeurs liés ont leurs propres droits."),
                _t("Importance is a display priority fixed at build time; it is not a market-impact estimate.",
                   "L'importance est une priorité d'affichage fixée à la construction; ce n'est pas une estimation "
                   "d'incidence sur les marchés."),
                # The reasons are the bundle manifest's English text, so the French line quotes them as recorded.
                _t(f"Not in this event feed: {not_loaded}",
                   f"Hors de ce fil d'événements (motifs du manifeste, en anglais) : {not_loaded}"),
                PALESTINE_NOTE,
            ],
            "limitations": ["LIM_IMPACT_NOT_ESTABLISHED"],
            "availabilityRule": _t(
                "Cached batch; occurrence, publication and retrieval times are kept separate. Not used in historical replays.",
                "Lot en cache; les heures d'occurrence, de publication et de récupération sont distinctes. Non utilisé dans "
                "les rejeux historiques."),
            "checks": [
                {"name": "bundle_checksums", "ok": True, "detail": "events.json matches the manifest SHA-256 and row count.",
                 "checkedAt": built},
                {"name": "sources_fetched", "ok": not failed,
                 "detail": "All configured sources answered at build time." if not failed
                 else "Failed at build time: " + ", ".join(failed), "checkedAt": built},
            ],
            "rejectedReason": None,
        }
    if ds.hazards:
        usgs = sources.get("usgs_earthquakes", {})
        magnitude = usgs.get("filter", "magnitude filter")
        out["natural_hazards"] = {
            "status": "in_use", "source": usgs.get("name", "USGS Earthquake Catalog"),
            "sourceUrl": "https://earthquake.usgs.gov/fdsnws/event/1/",
            "accessMethod": "HTTPS API, no key; one batch fetch at build time",
            "licence": "U.S. Government work, public domain",
            "licenceUrl": "https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits",
            "retrievedOn": built[:10], "coverage": manifest["hazards"]["coverage"], "frequency": "batch",
            "rowCount": len(ds.hazards), "dataVersion": ds.version,
            "schema": [{"name": "hazard", "type": "object", "description": "Hazard wire fields (contracts/schemas.md §10)"}],
            "processing": [
                _t(f"Earthquakes only ({magnitude}); wildfire detections (NASA FIRMS) are not served.",
                   f"Séismes seulement ({magnitude}); les détections de feux (NASA FIRMS) ne sont pas servies."),
                _t("Proximity to a hazard does not establish an effect on any holding.",
                   "La proximité d'un aléa n'établit aucun effet sur un titre."),
                PALESTINE_NOTE,
            ],
            "limitations": ["LIM_IMPACT_NOT_ESTABLISHED"],
            "availabilityRule": _t(
                "Cached batch stamped with the catalog origin time; magnitudes can be revised by the source later.",
                "Lot en cache horodaté à l'heure d'origine du catalogue; les magnitudes peuvent être révisées par la source."),
            "checks": [{"name": "bundle_checksums", "ok": True,
                        "detail": "hazards.json matches the manifest SHA-256 and row count.", "checkedAt": built}],
            "rejectedReason": None,
        }
    if ds.country_macro_manifest:
        macro = ds.country_macro_manifest
        withheld = macro["rowCount"] - len(ds.country_macro)
        out[SOURCE_ID] = {
            "datasetId": SOURCE_ID,
            "name": _t("World Bank World Development Indicators", "Indicateurs du développement dans le monde, Banque mondiale"),
            "role": _t("Annual country-level economic and demographic indicators", "Indicateurs annuels économiques et démographiques par pays"),
            "status": "in_use", "source": "World Bank, World Development Indicators",
            "sourceUrl": macro["catalogUrl"], "accessMethod": "World Bank indicators API v2; fixed bounded batch",
            "licence": macro["licence"], "licenceUrl": macro["licenceUrl"],
            "retrievedOn": macro["retrievedAt"][:10], "coverage": macro["coverage"],
            "frequency": "annual; manually refreshed batch", "rowCount": len(ds.country_macro),
            "dataVersion": macro["dataVersion"],
            "schema": [
                {"name": "countryIso3", "type": "string", "description": "World Bank country/territory code; geographic aggregates excluded."},
                {"name": "indicatorId", "type": "string", "description": "World Bank WDI indicator identifier."},
                {"name": "observationYear", "type": "integer", "description": "Reference year; not publication date."},
                {"name": "value", "type": "number", "description": "Latest captured value for the completed year."},
                {"name": "availableAt", "type": "timestamp", "description": "Capture timestamp; earliest established application availability."},
            ],
            "processing": [
                _t("Latest nonempty completed calendar year among the two most recent observations. World Bank regional and income-group aggregates are omitted.",
                   "Dernière année civile complète non vide parmi les deux dernières observations. Les agrégats régionaux et de groupe de revenu sont omis."),
                _t("Attribution: World Bank, World Development Indicators; indicators may incorporate data from national statistical bodies and other providers. Translations and filtered rows adapted by Aplomb. No World Bank endorsement implied.",
                   "Attribution : Banque mondiale, Indicateurs du développement dans le monde; les indicateurs peuvent inclure des données de sources nationales et autres. Traductions et filtrage adaptés par Aplomb. Aucun appui de la Banque mondiale n'est implicite."),
                _t("Annual observations are not real-time signals; estimates can be revised. No financial or causal impact is implied.",
                   "Les observations annuelles ne sont pas des signaux en temps réel; les estimations peuvent être révisées. Aucune incidence financière ou causale n'est implicite."),
                _t(f"Team decision: ISR-coded rows are presented under PSE (Palestine). The World Bank publishes its own PSE series (West Bank and Gaza), so that series is served and the {withheld} ISR rows are withheld, never merged or summed.",
                   f"Décision de l'équipe : les lignes codées ISR sont présentées sous PSE (Palestine). La Banque mondiale publie sa propre série PSE (Cisjordanie et Gaza); cette série est servie et les {withheld} lignes ISR sont retenues, jamais fusionnées ni additionnées."),
            ],
            "limitations": ["LIM_MACRO_REVISED", "LIM_IMPACT_NOT_ESTABLISHED"],
            "availabilityRule": _t("Publication dates and original historical vintages are unknown. The earliest proven availability is the retrieval timestamp. This snapshot is not used in historical replays.",
                                   "Les dates de publication et les versions historiques originales sont inconnues. La première disponibilité prouvée est la récupération. Cet instantané n'est pas utilisé dans les rejeux historiques."),
            "checks": [{"name": "country_macro_checksum", "ok": True,
                        "detail": f"The {macro['rowCount']} saved observations match the manifest SHA-256 and row count.", "checkedAt": macro["retrievedAt"]}],
            "rejectedReason": None,
        }
    return out


def provider_passports() -> dict[str, dict]:
    """Passports only for checksum-verified optional captures consumed by observations.

    A damaged capture removes only its own source's passport; intact sources keep theirs."""
    rows, manifests = load_provider_snapshots(errors=[])
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["sourceId"]] = counts.get(row["sourceId"], 0) + 1
    out = {}
    for manifest in manifests:
        source_id = manifest["datasetId"]
        attribution = manifest.get("attribution") or next(
            (row.get("properties", {}).get("attribution") for row in rows
             if row["sourceId"] == source_id and row.get("properties", {}).get("attribution")), None,
        )
        retrieved = manifest["retrievedAt"]
        scope = manifest.get("scope") or manifest["name"]
        version = f"snap-{retrieved[:10].replace('-', '')}-{source_id}-{manifest['sha256'][:10]}"
        presentation = manifest.get("presentation")
        presented = [PALESTINE_NOTE] if presentation else []
        if presentation and presentation["withheldIsrRows"]:
            withheld = presentation["withheldIsrRows"]
            presented.append(_t(
                f"This source also publishes PSE rows, so its own PSE rows are served and its {withheld} ISR-coded row(s) are withheld under the team decision.",
                f"Cette source publie aussi des lignes PSE; ses propres lignes PSE sont servies et ses {withheld} ligne(s) codée(s) ISR sont retenues selon la décision de l'équipe."))
        out[source_id] = {
            "datasetId": source_id,
            "name": _t(manifest["name"], manifest["name"]),
            "role": _t(scope, scope),
            "status": "in_use",
            "source": manifest["name"],
            "sourceUrl": manifest["sourceUrl"],
            "accessMethod": manifest.get("accessMethod", "Bounded public HTTPS batch capture; no runtime source request"),
            "licence": manifest["licence"],
            "licenceUrl": manifest.get("licenceUrl"),
            "retrievedOn": retrieved[:10],
            "coverage": None,
            "frequency": manifest["frequency"],
            "rowCount": counts[source_id],
            "dataVersion": version,
            "schema": [
                {"name": "id", "type": "string", "description": "Provider-stable source observation ID"},
                {"name": "location", "type": "object", "description": "Validated source coordinates when provided; may be absent"},
                {"name": "geometry", "type": "object", "description": "Source polygon or line geometry when provided; a polygon may have no point coordinates"},
                {"name": "retrievedAt", "type": "timestamp", "description": "First proven availability of this captured version"},
            ],
            "processing": [_t(note, note) for note in
                           ([attribution] if attribution else []) + manifest["limitations"]] + presented,
            "limitations": ["LIM_IMPACT_NOT_ESTABLISHED"],
            "availabilityRule": _t(manifest["availabilityRule"], manifest["availabilityRule"]),
            "checks": [
                {"name": "normalized_checksum", "ok": True,
                 "detail": f"{manifest['rowCount']} normalized rows match {manifest['sha256']}; "
                           "raw captures also passed SHA-256 verification.",
                 "checkedAt": retrieved},
                {"name": "pagination_coverage", "ok": bool(manifest.get("coverageComplete")),
                 "detail": scope, "checkedAt": retrieved},
            ],
            "rejectedReason": None,
        }
    return out


class WorldDatastoreService(DatastoreService):
    """``DataService`` whose passports reflect the loaded world bundle (planned otherwise)."""

    def __init__(self, snapshot, world: Callable[[], WorldDataset], on_demand=None) -> None:
        super().__init__(snapshot, on_demand)
        self._world = world

    def _overrides(self) -> dict[str, dict]:
        try:
            overrides = world_passports(self._world())
            try:
                facilities, facility = load_facilities()
            except (ValueError, OSError, KeyError):
                facilities, facility = [], None
            if facility:
                year = facility["reportingYear"]
                overrides["emissions_facilities"] = {
                    "status": "in_use", "source": "Environment and Climate Change Canada, GHGRP",
                    "sourceUrl": facility["sourceUrl"], "accessMethod": "Bounded official CSV capture; required-field projection",
                    "licence": facility["licence"], "licenceUrl": facility["licenceUrl"],
                    "retrievedOn": facility["capturedAt"][:10], "rowCount": len(facilities),
                    "dataVersion": facility["dataVersion"], "coverage": {"start": f"{year}-01-01", "end": f"{year}-12-31"},
                    "frequency": "annual; captured batch",
                    "processing": [
                        _t("Attribution: Environment and Climate Change Canada, Greenhouse Gas Reporting Program. Latest completed reference year; total reported tonnes CO2e exclude biomass CO2. Adapted by Aplomb; no government endorsement.",
                           "Attribution : Environnement et Changement climatique Canada, Programme de déclaration des gaz à effet de serre. Dernière année de référence complète; tonnes éq. CO2 déclarées hors CO2 de biomasse. Adaptation Aplomb; sans appui gouvernemental."),
                        _t("Only required facility, reporting-company, coordinate and emissions fields retained; public-contact/personal fields omitted. No security matching or ESG score is inferred.",
                           "Seuls les champs requis d'installation, société déclarante, coordonnées et émissions sont conservés; les coordonnées personnelles des contacts publics sont omises. Aucun lien avec un titre ni score ESG inféré."),
                        _t(f"Rejected {facility['rejected']} latest-year rows with missing/invalid coordinates, identity or emissions; incomplete observations are not mapped.",
                           f"{facility['rejected']} lignes de la dernière année rejetées pour coordonnées, identité ou émissions manquantes/invalides; les observations incomplètes ne sont pas cartographiées."),
                    ],
                    "limitations": ["LIM_IMPACT_NOT_ESTABLISHED"],
                    "availabilityRule": _t("Original publication and historical vintages unknown. Current captured reference only; not used in historical reconstruction.",
                                           "Publication originale et millésimes historiques inconnus. Référence actuelle capturée seulement; exclue des reconstitutions historiques."),
                    "checks": [{"name": "facility_snapshot_checksum", "ok": True,
                                "detail": "Normalized rows match SHA-256 and count; original and retained-projection hashes preserved in manifest.", "checkedAt": facility["capturedAt"]}],
                }
            try:
                overrides.update(provider_passports())
            except (ValueError, OSError, KeyError, TypeError):
                # Optional provider damage cannot hide the existing world passports.
                pass
            return overrides
        except WorldDataError:
            return {}

    def datasets(self, session_id: str) -> a.DatasetsResponse:
        body = self.snapshot().datasets_response()
        overrides = self._overrides()
        items = [{**p, **overrides.get(p["datasetId"], {})} for p in body["items"]]
        existing = {p["datasetId"] for p in items}
        items.extend(value for key, value in overrides.items() if key not in existing)
        return a.DatasetsResponse.model_validate({**body, "items": items})

    def dataset(self, session_id: str, dataset_id: str) -> m.DatasetPassport:
        override = self._overrides().get(dataset_id)
        if dataset_id in PROVIDER_DATASET_IDS | {SOURCE_ID} and override is not None:
            return m.DatasetPassport.model_validate(override)
        base = super().dataset(session_id, dataset_id)
        if override is None:
            return base
        return m.DatasetPassport.model_validate({**base.to_wire(), **override})
