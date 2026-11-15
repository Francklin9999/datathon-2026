"""Dataset passports for the world bundle (data SPEC: a dataset is ``in_use`` only once loaded
and checked). Overlays the catalog's planned entries for ``world_events`` and ``natural_hazards``."""

from __future__ import annotations

from typing import Callable

from aplomb.contracts import api as a
from aplomb.contracts import models as m
from aplomb.datastore.service import DatastoreService

from .dataset import WorldDataError, WorldDataset


def _t(en: str, fr: str) -> dict:
    return {"en": en, "fr": fr}


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
                   "utilisent l'épicentre du catalogue (précision point)."),
                _t("NASA EONET metadata is for visualization/general information. Spatial and temporal extents are approximations, not official event boundaries; original linked publishers have separate rights.",
                   "Les métadonnées NASA EONET servent à la visualisation et à l'information générale. Les emprises spatiales et temporelles sont approximatives, sans valeur officielle; les éditeurs liés ont leurs propres droits."),
                _t("Importance is a display priority fixed at build time; it is not a market-impact estimate.",
                   "L'importance est une priorité d'affichage fixée à la construction; ce n'est pas une estimation "
                   "d'incidence sur les marchés."),
                _t(f"Not loaded: {not_loaded}", f"Non chargé : {not_loaded}"),
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
                _t(f"Earthquakes only ({magnitude}); wildfire detections (NASA FIRMS) are not loaded.",
                   f"Séismes seulement ({magnitude}); les détections de feux (NASA FIRMS) ne sont pas chargées."),
                _t("Proximity to a hazard does not establish an effect on any holding.",
                   "La proximité d'un aléa n'établit aucun effet sur un titre."),
            ],
            "limitations": ["LIM_IMPACT_NOT_ESTABLISHED"],
            "availabilityRule": _t(
                "Cached batch stamped with the catalog origin time; magnitudes can be revised by the source later.",
                "Lot en cache horodaté à l'heure d'origine du catalogue; les magnitudes peuvent être révisées par la source."),
            "checks": [{"name": "bundle_checksums", "ok": True,
                        "detail": "hazards.json matches the manifest SHA-256 and row count.", "checkedAt": built}],
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
            return world_passports(self._world())
        except WorldDataError:
            return {}

    def datasets(self, session_id: str) -> a.DatasetsResponse:
        body = self.snapshot().datasets_response()
        overrides = self._overrides()
        items = [{**p, **overrides.get(p["datasetId"], {})} for p in body["items"]]
        return a.DatasetsResponse.model_validate({**body, "items": items})

    def dataset(self, session_id: str, dataset_id: str) -> m.DatasetPassport:
        base = super().dataset(session_id, dataset_id)
        override = self._overrides().get(dataset_id)
        if override is None:
            return base
        return m.DatasetPassport.model_validate({**base.to_wire(), **override})
