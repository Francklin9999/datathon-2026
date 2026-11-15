"""``WorldService`` for the HTTP API (api.md §6): cached events, exposure by listing country,
country panel, hazards and layers. Reads only the immutable world bundle and the pinned price
snapshot; no request ever reaches a third-party source (world SPEC §1).

Every link between an event and a holding is a documented match (company named in the source
title, theme-tag proxy, listing country). Financial impact is never estimated here.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from functools import cached_property
from typing import Callable

from aplomb.api.errors import NotFound, ServiceError, unavailable
from aplomb.contracts import api as a
from aplomb.datastore import Snapshot
from aplomb.quant.facts import FactContext, LocalLedger, fact_key, make_fact

from .airports import filter_airports, load_airports
from .country_macro import INDICATORS
from .dataset import WorldDataError, WorldDataset
from .facilities import filter_facilities, load_facilities
from .geo import UNKNOWN_COUNTRY, country_name, in_bbox
from .geo_boundaries import geometry_intersects_bbox
from .relationships import event_geography

DEFAULT_FEED_DAYS = 30
MAX_RANGE_DAYS = 366
CATEGORY_COLORS = {
    "monetary_policy": "#1F6F8B", "macro_release": "#2E8B8B", "geopolitical": "#8B3A3A", "trade_regulation": "#6B5B95",
    "corporate": "#B8860B", "energy_commodities": "#8B5A2B", "markets": "#3B6EA5", "natural_disaster": "#A04000",
    "other": "#6C757D",
}
CATEGORY_LABELS = {
    "monetary_policy": ("Monetary policy", "Politique monétaire"), "macro_release": ("Macro release", "Publication macroéconomique"),
    "geopolitical": ("Geopolitical", "Géopolitique"), "trade_regulation": ("Trade and regulation", "Commerce et réglementation"),
    "corporate": ("Corporate", "Entreprises"), "energy_commodities": ("Energy and commodities", "Énergie et matières premières"),
    "markets": ("Markets", "Marchés"), "natural_disaster": ("Natural disaster", "Catastrophe naturelle"), "other": ("Other", "Autre"),
}
# Policy rate first, then inflation (api.md §6.5: "policy rate, CPI where the country is CAN or USA").
COUNTRY_MACRO = {
    "CAN": (("V39079", "pct", 2, "Taux cible du financement à un jour de la Banque du Canada"),
            ("STATIC_TOTALCPICHANGE", "pct", 1, "IPC global du Canada, variation sur douze mois (non désaisonnalisé)")),
    "USA": (("DFF", "pct", 2, "Taux effectif des fonds fédéraux américains"),
            # An index level has no unit in the catalog: it is shown as text with its base.
            ("CPIAUCSL", "text", 1, "IPC des États-Unis, tous consommateurs urbains (indice 1982-84 = 100, désaisonnalisé)")),
}
LINK_ORDER = ("named_in_source", "theme", "listing_country")
# Manifest source record of an event, by the publisher of its primary source.
SOURCE_BY_PUBLISHER = {"U.S. Geological Survey": "usgs_earthquakes", "Bank of Canada": "boc_press",
                       "Federal Reserve Board": "fed_monetary", "Statistics Canada": "statcan_daily", "NASA EONET": "nasa_eonet"}
OBSERVATION_MODES = ("news", "macro", "trade", "energy", "hazards", "conflicts",
                     "aviation", "environment", "infrastructure")
EVENT_MODES = {
    "monetary_policy": "macro", "macro_release": "macro", "geopolitical": "conflicts",
    "trade_regulation": "trade", "energy_commodities": "energy", "natural_disaster": "hazards",
    "corporate": "news", "markets": "news", "other": "news",
}
PROVIDER_MODES = {
    "world_wikimedia_topic_pageviews": "news",
    "world_wikipedia_recent_changes": "news",
    "world_fda_drug_enforcement_counts": "news", "world_crossref_climate_bibliography": "news",
    "world_ted_published_notice_metadata": "trade",
    "world_climate_trace_canada_electricity_co2": "environment",
    "world_ecb_press": "macro", "world_uk_sanctions_updates": "conflicts",
    "world_geoboundaries_fra_adm1": "infrastructure", "world_ucdp_ged_ukraine_2025": "conflicts",
    "world_nasa_cmr_modis_granules": "environment",
}


def _t(en: str, fr: str) -> dict:
    return {"en": en, "fr": fr}


def _invalid(message: str, field: str) -> ServiceError:
    return ServiceError("validation_error", message, {"fields": [{"path": field, "problem": message}]})


class WorldServiceImpl:
    def __init__(self, profiles, snapshot: Callable[[], Snapshot], dataset: Callable[[], WorldDataset],
                 clock: Callable[[], datetime] | None = None) -> None:
        self.profiles = profiles
        self.snapshot = snapshot
        self._dataset = dataset
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    # Shared helpers ---------------------------------------------------------------------------

    def dataset(self) -> WorldDataset:
        try:
            return self._dataset()
        except WorldDataError as exc:
            raise unavailable("World events dataset") from exc

    def _now(self) -> str:
        return self.clock().astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _capture_visible(ds: WorldDataset, query: dict) -> bool:
        """The packaged bundle has no archived vintages before its build.

        An old occurrence date is not evidence that this captured row was known
        on that date. Explicit historical queries must respect the capture date.
        """
        as_of = query.get("asOf")
        return as_of is None or as_of >= ds.built_at[:10]

    def _universe(self):
        snap = self.snapshot()
        return snap.gate(snap.data_as_of, "current").universe()

    def _holdings(self, session_id: str, profile_id: str) -> list[tuple[object, float]]:
        """(asset record, weight in percent) for each position of the session's effective profile."""
        profile = self.profiles.get(session_id, profile_id)
        universe = self._universe()
        return [(universe.get(p.ticker), p.weight_pct) for p in profile.portfolio.positions if p.weight_pct > 0]

    @staticmethod
    def _country_weights(holdings) -> dict[str, list[tuple[str, float]]]:
        out: dict[str, list[tuple[str, float]]] = {}
        for asset, weight in holdings:
            out.setdefault(asset.country or UNKNOWN_COUNTRY, []).append((asset.ticker, weight))
        return out

    def _range(self, ds: WorldDataset, query: dict, default_days: int) -> tuple[str, str]:
        coverage = ds.coverage
        if coverage is None:
            raise unavailable("World events dataset")
        start, end = query.get("from"), query.get("to")
        # A single bound outside the dataset selects nothing; it is kept as a one-day range so no
        # date arithmetic runs on it (year 0001 or 9999 would overflow).
        if end is None and start is not None and start > coverage["end"]:
            end = start
        if start is None and end is not None and end < coverage["start"]:
            start = end
        if end is None:
            end = coverage["end"] if start is None else min(
                coverage["end"], (date.fromisoformat(start) + timedelta(days=MAX_RANGE_DAYS)).isoformat())
            end = max(end, start) if start else end
        if start is None:
            start = (date.fromisoformat(end) - timedelta(days=default_days - 1)).isoformat()
        days = (date.fromisoformat(end) - date.fromisoformat(start)).days
        if not 0 <= days <= MAX_RANGE_DAYS:
            raise _invalid("date range must contain 0 to 366 days", "from")
        return start, end

    @staticmethod
    def _wire_event(event: dict) -> dict:
        return dict(event)

    def provenance(self, event: dict) -> dict:
        """When and under which terms the event row was retrieved, from the bundle manifest."""
        ds = self.dataset()
        wanted = SOURCE_BY_PUBLISHER.get(event["sources"][0]["publisher"])
        record = next((s for s in ds.manifest["sources"] if s["id"] == wanted), {})
        return {"builtAt": ds.built_at, "retrievedAt": record.get("retrievedAt", ds.built_at),
                "licence": record.get("terms", "unknown"), "sourceName": record.get("name", event["sources"][0]["publisher"])}

    @cached_property
    def _provider_capture(self) -> tuple[tuple[dict, ...], tuple[dict, ...]]:
        from .providers import load_provider_snapshots

        return load_provider_snapshots()

    def observations(self, session_id: str, query: dict) -> a.WorldObservationsResponse:
        """Bounded, source-backed world observations for mode and viewport exploration.

        Static airport and facility references stay on their own endpoints: they
        have no valid observation timestamp. Optional provider corruption only
        disables those providers; it does not break the core event feed.
        """
        ds = self.dataset()
        try:
            provider_rows, provider_meta = self._provider_capture
            provider_error = None
        except (ValueError, OSError, KeyError, TypeError):
            provider_rows, provider_meta = (), ()
            provider_error = "Provider capture failed integrity validation."

        mode = query.get("mode")
        if mode is not None and mode not in OBSERVATION_MODES:
            raise _invalid("mode must be a supported world observation mode", "mode")
        bbox = tuple(float(v) for v in query["bbox"].split(",")) if query.get("bbox") else None
        countries = set(query.get("country") or [])
        needle = (query.get("q") or "").strip().casefold()
        if len(needle) > 200:
            raise _invalid("search must contain at most 200 characters", "q")
        start, end = query.get("from"), query.get("to")
        as_of = query.get("asOf")
        rows: list[dict] = []
        provider_countries: dict[str, str] = {}
        if self._capture_visible(ds, query):
            for event in ds.events:
                source = event["sources"][0]
                provenance = self.provenance(event)
                rows.append({
                    "id": event["eventId"], "mode": EVENT_MODES[event["category"]],
                    "title": event["title"], "summary": "Source event; financial effect is not established.",
                    "occurredAt": event["occurredAt"] + "T00:00:00Z",
                    "timeBasis": "event_date",
                    "publishedAt": event["publishedAt"], "retrievedAt": provenance["retrievedAt"],
                    "location": dict(event["location"], geometry=None), "source": {
                        "name": source["publisher"], "url": source["url"]},
                    "countryIso3": event["location"].get("countryIso3"),
                    "datasetId": event["datasetId"],
                    "limitations": ["Occurrence time is known only to the calendar day in this event record.",
                                    "Geographic overlap does not establish issuer exposure or financial effect."],
                })
        for item in provider_rows:
            lat, lon = item.get("latitude"), item.get("longitude")
            if as_of is not None and item["retrievedAt"][:10] > as_of:
                continue
            category = item["category"]
            item_mode = PROVIDER_MODES.get(item["sourceId"], category if category in OBSERVATION_MODES else "news")
            props = item.get("properties") or {}
            manifest = next((m for m in provider_meta if m.get("datasetId") == item["sourceId"]), {})
            attribution = manifest.get("attribution") or props.get("attribution")
            reference_month = (props.get("period") if item["sourceId"] == "world_climate_trace_canada_electricity_co2"
                               and props.get("periodResolution") == "month" else None)
            role = props.get("geographicRole")
            precision = "polygon_anchor" if role == "alert_polygon_representative_anchor" else "point"
            observed = item.get("observedAt") or item.get("publishedAt") or item["retrievedAt"]
            if reference_month:
                observed = reference_month + "-01"
            published = item.get("publishedAt")
            if item.get("countryIso3"):
                provider_countries[item["id"]] = item["countryIso3"]
            rows.append({
                "id": item["id"], "mode": item_mode, "title": item["title"],
                "summary": _observation_summary(item),
                "occurredAt": _utc_stamp(observed), "publishedAt": _utc_stamp(published) if published else None,
                "timeBasis": ("reference_period" if reference_month else
                             (("event_date" if item["sourceId"] == "world_ucdp_ged_ukraine_2025"
                              else "reference_period" if props.get("temporalPrecision") else "source_observation")
                             if item.get("observedAt") else
                             ("event_date" if published else "capture_only"))),
                "retrievedAt": _utc_stamp(item["retrievedAt"]),
                "location": ({"lat": lat, "lon": lon, "countryIso3": item.get("countryIso3"),
                              "precision": precision, "geometry": props.get("geometry")}
                             if lat is not None and lon is not None else None),
                "countryIso3": item.get("countryIso3"),
                "geometry": props.get("geometry"),
                "source": {"name": manifest.get("name", item["sourceId"]),
                           "url": item["sourceUrl"]},
                "datasetId": item["sourceId"],
                "limitations": ([attribution] if isinstance(attribution, str) else [])
                               + ["Current captured source record; no verified historical vintage.",
                                "A point or displayed polygon anchor does not establish issuer exposure or financial effect."]
                               + manifest.get("limitations", []),
            })

        counts = {key: 0 for key in OBSERVATION_MODES}
        for row in rows:
            counts[row["mode"]] += 1
        statuses = [{"mode": key, "available": counts[key] > 0, "count": counts[key],
                     "reason": None if counts[key] else (provider_error or "No geolocated authorized capture is loaded.")}
                    for key in OBSERVATION_MODES]
        if mode:
            rows = [r for r in rows if r["mode"] == mode]
        if countries:
            rows = [r for r in rows if (r["location"]["countryIso3"] if r["location"]
                                        else provider_countries.get(r["id"])) in countries]
        if bbox:
            rows = [r for r in rows if (
                geometry_intersects_bbox(r.get("geometry"), bbox)
                if r["datasetId"] in {"world_geoboundaries_fra_adm1", "world_nasa_cmr_modis_granules"}
                else r["location"] and in_bbox(r["location"]["lat"], r["location"]["lon"], bbox)
            )]
        if start:
            rows = [r for r in rows if r["occurredAt"][:10] >= start]
        if end:
            rows = [r for r in rows if r["occurredAt"][:10] <= end]
        if needle:
            rows = [r for r in rows if needle in r["title"].casefold() or needle in r["source"]["name"].casefold()]
        rows.sort(key=lambda r: (r["occurredAt"], r["id"]), reverse=True)
        version_parts = [ds.version] + [m["dataVersion"] for m in provider_meta]
        version = hashlib.sha256("|".join(sorted(version_parts)).encode()).hexdigest()[:16]
        signature = hashlib.sha256(json.dumps(
            {"version": version, "mode": mode, "bbox": bbox, "country": sorted(countries),
             "q": needle, "from": start, "to": end, "asOf": as_of}, sort_keys=True).encode()).hexdigest()[:16]
        offset = 0
        if query.get("cursor"):
            try:
                token = json.loads(base64.urlsafe_b64decode(query["cursor"].encode()))
                if token["key"] != signature or type(token["offset"]) is not int or token["offset"] < 0:
                    raise ValueError
                offset = token["offset"]
            except Exception as exc:
                raise _invalid("cursor is invalid for this query", "cursor") from exc
        limit = int(query.get("limit", 250))
        page = rows[offset:offset + limit]
        next_cursor = (base64.urlsafe_b64encode(json.dumps({"key": signature, "offset": offset + limit}).encode()).decode()
                       if offset + limit < len(rows) else None)
        return a.WorldObservationsResponse.model_validate({
            "items": page, "total": len(rows), "nextCursor": next_cursor,
            "dataVersion": version, "capturedAt": max([ds.built_at] + [m["retrievedAt"] for m in provider_meta]),
            "modes": statuses,
        })

    # 6.1 layers -------------------------------------------------------------------------------

    def layers(self, session_id: str, query: dict) -> a.WorldLayersResponse:
        try:
            ds: WorldDataset | None = self._dataset()
        except WorldDataError:
            ds = None
        events_ok = ds is not None and bool(ds.events)
        hazards_ok = ds is not None and bool(ds.hazards)
        categories = sorted(ds.manifest["events"]["byCategory"]) if events_ok else []
        try:
            airport_rows, airport_meta = load_airports()
        except (ValueError, OSError, KeyError):
            airport_rows, airport_meta = [], None
        try:
            facility_rows, facility_meta = load_facilities()
        except (ValueError, OSError, KeyError):
            facility_rows, facility_meta = [], None
        items = [
            {"layerId": "airports", "title": _t("Airports · static reference", "Aéroports · référence statique"),
             "tier": "P2", "available": bool(airport_rows), "datasetIds": ["world_airports"],
             "legend": [{"label": _t("Large scheduled-service airport", "Grand aéroport avec service régulier"), "color": "#BCA9F5"}],
             "count": len(airport_rows) if airport_meta else None, "coverage": None},
            {"layerId": "events", "title": _t("Events", "Événements"), "tier": "P1", "available": events_ok,
             "datasetIds": ["world_events"],
             "legend": [{"label": _t(*CATEGORY_LABELS[c]), "color": CATEGORY_COLORS[c]} for c in categories],
             "count": len(ds.events) if events_ok else None, "coverage": ds.coverage if events_ok else None},
            {"layerId": "exposure", "title": _t("Portfolio weight by listing country", "Poids du portefeuille par pays de cotation"),
             "tier": "P1", "available": True, "datasetIds": ["assets_universe"],
             "legend": [{"label": _t("Share of the portfolio listed in the country", "Part du portefeuille cotée dans le pays"),
                         "color": "#1F6F8B"}],
             "count": None, "coverage": None},
            {"layerId": "facilities", "title": _t("Reported emissions · Canada (ECCC)", "Émissions déclarées · Canada (ECCC)"), "tier": "P2",
             "available": bool(facility_rows), "datasetIds": ["emissions_facilities"],
             "legend": [{"label": _t("Reporting facility; no issuer match", "Installation déclarante; aucun émetteur associé"), "color": "#6FD0C5"}],
             "count": len(facility_rows) if facility_meta else None,
             "coverage": {"start": f"{facility_meta['reportingYear']}-01-01", "end": f"{facility_meta['reportingYear']}-12-31"} if facility_meta else None},
            {"layerId": "hazards", "title": _t("Earthquakes (USGS)", "Séismes (USGS)"), "tier": "P2", "available": hazards_ok,
             "datasetIds": ["natural_hazards"],
             "legend": [{"label": _t("Earthquake, magnitude 6 or more", "Séisme de magnitude 6 ou plus"), "color": "#A04000"}],
             "count": len(ds.hazards) if hazards_ok else None,
             "coverage": ds.manifest["hazards"]["coverage"] if hazards_ok else None},
        ]
        return a.WorldLayersResponse.model_validate({"items": items})

    def airports(self, session_id: str, query: dict) -> a.AirportsResponse:
        try:
            rows, meta = load_airports()
        except (ValueError, OSError, KeyError) as exc:
            raise unavailable("Airport snapshot failed integrity validation") from exc
        if meta is None:
            raise unavailable("Airport reference is not loaded")
        # This capture is current reference data, never a historical reconstruction.
        if query.get("asOf"):
            raise _invalid("Airport reference does not support historical queries", "asOf")
        countries = set(query.get("country") or [])
        selected = filter_airports(rows, query=query.get("q", ""),
            bbox=tuple(float(v) for v in query["bbox"].split(",")) if query.get("bbox") else None)
        if countries:
            selected = [row for row in selected if row["countryIso3"] in countries]
        return a.AirportsResponse.model_validate({"items": selected[:query.get("limit", 2000)],
            "total": len(selected), "dataVersion": meta["dataVersion"], "capturedAt": meta["capturedAt"]})

    # 6.2 events -------------------------------------------------------------------------------

    def _filter(self, ds: WorldDataset, query: dict, start: str, end: str) -> list[dict]:
        categories = set(query.get("category") or [])
        countries = set(query.get("country") or [])
        origins = set(query.get("origin") or [])
        allowed = {"gdelt", "official", "curated", "usgs", "firms", "live", "eonet"}
        if origins - allowed:
            raise _invalid("origin must be one of " + ", ".join(sorted(allowed)), "origin")
        needle = (query.get("q") or "").strip().casefold()
        ticker, theme = query.get("ticker"), query.get("theme")
        bbox = tuple(float(v) for v in query["bbox"].split(",")) if query.get("bbox") else None
        out = []
        for ev in ds.events:
            if not start <= ev["occurredAt"] <= end:
                continue
            if categories and ev["category"] not in categories:
                continue
            if origins and ev["origin"] not in origins:
                continue
            if countries and not (countries & set(ev["relatedCountries"])):
                continue
            if ticker and ticker not in ev["relatedTickers"]:
                continue
            if theme and theme not in ev["relatedThemes"]:
                continue
            if bbox and not in_bbox(ev["location"]["lat"], ev["location"]["lon"], bbox):
                continue
            if needle and needle not in ev["title"].casefold() and not any(
                    needle in s["publisher"].casefold() for s in ev["sources"]):
                continue
            out.append(ev)
        return out

    @staticmethod
    def _sorted(events: list[dict], sort: str) -> list[dict]:
        if sort == "date":
            return sorted(events, key=lambda e: (e["occurredAt"], e["eventId"]), reverse=True)
        return sorted(events, key=lambda e: (-e["importance"], _neg_date(e["occurredAt"]), e["eventId"]))

    def events(self, session_id: str, query: dict) -> a.WorldEventsResponse:
        ds = self.dataset()
        start, end = self._range(ds, query, DEFAULT_FEED_DAYS)
        sort = query.get("sort", "importance")
        matches = self._sorted(self._filter(ds, query, start, end), sort) if self._capture_visible(ds, query) else []
        limit = int(query.get("limit", 300))
        # The cursor is bound to the filter set, so a cursor cannot be replayed on another query.
        signature = hashlib.sha256(json.dumps(
            {k: query.get(k) for k in ("category", "country", "origin", "q", "ticker", "theme", "bbox", "asOf")}
            | {"from": start, "to": end, "sort": sort, "v": ds.version}, sort_keys=True).encode()).hexdigest()[:16]
        offset = 0
        if query.get("cursor"):
            try:
                decoded = json.loads(base64.urlsafe_b64decode(query["cursor"].encode()))
                if decoded["k"] != signature or type(decoded["o"]) is not int or decoded["o"] < 0:
                    raise ValueError
                offset = decoded["o"]
            except Exception as exc:
                raise _invalid("cursor is invalid for this query", "cursor") from exc
        page = matches[offset:offset + limit]
        next_cursor = None
        if offset + limit < len(matches):
            next_cursor = base64.urlsafe_b64encode(json.dumps({"k": signature, "o": offset + limit}).encode()).decode()
        relevant = None
        if query.get("profileId"):
            holdings = self._holdings(session_id, query["profileId"])
            held = {asset.ticker for asset, _ in holdings}
            exposed = {c for c in self._country_weights(holdings) if c != UNKNOWN_COUNTRY}
            relevant = (held, exposed)
        items = []
        for ev in page:
            item = self._wire_event(ev)
            if relevant is not None:
                item["portfolioRelevant"] = bool(relevant[0] & set(ev["relatedTickers"]) or relevant[1] & set(ev["relatedCountries"]))
            items.append(item)
        return a.WorldEventsResponse.model_validate({
            "items": items, "nextCursor": next_cursor, "total": len(matches), "coverage": ds.coverage, "dataVersion": ds.version})

    # 6.3 one event ----------------------------------------------------------------------------

    def link_candidates(self, event: dict, holdings) -> list[dict]:
        """Code-only matches, strongest link per holding; never ``documented_exposure`` (api.md §6.3)."""
        rows = []
        for asset, weight in holdings:
            links = []
            if asset.ticker in event["relatedTickers"]:
                links.append(("named_in_source", _t(
                    f"{asset.name} is named in the source title. Financial impact not established.",
                    f"{asset.name} est nommée dans le titre de la source. Incidence financière non établie.")))
            shared = sorted(set(asset.themes) & set(event["relatedThemes"]))
            if shared:
                tags = ", ".join(shared)
                links.append(("theme", _t(
                    f"Proxy link (team assumption): the holding carries the theme tag {tags}, which this kind of event is "
                    "tagged with. Financial impact not established.",
                    f"Lien indirect (hypothèse de l'équipe) : le titre porte l'étiquette thématique {tags}, associée à ce type "
                    "d'événement. Incidence financière non établie.")))
            if asset.country and asset.country in event["relatedCountries"]:
                place = country_name(asset.country)
                links.append(("listing_country", _t(
                    f"Proxy link: listed on an exchange in {place['en']}. A listing location is not revenue or operational "
                    "exposure. Financial impact not established.",
                    f"Lien indirect : coté sur une bourse du pays suivant : {place['fr']}. Un lieu de cotation n'est pas une "
                    "exposition aux revenus ou aux activités. Incidence financière non établie.")))
            if links:
                link, note = min(links, key=lambda item: LINK_ORDER.index(item[0]))
                rows.append({"ticker": asset.ticker, "weightPct": min(weight, 100.0), "linkType": link, "evidenceIds": [],
                             "impact": "not_established", "impactFactId": None, "note": note})
        rows.sort(key=lambda r: (LINK_ORDER.index(r["linkType"]), -r["weightPct"], r["ticker"]))
        return rows

    def event(self, session_id: str, event_id: str, query: dict) -> a.WorldEventResponse:
        ds = self.dataset()
        if not self._capture_visible(ds, query):
            raise NotFound(f"Event {event_id} is unavailable at the requested historical date")
        event = ds.event(event_id)
        if event is None:
            raise NotFound(f"Unknown event {event_id}")
        related = []
        if event["relatedCountries"]:
            day = date.fromisoformat(event["occurredAt"])
            lo, hi = (day - timedelta(days=7)).isoformat(), (day + timedelta(days=7)).isoformat()
            related = [e for e in ds.events if e["eventId"] != event_id and lo <= e["occurredAt"] <= hi
                       and set(e["relatedCountries"]) & set(event["relatedCountries"])]
            related = self._sorted(related, "importance")[:10]
        exposures = []
        if query.get("profileId"):
            exposures = self.link_candidates(event, self._holdings(session_id, query["profileId"]))
        relation = event_geography(event, self.provenance(event))
        geographic_relationships = []
        if relation is not None:
            geographic_relationships.append({
                "relationshipId": relation.relationship_id, "relation": relation.relation,
                "subjectId": relation.subject_id, "objectId": relation.object_id,
                "evidenceClass": relation.evidence_class, "sourceId": relation.evidence.source_id,
                "sourceUrl": relation.evidence.url,
                "normalizedRecordSha256": relation.evidence.content_sha256,
                "retrievedAt": relation.evidence.retrieved_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "limitations": list(relation.evidence.limitations),
            })
        return a.WorldEventResponse.model_validate({
            "event": self._wire_event(event), "related": [self._wire_event(e) for e in related],
            "exposures": exposures, "geographicRelationships": geographic_relationships})

    # 6.4 exposure -----------------------------------------------------------------------------

    def _exposures(self, session_id: str, profile_id: str) -> tuple[list[dict], dict]:
        snap = self.snapshot()
        gate = snap.gate(snap.data_as_of, "current")
        passport = gate.describe("assets_universe")
        ctx = FactContext(snap.data_as_of, self._now(), snap.data_version)
        ledger = LocalLedger()
        weights = self._country_weights(self._holdings(session_id, profile_id))
        items = []
        ordered = sorted(weights.items(), key=lambda kv: (kv[0] == UNKNOWN_COUNTRY, -sum(w for _, w in kv[1]), kv[0]))
        for iso3, rows in ordered:
            total = min(sum(w for _, w in rows), 100.0)
            name = country_name(iso3)
            ledger.add_fact(make_fact(
                ctx, key=fact_key("weight.country", "country", iso3, "before", "weights"), kind="computed", metric="weight.country",
                label=_t(f"Portfolio weight listed in: {name['en']}", f"Poids du portefeuille coté : {name['fr']}"),
                value=total, unit="pct", currency=None, subject={"type": "country", "id": iso3, "variant": "before"},
                method_id="M_PROFILE_ASSUMPTION", created_by="world",
                params={"profile": profile_id, "basis": "listing_country", "holdings": ", ".join(t for t, _ in rows)},
                sources=[{"datasetId": "assets_universe", "dataVersion": snap.data_version, "sourceName": passport["source"],
                          "sourceUrl": passport["sourceUrl"], "retrievedOn": passport["retrievedOn"] or snap.data_as_of,
                          "licence": passport["licence"], "rowsRead": len(rows)}],
                limitations=["LIM_ETF_NO_LOOKTHROUGH"],
                checks=[{"code": "listing_country_sum", "ok": True,
                         "detail": "Sum of the profile's position weights whose listing market is in this country; "
                                   "funds count at their own listing, crypto and cash have no country."}]))
            items.append({"countryIso3": iso3, "weightPct": total, "basis": "listing_country",
                          "holdings": [{"ticker": t, "weightPct": min(w, 100.0)} for t, w in sorted(rows, key=lambda r: (-r[1], r[0]))]})
        return items, ledger.wire()

    def exposure(self, session_id: str, query: dict) -> a.WorldExposureResponse:
        items, facts = self._exposures(session_id, query["profileId"])
        return a.WorldExposureResponse.model_validate({
            "items": items,
            "basisNote": _t(
                "Weights by the country of the exchange where each holding is listed. A fund counts at its own listing "
                f"(no look-through). Crypto and cash have no listing country and are shown under {UNKNOWN_COUNTRY}. "
                "A listing country is not revenue or operational exposure.",
                "Poids selon le pays de la bourse où chaque titre est coté. Un fonds compte à son propre lieu de cotation "
                f"(sans transparence). Les cryptoactifs et les liquidités n'ont pas de pays de cotation et figurent sous {UNKNOWN_COUNTRY}. "
                "Un pays de cotation n'est pas une exposition aux revenus ou aux activités."),
            "limitations": ["LIM_ETF_NO_LOOKTHROUGH", "LIM_IMPACT_NOT_ESTABLISHED"], "facts": facts})

    # 6.5 country panel ------------------------------------------------------------------------

    def _macro_facts(self, iso3: str, as_of: str | None = None) -> list[dict]:
        snap = self.snapshot()
        effective = min(as_of, snap.data_as_of) if as_of else snap.data_as_of
        gate = snap.gate(effective, "historical" if as_of else "current")
        passport = gate.describe("macro_rates")
        ctx = FactContext(effective, self._now(), snap.data_version)
        ledger = LocalLedger()
        for series_id, unit, decimals, label_fr in COUNTRY_MACRO.get(iso3, ()):
            sl = gate.macro(series_id, None, None)
            if not sl.rows:
                continue
            row = sl.rows[-1]
            value = float(row["value"]) if unit != "text" else f"{float(row['value']):.{decimals}f}"
            ledger.add_fact(make_fact(
                ctx, key=fact_key("macro.level", "macro", series_id, "na", "latest"), kind="observed", metric="macro.level",
                label=_t(row["label"], label_fr), value=value, unit=unit, currency=None,
                subject={"type": "macro", "id": series_id, "variant": "na"}, method_id="M_OBSERVED_ROW", created_by="world",
                period={"start": row["date"], "end": row["date"]}, available_at=row.get("available_at"),
                params={"seriesId": series_id, "referenceDate": row["date"], "sourceUnit": row["unit"]}, n_obs=1,
                sources=[{"datasetId": "macro_rates", "dataVersion": snap.data_version, "sourceName": row["source"],
                          "sourceUrl": passport["sourceUrl"], "retrievedOn": passport["retrievedOn"] or snap.data_as_of,
                          "licence": passport["licence"], "rowsRead": 1}],
                limitations=list(sl.limitations), decimals=decimals,
                checks=[{"code": "gated_inputs", "ok": True,
                         "detail": f"Latest row visible through the temporal gate (current, as of {snap.data_as_of}); "
                                   f"{sl.rows_withheld} later row(s) withheld."}]))
        dataset = self.dataset()
        source = dataset.country_macro_manifest
        # Current-only: asOf date queries cannot see WDI rows before capture. These rows
        # are unavailable to replay workflows, which use the separately gated snapshot.
        if source and (as_of is None or source["retrievedAt"][:10] <= as_of):
            context = FactContext(source["retrievedAt"][:10], self._now(), source["dataVersion"])
            for row in dataset.country_macro:
                if row["countryIso3"] != iso3:
                    continue
                indicator = row["indicatorId"]
                en, fr, unit = INDICATORS[indicator]
                year = row["observationYear"]
                ledger.add_fact(make_fact(
                    context, key=fact_key("macro.level", "macro", f"wdi:{iso3}:{indicator}", "na", "latest"),
                    kind="observed", metric="macro.level", label=_t(f"{en} ({year})", f"{fr} ({year})"),
                    value=row["value"], unit=unit, currency="USD" if unit == "usd" else None,
                    subject={"type": "macro", "id": f"wdi:{iso3}:{indicator}", "variant": "na"},
                    method_id="M_OBSERVED_ROW", created_by="world", available_at=row["availableAt"],
                    period={"start": f"{year}-01-01", "end": row["observedAt"]},
                    params={"seriesId": indicator, "countryIso3": iso3,
                            "observationYear": year, "publicationDate": "unknown",
                            "availabilityBasis": "first captured; original vintage unknown"}, n_obs=1,
                    sources=[{"datasetId": "world_bank_indicators", "dataVersion": source["dataVersion"],
                              "sourceName": "World Bank, World Development Indicators",
                              "sourceUrl": f"https://data.worldbank.org/indicator/{indicator}?locations={iso3}",
                              "retrievedOn": row["retrievedAt"][:10], "licence": source["licence"], "rowsRead": 1}],
                    limitations=["LIM_MACRO_REVISED"], decimals=2 if unit == "pct" else 0,
                    checks=[{"code": "wdi_snapshot_integrity", "ok": True,
                             "detail": "Read from checksum-verified WDI snapshot; observation year is not publication date."}]))
        return list(ledger.wire().values())

    def country(self, session_id: str, iso3: str, query: dict) -> a.WorldCountryResponse:
        if len(iso3) != 3 or not iso3.isascii() or not iso3.isalpha() or not iso3.isupper():
            raise _invalid("country must be an uppercase ISO 3166-1 alpha-3 code", "iso3")
        ds = self.dataset()
        start, end = self._range(ds, query, MAX_RANGE_DAYS)
        exposure = None
        if query.get("profileId"):
            exposure = next((item for item in self._exposures(session_id, query["profileId"])[0]
                             if item["countryIso3"] == iso3), None)
        events = ([e for e in ds.events if start <= e["occurredAt"] <= end and iso3 in e["relatedCountries"]]
                  if self._capture_visible(ds, query) else [])
        return a.WorldCountryResponse.model_validate({
            "countryIso3": iso3, "name": country_name(iso3), "exposure": exposure,
            "events": [self._wire_event(e) for e in self._sorted(events, "importance")[:20]],
            "macro": self._macro_facts(iso3, query.get("asOf"))})

    # 6.6 / 6.7 optional layers ----------------------------------------------------------------

    def facilities(self, session_id: str, query: dict) -> a.FacilitiesResponse:
        try:
            rows, meta = load_facilities()
        except (ValueError, OSError, KeyError) as exc:
            raise unavailable("Emissions facilities snapshot failed integrity validation") from exc
        if meta is None:
            raise unavailable("Emissions facilities dataset")
        if query.get("asOf"):
            raise _invalid("Facility capture has no original historical vintages", "asOf")
        selected = filter_facilities(rows, query)
        return a.FacilitiesResponse.model_validate({"items": selected[:query.get("limit", 500)],
            "total": len(selected), "reportingYear": meta["reportingYear"], "capturedAt": meta["capturedAt"],
            "dataVersion": meta["dataVersion"], "limitations": ["LIM_IMPACT_NOT_ESTABLISHED"]})

    def hazards(self, session_id: str, query: dict) -> a.HazardsResponse:
        ds = self.dataset()
        if not ds.hazards:
            raise unavailable("Natural hazards dataset")
        if not self._capture_visible(ds, query):
            return a.HazardsResponse.model_validate({"items": [], "total": 0})
        kind = query.get("type")
        if kind is not None and kind not in ("earthquake", "wildfire"):
            raise _invalid("type must be earthquake or wildfire", "type")
        start, end = query.get("from"), query.get("to")
        bbox = tuple(float(v) for v in query["bbox"].split(",")) if query.get("bbox") else None
        out = [h for h in ds.hazards
               if (kind is None or h["type"] == kind)
               and (start is None or h["occurredAt"][:10] >= start) and (end is None or h["occurredAt"][:10] <= end)
               and (bbox is None or in_bbox(h["lat"], h["lon"], bbox))]
        out.sort(key=lambda h: (h["occurredAt"], h["hazardId"]), reverse=True)
        return a.HazardsResponse.model_validate({"items": out[:int(query.get("limit", 500))], "total": len(out)})

    # Research tool (contracts/tools.md §5: world.search_events) --------------------------------

    def search_events(self, q: str | None = None, country: str | None = None, ticker: str | None = None,
                      start: str | None = None, end: str | None = None, limit: int = 20, as_of: str | None = None,
                      historical: bool = False) -> list[dict]:
        """Events from our own dataset; nothing after ``as_of`` is returned."""
        ds = self.dataset()
        if historical and not self._capture_visible(ds, {"asOf": as_of}):
            return []
        query = {"q": q, "country": [country] if country else None, "ticker": ticker}
        hi = min(x for x in (end, as_of, ds.coverage["end"]) if x)
        lo = start or ds.coverage["start"]
        return self._sorted(self._filter(ds, query, lo, hi), "importance")[:max(1, min(int(limit), 50))]


def _neg_date(iso: str) -> int:
    return -date.fromisoformat(iso).toordinal()


def _utc_stamp(value: str) -> str:
    if len(value) == 10:
        value += "T00:00:00Z"
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Source timestamp has no timezone")
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _observation_summary(row: dict) -> str:
    """Short code-owned description of recorded fields, never an AI summary."""
    props = row.get("properties") or {}
    if row["sourceId"] == "world_openflights_airport_reference":
        return (f"OpenFlights static airport reference {props['iata']} in "
                f"{props['sourceCity']}, {props['sourceCountry']}. "
                "Source reference coordinates; no aircraft movement, current operational status "
                f"or issuer relationship is established. {props['attribution']}")
    if row["sourceId"] == "world_nasa_cmr_modis_granules":
        return (f"NASA MODIS Terra {props['producerGranuleId']} metadata; "
                f"product coverage {props['observationPeriodStart']} to {props['observationPeriodEnd']}. "
                "Polygon shows granule coverage, not a fire detection. No imagery or scientific pixels loaded. "
                "First five granules intersecting a European search region; capture availability applies. "
                f"{props['attribution']}")
    if row["sourceId"] == "world_wikimedia_topic_pageviews":
        return (f"Wikimedia English Wikipedia {props['article']} article: {props['views']:,} "
                f"user-classified pageviews on {props['referenceDate']} across all access types. "
                "Topic attention count; does not identify reader location, unique people, sentiment "
                f"or a confirmed event. {props['attribution']}")
    if row["sourceId"] == "world_ted_published_notice_metadata":
        return (f"TED published procurement notice {props['publicationNumber']}; "
                f"source publication date {props['publicationDate']} (day precision); "
                f"reported buyer countries: {', '.join(props['buyerCountries'])}. "
                "Five-notice first-page sample; buyer country is not contract performance geography. "
                "Publication does not establish an award or realized spending. "
                f"{props['attribution']}")
    if row["sourceId"] == "world_fda_drug_enforcement_counts":
        return (f"FDA {props['classification']}: {props['recordCount']:,} matching drug enforcement records "
                f"with report dates {props['queryPeriodStart']} to {props['queryPeriodEnd']}; "
                f"source last updated {props['sourceLastUpdated']}. "
                "Counts are not unique recalls or current recall alerts. "
                f"{props['attribution']}")
    if row["sourceId"] == "world_crossref_climate_bibliography":
        publication_date = "-".join(str(part).zfill(2) for part in props["publicationDateParts"])
        return (f"Crossref bibliographic metadata: {props['workType']}; DOI {props['doi']}; "
                f"deposited publication date {publication_date} ({props['publicationDateResolution']} precision). "
                "Five-record title-query sample; relevance does not establish scientific validity or geography.")
    if row["sourceId"] == "world_climate_trace_canada_electricity_co2":
        return (f"Climate TRACE modeled Canada electricity-generation CO2 in {props['period']}: "
                f"{props['emissionsQuantity']:,.0f} {props['unit']} (release {props['dataRelease']}). "
                "National estimate; may be revised. First-of-month midnight UTC is a display anchor "
                "for the monthly reference period, not a measurement or publication time.")
    if row["sourceId"] == "world_geoboundaries_fra_adm1":
        return (f"geoBoundaries simplified {props['representedYear']} France ADM1 administrative boundary. "
                "Metropolitan France sample; source polygon has no point coordinates.")
    if row["sourceId"] == "world_ucdp_ged_ukraine_2025":
        return (f"UCDP GED 26.1 Ukraine event {props['eventId']}, possible dates "
                f"{props['dateStart']} to {props['dateEnd']}. Estimated fatalities: "
                f"{props['fatalitiesBest']} best, {props['fatalitiesLow']}–{props['fatalitiesHigh']} range. "
                f"Source location precision code {props['locationPrecision']}; "
                f"date precision code {props['datePrecision']}. "
                "Midnight UTC represents the earliest possible date, not an exact event time.")
    if row["sourceId"] == "world_ecb_press":
        return "ECB press release metadata from the current RSS feed."
    if row["sourceId"] == "world_wikipedia_recent_changes":
        return (f"English Wikipedia {props['changeType']} to article {props['articleTitle']}; "
                f"revision {props['revisionId']}; {props['oldBytes']:,} to {props['newBytes']:,} bytes. "
                "Edit activity does not confirm a real-world event or establish geography or issuer relevance. "
                f"{props['attribution']}")
    if row["sourceId"] == "world_uk_sanctions_updates":
        return "UK Sanctions List publication update note. Consult the current official list and applicable law."
    if row["sourceId"] == "world_usgs_minerals":
        return (f"USGS estimated {props['commodity']} mine production in {props['country']} for "
                f"{props['referenceYear']}: {props['value']:g} {props['unit']}. Country total, not a mine location.")
    if row["sourceId"] == "world_usgs_geojson":
        return (f"USGS reported magnitude {props['magnitude']:g} earthquake epicenter. "
                "Affected area, damage and issuer exposure are not established.")
    if row["sourceId"] == "world_ilo_unemployment_2024":
        return (f"ILOSTAT {props['referenceYear']} unemployment rate for {props['sourceCountry']}: "
                f"{props['unemploymentRate']:g}% of the labor force, total sex, ages 15 and over. "
                f"Source survey code {props['sourceSurveyCode']}. Annual national statistic; "
                f"not a current labor-market signal. {props['attribution']}")
    if row["sourceId"] == "world_bls_us_cpi_2024":
        return (f"U.S. CPI-U all-items city average in {props['referenceMonth']}: {props['index']:g} "
                f"({props['unit']}), not seasonally adjusted. This is an index, not an inflation rate. "
                f"{props['attribution']}")
    if row["sourceId"] == "world_statcan_cpi":
        return (f"Canada all-items CPI in {props['referenceMonth']}: {props['index']:g} "
                f"({props['unit']}), not seasonally adjusted. {props['attribution']}")
    if row["sourceId"] == "world_wgi_political_stability_2024":
        return (f"World Bank WGI 2024 political stability governance score for {props['sourceCountry']}: "
                f"{props['score']:.1f} / 100. Composite estimate for an annual reference period, "
                f"not a current event or financial risk measure. {props['attribution']}")
    if row["sourceId"] == "world_gdelt_event_metadata":
        return (f"GDELT machine-coded Event {props['globalEventId']} lists an action location at "
                f"{props['sourceLocationName']}. The location and event coding are unverified; "
                "the linked publisher content was not fetched or confirmed.")
    if row["sourceId"] in {"world_gdelt_gkg_locations", "world_gdelt_geographic_mentions"}:
        return (f"GDELT machine-extracted article location mention: {props['sourceLocationName']}. "
                "A mention is not an event location or verified article claim; publisher content was not fetched.")
    if row["sourceId"] == "trade_un_comtrade_exports":
        return (f"Source: UN Comtrade. {props['referenceYear']} merchandise exports from {props['reporterName']} "
                f"to the world: US${props['valueUsd']:,.0f}. Country total; conditional reuse applies.")
    if row["sourceId"] == "trade_wits_fuel_exports":
        return (f"WITS, Source: UN Comtrade. {props['referenceYear']} fuel exports from Canada to the world: "
                f"US${props['valueUsdThousands']:,.0f} thousand. Country total; conditional reuse applies.")
    if row["sourceId"] == "trade_unctad_concentration":
        return (f"United Nations Trade and Development Data Hub (UNCTAD), adapted by Aplomb: "
                f"{props['referenceYear']} global export market concentration for "
                f"{props['productLabel']}: {props['concentrationIndex']:.6f}. "
                "Normalized index, not trade value or port activity.")
    if row["category"] == "aviation":
        return f"Airport weather observation at {props.get('stationId', 'station')}: {props.get('metar', 'report unavailable')}."
    if row["category"] == "energy":
        fuel = props.get("primaryFuel")
        capacity = props.get("capacityMw")
        return f"Power plant reference: {capacity} MW of {fuel} generation capacity." if fuel and capacity is not None else "Power plant reference."
    if row["category"] == "trade":
        return "Port location reference. Port activity and issuer exposure are not established."
    if row["category"] == "hazards":
        return f"Official alert: {props.get('event', 'hazard')}; severity {props.get('severity', 'not stated')}."
    if row["sourceId"] == "world_nasa_power":
        return (f"NASA POWER gridded daily 2 m temperature: {props['temperatureC']} °C "
                f"for {props['date']} in local solar time. This is a modeled grid value, not a station measurement.")
    if row["sourceId"] == "world_epa_sems_sites":
        return (f"EPA SEMS site reference in {props['state']}. Source NPL status: "
                f"{props.get('sourceNplStatus') or 'not stated'}. No emissions or company relationship is established.")
    return "Source record. Open the original source for details and publication context."
