"""Query normalization; repeated world filters remain lists for providers."""

import math
from datetime import date

from pydantic import TypeAdapter, ValidationError

from aplomb.contracts import models as m
from aplomb.contracts.base import ProfileId
from aplomb.contracts.catalog import ThemeTag

from .errors import ServiceError


def parameters(request, kind: str) -> dict:
    query = dict(request.query_params)
    try:
        if kind.startswith("world"):
            for key in ("category", "country", "origin"):
                if key in request.query_params:
                    query[key] = request.query_params.getlist(key)
            if "category" in query:
                TypeAdapter(list[m.EventCategory]).validate_python(query["category"])
            for country in query.get("country", []):
                if len(country) != 3 or not country.isascii() or not country.isupper():
                    raise ValueError("country must use uppercase ISO3")
        if "profileId" in query:
            TypeAdapter(ProfileId).validate_python(query["profileId"])
        if kind == "world_exposure" and "profileId" not in query:
            raise ValueError("profileId is required")
        limits = {
            "assets": (50, 500),
            "world_events": (300, 1000),
            "world_facilities": (500, 2000),
            "world_hazards": (500, 2000),
        }
        if kind in limits:
            default, maximum = limits[kind]
            limit = int(query.get("limit", default))
            if not 1 <= limit <= maximum:
                raise ValueError(f"limit must be between 1 and {maximum}")
            query["limit"] = limit
        for key in ("from", "to", "asOf", "start", "end"):
            if key in query:
                if len(query[key]) != 10:
                    raise ValueError(f"{key} must be an ISO date")
                date.fromisoformat(query[key])
        if "from" in query and "to" in query:
            days = (date.fromisoformat(query["to"]) - date.fromisoformat(query["from"])).days
            if not 0 <= days <= 366:
                raise ValueError("date range must contain 0–366 days")
        if "bbox" in query:
            bbox = [float(value) for value in query["bbox"].split(",")]
            if (
                len(bbox) != 4
                or not all(math.isfinite(v) for v in bbox)
                or not -180 <= bbox[0] <= bbox[2] <= 180
                or not -90 <= bbox[1] <= bbox[3] <= 90
            ):
                raise ValueError("bbox must be minLon,minLat,maxLon,maxLat")
        if "minEmissions" in query:
            value = float(query["minEmissions"])
            if not math.isfinite(value) or value < 0:
                raise ValueError("minEmissions must be a non-negative number")
            query["minEmissions"] = value
        if "window" in query:
            TypeAdapter(m.WindowCode).validate_python(query["window"])
            if query["window"] == "custom":
                m.WindowSpec(code="custom", start=query.get("start"), end=query.get("end"))
        if "sort" in query and query["sort"] not in {"importance", "date"}:
            raise ValueError("sort must be importance or date")
        for key, annotation in (
            ("currency", m.Currency),
            ("assetClass", m.AssetClass),
            ("theme", ThemeTag),
        ):
            if key in query:
                TypeAdapter(annotation).validate_python(query[key])
        if "tier" in query and query["tier"] not in {"starter", "extended", "on_demand"}:
            raise ValueError("Unknown universe tier")
        if "lang" not in query:
            language = (
                request.headers.get("accept-language", "en")
                .split(",")[0]
                .split(";")[0]
                .split("-")[0]
            )
            query["lang"] = language if language in {"en", "fr"} else "en"
        TypeAdapter(m.Lang).validate_python(query["lang"])
    except (ValidationError, ValueError, TypeError) as exc:
        raise ServiceError(
            "validation_error", "Invalid query parameters", {"problem": str(exc).split("\n")[0]}
        ) from exc
    return query
