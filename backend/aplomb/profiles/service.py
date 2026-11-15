"""Profile service (track T06, profiles SPEC §2): defaults + per-session overlays, custom
profiles, rule edits, deterministic overview and performance.

Defaults are read-only; a session's edits to a default are an overlay item holding only the
changed rules/portfolio, merged on read. ``version`` = 1 + overlay revision for defaults and the
stored revision for custom profiles. Threshold derivation and starting-portfolio proposals are
injected (optimizer, T07); without them those operations report ``upstream_unavailable``.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import secrets
import threading
import unicodedata
from collections import OrderedDict
from datetime import date, datetime, timezone
from typing import Callable

from aplomb.api.errors import Conflict, NotFound, ServiceError, unavailable
from aplomb.contracts import api as a
from aplomb.contracts import models as m
from aplomb.datastore import Snapshot, UnknownTicker
from aplomb.quant import LocalLedger, QuantEngine, Unavailable
from aplomb.quant import metrics as mx
from aplomb.quant.engine import slug
from aplomb.rules.definitions import SECTOR_FR, rule_def
from aplomb.rules.engine import RuleEngine, RuleInputs, verdict_of

from .defaults import load_defaults
from .rulebuilder import renumber

# Entries kept by the read cache of each process (overview and performance responses).
READ_CACHE_SIZE = 64

VOL_BUDGET = {"low": 6.0, "low_moderate": 9.0, "moderate": 12.0, "moderate_high": 16.0, "high": 22.0}  # A-02
RISK_ORDER = ("low", "low_moderate", "moderate", "moderate_high", "high")
WINDOW_CODES = ("full", "1y", "3y", "5y", "ytd", "custom")
ISO_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
MAX_POSITIONS = 40
_B32 = "0123456789abcdefghjkmnpqrstvwxyz"  # Crockford base32, lower case (contracts ProfileId)

Deriver = Callable[..., tuple[list[dict], dict[str, m.Fact]]]
Proposer = Callable[..., dict]


def _now(clock: Callable[[], datetime]) -> str:
    return clock().astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validation(message: str, details: dict | None = None) -> ServiceError:
    return ServiceError("validation_error", message, details)


def _fold(label: str) -> str:
    """Slug without accents, so "Énergie", "energie" and "Energy " compare by their letters."""
    return slug("".join(c for c in unicodedata.normalize("NFKD", label) if not unicodedata.combining(c)))


def _window_spec(query: dict | None) -> dict:
    """WindowSpec wire of a read query: ``window`` (default ``full``); ``custom`` also takes
    ``start`` and ``end`` (ISO days, start <= end), from the query or from a ``window`` dict."""
    query = query or {}
    raw = query.get("window") or "full"
    spec = dict(raw) if isinstance(raw, dict) else {"code": raw}
    code = spec.get("code") or "full"
    if code not in WINDOW_CODES:
        raise validation(f"window must be one of {', '.join(WINDOW_CODES)}", {"fields": ["window"]})
    if code != "custom":
        return {"code": code}
    start, end = spec.get("start", query.get("start")), spec.get("end", query.get("end"))
    if not start or not end:
        raise validation("window=custom needs both start and end (YYYY-MM-DD)", {"fields": ["start", "end"]})
    try:
        if not (isinstance(start, str) and isinstance(end, str) and ISO_DAY.fullmatch(start) and ISO_DAY.fullmatch(end)):
            raise ValueError
        d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError:
        raise validation("start and end must be ISO dates (YYYY-MM-DD)", {"fields": ["start", "end"]}) from None
    if d0 > d1:
        raise validation(f"start ({start}) must be on or before end ({end})", {"fields": ["start", "end"]})
    return {"code": "custom", "start": start, "end": end}


class ProfileServiceImpl:
    def __init__(self, repository, snapshot: Callable[[], Snapshot], *, clock: Callable[[], datetime] | None = None,
                 deriver: Deriver | None = None, proposer: Proposer | None = None) -> None:
        self.repo = repository
        self.snapshot = snapshot
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.deriver = deriver
        self.proposer = proposer
        self._defaults = {p.profile_id: p for p in load_defaults()}
        self._frontier_cache: dict[tuple, a.FrontierResponse] = {}
        self._read_cache: OrderedDict[tuple, object] = OrderedDict()
        self._read_lock = threading.Lock()

    # Reads ------------------------------------------------------------------------------------

    def list(self, session_id: str) -> list[m.Profile]:
        out = [self.get(session_id, pid) for pid in self._defaults]
        customs = [item for item in self.repo.list(session_id) if not item.get("overlay")]
        for item in sorted(customs, key=lambda i: i["value"]["createdAt"]):
            profile = m.Profile.model_validate(item["value"])
            if not profile.archived:
                out.append(profile)
        return out

    def duplicate(self, session_id: str, profile_id: str, name: str | None = None):
        profile = self.get(session_id, profile_id)
        data = profile.to_wire()
        body = {key: data[key] for key in ("age", "riskLevel", "horizonYears", "objective", "experience", "reportingCurrency", "preferences")}
        body.update(name=name or (profile.name + " copy")[:40],
            portfolio={"totalValue": profile.portfolio.total_value, "positions": [p.to_wire() for p in profile.portfolio.positions]},
            rules=[{**r.to_wire(), "origin": "imported"} for r in profile.rules], fromDraftRunId=None,
            investorContext=data.get("investorContext"))
        now = _now(self.clock)
        profile_id = "p_" + "".join(secrets.choice(_B32) for _ in range(10))
        cloned = self._custom_body(a.CreateProfileRequest.model_validate(body), profile_id, now, created_at=now)
        if profile.accounts:
            id_map = {account.account_id: "acct_" + secrets.token_hex(6) for account in profile.accounts}
            cloned["accounts"] = [{**account.to_wire(), "accountId": id_map[account.account_id]} for account in profile.accounts]
            cloned["activeAccountId"] = id_map.get(profile.active_account_id, profile.active_account_id)
        cloned["version"] = 1
        self.repo.save(session_id, profile_id, cloned, None)
        return m.Profile.model_validate(cloned)

    def add_exposure_limit(self, session_id: str, profile_id: str, request: a.AddExposureLimitRequest):
        from .rulebuilder import make_rule
        profile, stored = self._load(session_id, profile_id)
        if profile.is_default:
            raise Conflict("Copy a seed profile before adding custom policy rules")
        if profile.version != request.version:
            raise Conflict()
        rid = f"cap.{request.dimension}.{request.key}"
        now = _now(self.clock)
        rules = [r.to_wire() for r in profile.rules if r.rule_id != rid]
        rules.append(make_rule(rid, f"R{len(rules)+1}", threshold=request.threshold, origin="user", derivation=None,
            rationale={"en": "User-defined exposure limit; listing/quotation proxy only, not a regulatory rule or economic look-through.",
                       "fr": "Limite définie par l'utilisateur; approximation par cotation/devise, sans règle réglementaire ni transparence économique."}, updated_at=now))
        self._validate_rules([m.PolicyRule.model_validate(r) for r in rules])
        data = profile.to_wire()
        data.update(rules=renumber(rules), updatedAt=now)
        return self._save(session_id, m.Profile.model_validate(data), stored)

    def goal_funding(self, session_id: str, profile_id: str):
        from .goals import assess_goals
        return assess_goals(self.get(session_id, profile_id), self.snapshot().data_version, _now(self.clock))

    def archived(self, session_id: str) -> list[m.Profile]:
        return [m.Profile.model_validate(item["value"]) for item in self.repo.list(session_id)
                if not item.get("overlay") and item["value"].get("archived", False)]

    def archive(self, session_id: str, profile_id: str, archived: bool, version: int) -> m.Profile:
        profile, stored = self._load(session_id, profile_id)
        if profile.is_default:
            raise Conflict("Seed profiles cannot be archived; copy a template first")
        if profile.version != version:
            raise Conflict()
        data = profile.to_wire()
        data.update(archived=archived, updatedAt=_now(self.clock))
        return self._save(session_id, m.Profile.model_validate(data), stored)

    def get(self, session_id: str, profile_id: str) -> m.Profile:
        return self._load(session_id, profile_id)[0]

    def _load(self, session_id: str, profile_id: str) -> tuple[m.Profile, dict | None]:
        if profile_id in self._defaults:
            overlay = self.repo.get(session_id, profile_id, overlay=True)
            return self._merge(self._defaults[profile_id], overlay), overlay
        item = self.repo.get(session_id, profile_id)
        if item is None:
            raise NotFound(f"Unknown profile {profile_id}")
        return m.Profile.model_validate(item["value"]), item

    def _merge(self, default: m.Profile, overlay: dict | None) -> m.Profile:
        if not overlay:
            return default
        data = default.to_wire()
        ov = overlay["value"]
        changed = ov.get("rules") or {}
        data["rules"] = [copy.deepcopy(changed.get(r["ruleId"], r)) for r in data["rules"]]
        if ov.get("portfolio") is not None:
            data["portfolio"] = copy.deepcopy(ov["portfolio"])
        for field in ("accounts", "activeAccountId"):
            if field in ov:
                data[field] = copy.deepcopy(ov[field])
        data["version"] = 1 + overlay["revision"]
        data["updatedAt"] = ov.get("updatedAt", data["updatedAt"])
        return m.Profile.model_validate(data)

    # Writes -----------------------------------------------------------------------------------

    def _save(self, session_id: str, profile: m.Profile, stored: dict | None) -> m.Profile:
        data = profile.to_wire()
        if data.get("activeAccountId") != "aggregate":
            for account in data.get("accounts", []):
                if account["accountId"] == data.get("activeAccountId"):
                    account["portfolio"] = copy.deepcopy(data["portfolio"])
        if profile.is_default:
            # Overlay = only what differs from the shipped default (profiles SPEC §2 "Storage").
            base = self._defaults[profile.profile_id].to_wire()
            base_rules = {r["ruleId"]: r for r in base["rules"]}
            value = {"rules": {r["ruleId"]: r for r in data["rules"] if r != base_rules.get(r["ruleId"])},
                     "portfolio": data["portfolio"] if data["portfolio"] != base["portfolio"] else None,
                     "updatedAt": data["updatedAt"]}
            for field in ("accounts", "activeAccountId"):
                if field in data:
                    value[field] = copy.deepcopy(data[field])
            revision = stored["revision"] if stored else None
            saved = self.repo.save(session_id, profile.profile_id, value, revision, overlay=True)
            data["version"] = 1 + saved["revision"]
        else:
            revision = stored["revision"]
            data["version"] = revision + 1
            self.repo.save(session_id, profile.profile_id, data, revision)
        return m.Profile.model_validate(data)

    def patch_rule(self, session_id: str, profile_id: str, rule_id: str, threshold: float | None,
                   enabled: bool | None) -> m.Profile:
        profile, stored = self._load(session_id, profile_id)
        data = profile.to_wire()
        rule = next((r for r in data["rules"] if r["ruleId"] == rule_id), None)
        if rule is None:
            raise NotFound(f"Profile {profile_id} has no rule {rule_id}")
        if not rule["editable"]:
            raise Conflict(f"Rule {rule_id} cannot be edited")
        if threshold is None and enabled is None:
            raise validation("Supply threshold or enabled")
        if threshold is not None:
            b = rule["bounds"]
            if rule["threshold"] is None or b is None:
                raise validation(f"Rule {rule_id} has no editable threshold", {"fields": ["threshold"]})
            if not (b["min"] - 1e-9 <= threshold <= b["max"] + 1e-9):
                raise validation(f"threshold must be between {b['min']:g} and {b['max']:g}", {"fields": ["threshold"]})
            rule["threshold"] = float(threshold)
            rule["derivation"] = None
        if enabled is not None:
            rule["enabled"] = bool(enabled)
        now = _now(self.clock)
        rule["origin"] = "user"
        rule["updatedAt"] = now
        data["updatedAt"] = now
        return self._save(session_id, m.Profile.model_validate(data), stored)

    def set_portfolio(self, session_id: str, profile_id: str, portfolio: a.UpdatePortfolioRequest, version: int) -> m.Profile:
        profile, stored = self._load(session_id, profile_id)
        if profile.version != version:
            raise Conflict()
        if profile.active_account_id == "aggregate":
            raise Conflict("Select an individual account before editing holdings")
        positions = [p.to_wire() for p in portfolio.positions]
        self._validate_portfolio(portfolio.total_value, positions)
        now = _now(self.clock)
        data = profile.to_wire()
        data["portfolio"] = {"isFictional": True, "totalValue": float(portfolio.total_value), "currency": profile.reporting_currency,
                             "positions": positions, "updatedAt": now}
        for account in data.get("accounts", []):
            if account["accountId"] == profile.active_account_id:
                if account["portfolio"]["totalValue"] != data["portfolio"]["totalValue"]:
                    account["nativeValuation"] = None
                account["portfolio"] = copy.deepcopy(data["portfolio"])
        data["updatedAt"] = now
        return self._save(session_id, m.Profile.model_validate(data), stored)

    def create(self, session_id: str, request: a.CreateProfileRequest) -> m.Profile:
        now = _now(self.clock)
        profile_id = "p_" + "".join(secrets.choice(_B32) for _ in range(10))
        data = self._custom_body(request, profile_id, now, created_at=now)
        data["version"] = 1
        self.repo.save(session_id, profile_id, data, None)
        return m.Profile.model_validate(data)

    def replace(self, session_id: str, profile_id: str, request: a.UpdateProfileRequest, version: int) -> m.Profile:
        if profile_id in self._defaults:
            raise Conflict("Default profiles cannot be replaced; edit rules or the portfolio instead")
        profile, stored = self._load(session_id, profile_id)
        if profile.version != version:
            raise Conflict()
        if profile.active_account_id == "aggregate":
            raise Conflict("Select an individual account before replacing a profile")
        now = _now(self.clock)
        data = self._custom_body(request, profile_id, now, created_at=profile.created_at)
        if request.rules is None:
            overrides = {r.rule_id: r.to_wire() for r in profile.rules if r.origin in ("user", "imported")}
            derived_ids = {r["ruleId"] for r in data["rules"]}
            data["rules"] = renumber([overrides.get(r["ruleId"], r) for r in data["rules"]]
                + [r for key, r in overrides.items() if key not in derived_ids])
        if profile.accounts:
            if request.reporting_currency != profile.reporting_currency:
                raise Conflict("Account values require explicit FX conversion before changing reporting currency")
            data["accounts"] = [x.to_wire() for x in profile.accounts]
            data["activeAccountId"] = profile.active_account_id
            for account in data["accounts"]:
                if account["accountId"] == profile.active_account_id:
                    if account["portfolio"]["totalValue"] != data["portfolio"]["totalValue"]:
                        account["nativeValuation"] = None
                    account["portfolio"] = copy.deepcopy(data["portfolio"])
        data["archived"] = profile.archived
        data["version"] = stored["revision"] + 1
        self.repo.save(session_id, profile_id, data, stored["revision"])
        return m.Profile.model_validate(data)

    def delete(self, session_id: str, profile_id: str) -> None:
        if profile_id in self._defaults:
            raise Conflict("Default profiles cannot be deleted")
        _, stored = self._load(session_id, profile_id)
        self.repo.delete(session_id, profile_id, stored["revision"])

    def create_account(self, session_id: str, profile_id: str, request: a.CreateAccountRequest) -> m.Profile:
        profile, stored = self._load(session_id, profile_id)
        if profile.version != request.version:
            raise Conflict()
        if not request.name.strip():
            raise validation("Account name must contain a visible character")
        data = profile.to_wire()
        accounts = copy.deepcopy(data.get("accounts", []))
        # Materialize the original account once. Existing profiles need no migration.
        if not accounts:
            primary = "acct_" + secrets.token_hex(6)
            accounts.append({"accountId": primary, "name": "Primary", "portfolio": data["portfolio"]})
            data["activeAccountId"] = primary
        elif data.get("activeAccountId") != "aggregate":
            for account in accounts:
                if account["accountId"] == data.get("activeAccountId"):
                    account["portfolio"] = copy.deepcopy(data["portfolio"])
        if len(accounts) >= 20:
            raise validation("At most 20 accounts per profile")
        portfolio = request.portfolio
        if portfolio is None:
            raise validation("A new account requires explicit holdings and value; existing assets are not duplicated implicitly")
        positions = [p.to_wire() for p in portfolio.positions]
        self._validate_portfolio(portfolio.total_value, positions)
        now = _now(self.clock)
        account_id = "acct_" + secrets.token_hex(6)
        from .account_fx import convert_account_value
        valuation = convert_account_value(self.snapshot(), request.currency or profile.reporting_currency,
            portfolio.total_value, profile.reporting_currency, now)
        saved_portfolio = {"isFictional": True, "currency": profile.reporting_currency,
                           "totalValue": valuation.reporting_value, "positions": positions, "updatedAt": now}
        accounts.append({"accountId": account_id, "name": request.name.strip(), "portfolio": saved_portfolio,
                         "nativeValuation": valuation.to_wire()})
        data.update(accounts=accounts, activeAccountId=account_id, portfolio=saved_portfolio, updatedAt=now)
        return self._save(session_id, m.Profile.model_validate(data), stored)

    def select_account(self, session_id: str, profile_id: str, account_id: str, version: int) -> m.Profile:
        profile, stored = self._load(session_id, profile_id)
        if profile.version != version:
            raise Conflict()
        data = profile.to_wire()
        accounts = copy.deepcopy(data.get("accounts", []))
        if not accounts:
            raise NotFound("No named accounts exist for this profile")
        if data.get("activeAccountId") != "aggregate":
            for account in accounts:
                if account["accountId"] == data.get("activeAccountId"):
                    account["portfolio"] = copy.deepcopy(data["portfolio"])
        if account_id == "aggregate":
            if any(x["portfolio"]["currency"] != profile.reporting_currency for x in accounts):
                raise unavailable("Cross-currency account aggregation needs sourced FX conversion")
            try:
                total = math.fsum(x["portfolio"]["totalValue"] for x in accounts)
            except OverflowError:
                raise validation("Combined account value exceeds the supported finite range") from None
            values = {}
            for account in accounts:
                portfolio = account["portfolio"]
                for position in portfolio["positions"]:
                    ticker = position["ticker"]
                    values[ticker] = values.get(ticker, 0) + portfolio["totalValue"] * (position["weightPct"] / 100)
            positions = [{"ticker": ticker, "weightPct": value / total * 100} for ticker, value in values.items()]
            self._validate_portfolio(total, positions)
            portfolio = {"isFictional": True, "currency": profile.reporting_currency, "totalValue": total,
                         "positions": positions, "updatedAt": _now(self.clock)}
        else:
            account = next((x for x in accounts if x["accountId"] == account_id), None)
            if account is None:
                raise NotFound("Unknown account in this session-owned profile")
            portfolio = account["portfolio"]
        data.update(accounts=accounts, activeAccountId=account_id, portfolio=portfolio, updatedAt=_now(self.clock))
        return self._save(session_id, m.Profile.model_validate(data), stored)

    def rederive_rules(self, session_id: str, profile_id: str, reset: bool, window: m.WindowSpec | None):
        if self.deriver is None:
            raise unavailable("Threshold derivation")
        profile, stored = self._load(session_id, profile_id)
        rules, facts = self.deriver(profile=profile, snapshot=self.snapshot(), window=window.to_wire() if window else None,
                                    created_at=_now(self.clock))
        derived = {r["ruleId"]: r for r in rules}
        merged = []
        for r in profile.to_wire()["rules"]:
            if r["ruleId"] in derived and (r["origin"] == "derived" or (reset and r["origin"] == "user")):
                merged.append({**derived[r["ruleId"]], "enabled": r["enabled"] if not reset else True})
            else:
                merged.append(r)
        data = profile.to_wire()
        data["rules"] = renumber(merged)
        data["updatedAt"] = _now(self.clock)
        return self._save(session_id, m.Profile.model_validate(data), stored), facts

    def _custom_body(self, request: a.CreateProfileRequest, profile_id: str, now: str, created_at: str) -> dict:
        if not request.name.strip():
            raise validation("name must contain a visible character", {"fields": ["name"]})
        hz = request.horizon_years
        if hz.max is not None and hz.max < hz.min:
            raise validation("horizonYears.max must be at least horizonYears.min", {"fields": ["horizonYears"]})
        sectors = self._sector_labels(request.preferences.excluded_sectors)
        request = request.model_copy(update={"preferences": request.preferences.model_copy(update={"excluded_sectors": sectors})})
        if request.rules is not None:
            self._validate_rules(request.rules)
        req = request.to_wire()
        if request.portfolio is not None:
            positions = [p.to_wire() for p in request.portfolio.positions]
            self._validate_portfolio(request.portfolio.total_value, positions)
            portfolio = {"isFictional": True, "totalValue": float(request.portfolio.total_value),
                         "currency": request.reporting_currency, "positions": positions, "updatedAt": now}
        else:
            if self.proposer is None:
                raise unavailable("Starting-portfolio proposal")
            portfolio = self.proposer(request=request, snapshot=self.snapshot(), created_at=now)
        body = {
            "profileId": profile_id, "isDefault": False, "origin": "agent_draft" if req.get("fromDraftRunId") else "user",
            "name": request.name, "initial": request.name.strip()[0].upper()[:1], "age": request.age, "occupation": None,
            "riskLevel": request.risk_level, "horizonYears": req["horizonYears"], "objective": request.objective,
            "objectiveText": _OBJECTIVE[request.objective], "experience": request.experience,
            "reportingCurrency": request.reporting_currency, "preferences": req["preferences"],
            "blurb": {"en": f"Custom fictional profile, {request.risk_level.replace('_', '-')} risk.",
                      "fr": f"Profil fictif personnalisé, risque {request.risk_level.replace('_', ' ')}."},
            "personaTest": None, "portfolio": portfolio, "rules": [], "version": 1, "createdAt": created_at, "updatedAt": now,
        }
        if request.investor_context is not None:
            body["investorContext"] = request.investor_context.model_dump(mode="json", by_alias=True)
        if request.rules is not None:
            body["rules"] = renumber([r.to_wire() for r in request.rules])
        else:
            if self.deriver is None:
                raise unavailable("Threshold derivation")
            rules, _ = self.deriver(profile=m.Profile.model_validate(body), snapshot=self.snapshot(), window=None, created_at=now)
            body["rules"] = renumber(rules)
        return m.Profile.model_validate(body).to_wire()

    def _validate_portfolio(self, total_value: float, positions: list[dict]) -> None:
        if not math.isfinite(total_value) or not total_value > 0:
            raise validation("totalValue must be positive and finite", {"fields": ["totalValue"]})
        if len(positions) > MAX_POSITIONS:
            raise validation(f"At most {MAX_POSITIONS} positions", {"fields": ["positions"]})
        tickers = [p["ticker"] for p in positions]
        if len(set(tickers)) != len(tickers):
            raise validation("Each ticker may appear once", {"fields": ["positions"]})
        total = math.fsum(p["weightPct"] for p in positions)
        if abs(total - 100.0) > 0.01 + 1e-9:  # 99.99 and 100.01 are inside the contract tolerance despite float error
            raise validation(f"Position weights sum to {total:.2f}, not 100", {"fields": ["positions"], "sum": total})
        snap = self.snapshot()
        universe = snap.gate(snap.data_as_of).universe()
        unknown = [t for t in tickers if t not in universe]
        if unknown:
            raise validation(f"Unknown tickers: {', '.join(unknown)}", {"fields": ["positions"], "unknown": unknown})
        if abs(total - 100.0) > 1e-9:
            # Stored weights sum to exactly 100: quant accepts 1e-6 on the fraction, the contract 0.01 on the percent.
            for p in positions:
                p["weightPct"] = p["weightPct"] * 100.0 / total

    def _universe_sectors(self) -> list[str]:
        """Sector labels a sector rule can measure: those of the universe's directly held stocks."""
        snap = self.snapshot()
        return sorted({x.sector for x in snap.gate(snap.data_as_of).universe().all()
                       if x.asset_class == "equity" and x.sector != "unknown"})

    def _sector_labels(self, entries: list[str]) -> list[str]:
        """Universe sector labels named by ``entries`` (English or French label, any case), each
        once and in the order given."""
        if not entries:
            return []
        labels = self._universe_sectors()
        known = {_fold(SECTOR_FR[label]): label for label in labels if label in SECTOR_FR}
        known.update({_fold(label): label for label in labels})
        out, unknown = [], []
        for entry in entries:
            label = known.get(_fold(entry))
            if label is None:
                unknown.append(entry)
            elif label not in out:
                out.append(label)
        if unknown:
            raise validation(f"Unknown sector labels: {', '.join(repr(u) for u in unknown)}",
                             {"fields": ["preferences.excludedSectors"], "unknown": unknown, "valid": labels})
        return out

    def _validate_rules(self, rules: list[m.PolicyRule]) -> None:
        """Caller-supplied rules must agree with the rule definitions the engine measures them with."""
        def bad(message: str) -> ServiceError:
            return validation(message, {"fields": ["rules"]})

        sectors = {slug(label) for label in self._universe_sectors()}
        seen: set[str] = set()
        for r in rules:
            rid = r.rule_id
            try:
                d = rule_def(rid)
            except KeyError:
                raise bad(f"Unknown rule {rid}") from None
            if rid in seen:
                raise bad(f"Rule {rid} appears more than once")
            seen.add(rid)
            if r.type != d.type:
                raise bad(f"Rule {rid} must have type {d.type}")
            if (r.metric != d.metric or r.comparator != d.comparator or r.unit != d.unit
                    or r.target.dimension != d.dimension or r.target.key != d.target_key
                    or r.counts_in_verdict != d.counts):
                raise bad(f"Rule {rid} metadata must agree with its deterministic definition")
            if d.type == "exclude" and r.threshold != 0:
                raise bad(f"Rule {rid} is an exclusion and must use a zero threshold")
            if d.type in ("flag", "evidence", "sim") and r.threshold is not None:
                raise bad(f"Rule {rid} does not accept a numerical threshold")
            if rid.startswith("exclude.sector.") and rid[len("exclude.sector."):] not in sectors:
                raise bad(f"Rule {rid} names no sector of the universe")
            if d.type in ("cap", "floor", "limit", "exclude") and r.threshold is None:
                raise bad(f"Rule {rid} needs a threshold")
            # The lower edit bound is not enforced: derivation itself can emit a 0% crypto cap (A-05).
            if d.bounds and not (-1e-9 <= r.threshold <= d.bounds["max"] + 1e-9):
                raise bad(f"Rule {rid} threshold must be between 0 and {d.bounds['max']:g}")

    # Deterministic analytics ------------------------------------------------------------------

    def _engine(self, profile: m.Profile, query: dict, ledger: LocalLedger):
        window = _window_spec(query)
        snap = self.snapshot()
        gate = snap.gate(snap.data_as_of, "current")
        eng = QuantEngine(gate, ledger, currency=profile.reporting_currency, subject_id=profile.profile_id,
                          created_at=_now(self.clock), window=window)
        if window["code"] == "custom":
            # A caller-chosen range must hold visible history; fixed codes keep their own handling.
            try:
                eng.window(window)
            except Unavailable as exc:
                dates = eng.market.dates
                first, last = (dates[0], dates[-1]) if dates else (None, None)
                raise ServiceError(
                    "insufficient_data",
                    f"No usable history for {window['start']}..{window['end']}: {exc.detail}"
                    + (f" (visible history {first}..{last})" if first else ""),
                    {"fields": ["start", "end"], "reason": exc.reason, "historyStart": first, "historyEnd": last}) from exc
        return eng, window

    @staticmethod
    def _weights(profile: m.Profile) -> dict[str, float]:
        return {p.ticker: p.weight_pct / 100.0 for p in profile.portfolio.positions if p.weight_pct > 0}

    def risk_diagnostics(self, session_id: str, profile_id: str, query: dict) -> a.RiskDiagnosticsResponse:
        profile = self.get(session_id, profile_id)
        ledger = LocalLedger()
        engine, window = self._engine(profile, query, ledger)
        weights = self._weights(profile)
        metrics, contributions = {}, {}
        try:
            wr = engine.window(window)
            tickers = list(weights)
            series = [engine.asset_returns(t, wr.i0, wr.i1) for t in tickers]
            portfolio = mx.portfolio_returns(list(weights.values()), series)
            tail = mx.historical_tail_pct(portfolio)
            shares = mx.variance_shares_pct(list(weights.values()), series)
            composition = engine.view(weights, "before", profile.portfolio.total_value).composition_fact()

            def record(metric, value, method, label, variant="before", missing_reason="short_history"):
                if value is None:
                    return {"value": None, "factId": None, "unavailableReason": missing_reason}
                fid = engine.add_series_fact(
                    metric=metric, value=value, subject={"type": "portfolio", "id": profile_id, "variant": variant},
                    variant_key=variant, window_code=wr.code, tickers=tickers, i0=wr.i0, i1=wr.i1,
                    method_id=method, label={"en": label, "fr": label}, window_spec=wr.spec,
                    params={"weights": json.dumps(weights, sort_keys=True), "reportingCurrency": profile.reporting_currency,
                            "confidence": .95, "holdingPeriodDays": 1, "minimumTailSample": 100},
                    inputs=[composition] if composition else None)
                return {"value": value, "factId": fid, "unavailableReason": None}

            for i, (metric, label) in enumerate((("risk.var95", "Historical daily VaR 95% / VaR historique journalière"),
                                                ("risk.es95", "Historical daily ES 95% / ES historique journalière"))):
                metrics[metric] = record(metric, tail[i] if tail else None, "M_HISTORICAL_TAIL", label)
            for i, ticker in enumerate(tickers):
                contributions[ticker] = record("risk.variance_share", shares[i] if shares else None,
                                               "M_VARIANCE_SHARE", f"{ticker}: variance contribution / contribution à la variance",
                                               variant=f"before:holding:{ticker}",
                                               missing_reason="zero_variance" if len(portfolio) >= 2 else "short_history")
        except Unavailable as exc:
            metrics = {key: {"value": None, "factId": None, "unavailableReason": exc.reason}
                       for key in ("risk.var95", "risk.es95")}
        return a.RiskDiagnosticsResponse.model_validate({"profileId": profile_id, "currency": profile.reporting_currency,
            "dataVersion": engine.gate.data_version, "window": window, "metrics": metrics,
            "contributions": contributions, "facts": ledger.wire()})

    def _cached_read(self, kind: str, profile: m.Profile, query: dict | None, compute: Callable[[], object]):
        """Deterministic reads (overview, performance) cached per process, least recently used out.

        The result depends only on the data snapshot, the profile's full content (holdings, rules,
        name, currency, capital) and the query, so the key holds all three: an edited rule, another
        session's overlay or a new snapshot never reuses an entry, while every session reading an
        unedited default profile shares one. Errors are not cached. Callers get a deep copy.
        """
        content = json.dumps(profile.to_wire(), sort_keys=True, default=str)
        request = json.dumps({k: v for k, v in (query or {}).items() if k != "lang"}, sort_keys=True, default=str)
        key = (kind, self.snapshot().data_version, hashlib.sha256(content.encode()).hexdigest(), request)
        with self._read_lock:
            hit = self._read_cache.get(key)
            if hit is not None:
                self._read_cache.move_to_end(key)
        if hit is None:
            hit = compute()
            with self._read_lock:
                self._read_cache[key] = hit
                self._read_cache.move_to_end(key)
                while len(self._read_cache) > READ_CACHE_SIZE:
                    self._read_cache.popitem(last=False)
        return hit.model_copy(deep=True)

    def overview(self, session_id: str, profile_id: str, query: dict) -> a.OverviewResponse:
        profile = self.get(session_id, profile_id)
        return self._cached_read("overview", profile, query, lambda: self._overview(profile, query))

    def _overview(self, profile: m.Profile, query: dict) -> a.OverviewResponse:
        ledger = LocalLedger()
        eng, window = self._engine(profile, query, ledger)
        weights = self._weights(profile)
        try:
            view = eng.view(weights, "before", profile.portfolio.total_value)
        except UnknownTicker as exc:
            raise ServiceError("insufficient_data", str(exc)) from exc
        snapshot = view.snapshot()
        pm = view.metrics()

        returns, rids = {}, {}
        for field_name, code, metric in (("ytdPct", "ytd", "return.ytd"), ("y1Pct", "1y", "return.trailing"),
                                         ("y3Pct", "3y", "return.trailing"), ("y5Pct", "5y", "return.trailing")):
            try:
                wr = eng.window({"code": code})
                value = mx.period_return_pct(eng.portfolio_levels(weights, wr.i0, wr.i1))
            except Unavailable:
                returns[field_name] = None
                continue
            returns[field_name] = value
            rids[field_name] = eng.add_series_fact(
                metric=metric, value=value, subject=view.subject, variant_key="before", window_code=code, tickers=list(weights),
                i0=wr.i0, i1=wr.i1, method_id="M_PORT_CONST_WEIGHTS", window_spec={"code": code},
                label={"en": f"Portfolio return, {code}, {profile.name}, {profile.reporting_currency}",
                       "fr": f"Rendement du portefeuille, {code}, {profile.name}, {profile.reporting_currency}"})

        # The headline return uses the same window and calendar as the history chart.
        # Add a reference through the existing extensible factIds map (no wire-shape change).
        try:
            wr = eng.window(window)
            value = mx.period_return_pct(eng.portfolio_levels(weights, wr.i0, wr.i1))
            if value is not None:
                rids["selectedPct"] = eng.add_series_fact(
                    metric="return.period", value=value, subject=view.subject, variant_key="before",
                    window_code=window["code"], tickers=list(weights), i0=wr.i0, i1=wr.i1,
                    method_id="M_PORT_CONST_WEIGHTS", window_spec=window,
                    label={"en": "Historical return, selected window", "fr": "Rendement historique, période choisie"})
        except Unavailable:
            pass

        worst12, wid = None, None
        try:
            wr = eng.window(window)
            worst12 = mx.worst_rolling_return_pct(eng.portfolio_levels(weights, wr.i0, wr.i1))
            if worst12 is not None:
                wid = eng.add_series_fact(
                    metric="return.worst_12m", value=worst12, subject=view.subject, variant_key="before", window_code=wr.code,
                    tickers=list(weights), i0=wr.i0, i1=wr.i1, method_id="M_WORST_ROLLING_252", window_spec=window,
                    label={"en": f"Worst 12-month return, {profile.name}", "fr": f"Pire rendement sur 12 mois, {profile.name}"})
        except Unavailable:
            pass
        vol = pm.volatility_pct
        category = next((r for r in RISK_ORDER if vol is not None and VOL_BUDGET[r] >= vol - 1e-12), None)
        if category is None:
            category = "high" if vol is not None else profile.risk_level
        risk_ids = {k: v for k, v in {"volatility": pm.fact_ids.get("vol.annualized"), "maxDrawdown": pm.fact_ids.get("drawdown.max"),
                                      "worst12m": wid, "stress2022": pm.fact_ids.get("stress.replay_2022")}.items() if v}

        top = []
        for p in sorted((x for x in profile.portfolio.positions if x.weight_pct > 0), key=lambda x: -x.weight_pct)[:5]:
            r1 = eng.asset_metrics(p.ticker, {"code": "1y"})["return.period"] if not p.ticker.startswith("CASH.") else None
            top.append({"ticker": p.ticker, "name": view.assets[p.ticker].name, "weightPct": p.weight_pct,
                        "marketValue": p.weight_pct / 100.0 * profile.portfolio.total_value,
                        "return1yPct": r1.value if r1 else None, "assetClass": view.assets[p.ticker].asset_class})

        correlation = None
        if len(weights) <= 20:
            pairs = eng.correlation(list(weights), window)
            usable = [t for t in weights if all(pairs.get((a_, b_), pairs.get((b_, a_))).value is not None
                                                for a_, b_ in [(t, u) for u in weights if u != t])]
            if len(usable) >= 2:
                matrix = [[1.0 if x == y else (pairs.get((x, y)) or pairs.get((y, x))).value for y in usable] for x in usable]
                correlation = {"tickers": usable, "matrix": matrix}

        rule_engine = RuleEngine(ledger, eng.ctx)
        checks = rule_engine.check_rules(profile.rules, RuleInputs(view, profile.profile_id))
        verdict, counts = verdict_of(checks)
        facts = ledger.wire()
        limitations = sorted({lim for f in ledger.facts().values() for lim in f.limitations} | {"LIM_SIMULATION_ONLY"})
        return a.OverviewResponse.model_validate({
            "profileId": profile.profile_id, "asOf": eng.ctx.as_of, "dataVersion": eng.ctx.data_version, "window": window,
            "snapshot": snapshot.to_wire(),
            "returns": {**returns, "factIds": rids},
            "risk": {"volatilityPct": vol, "maxDrawdownPct": pm.max_drawdown_pct, "worst12mPct": worst12,
                     "stress2022Pct": pm.stress2022_pct, "riskCategory": category, "factIds": risk_ids},
            "concentration": {"hhi": pm.hhi, "effectiveN": pm.effective_n, "topPositions": top},
            "correlation": correlation, "ruleChecks": [c.to_wire() for c in checks], "verdict": verdict,
            "counts": counts.to_wire(), "facts": facts, "limitations": limitations,
        })

    def performance(self, session_id: str, profile_id: str, query: dict) -> a.PerformanceResponse:
        profile = self.get(session_id, profile_id)
        return self._cached_read("performance", profile, query, lambda: self._performance(profile, query))

    def _performance(self, profile: m.Profile, query: dict) -> a.PerformanceResponse:
        eng, window = self._engine(profile, query, LocalLedger())
        weights = self._weights(profile)
        try:
            wr = eng.window(window)
            levels = eng.portfolio_levels(weights, wr.i0, wr.i1)
        except Unavailable as exc:
            raise ServiceError("insufficient_data", exc.detail) from exc
        dates = eng.market.dates[wr.i0:wr.i1 + 1]
        start = profile.portfolio.total_value
        series = [{"date": d, "value": start * v} for d, v in zip(dates, levels)]
        benchmark = None
        ticker = (query or {}).get("benchmark")
        if ticker:
            try:
                lv = eng.market.window_levels(ticker, wr.i0, wr.i1)
            except Unavailable as exc:
                if exc.reason == "asset_unknown":
                    raise NotFound(f"Unknown ticker {ticker}") from exc
                raise ServiceError("insufficient_data", exc.detail) from exc
            benchmark = {"ticker": ticker, "series": [{"date": d, "value": start * x / lv[0]} for d, x in zip(dates, lv)]}
        lims = ["LIM_CONSTANT_WEIGHTS", "LIM_SAMPLE_WINDOW", "LIM_PAST_NOT_FUTURE", "LIM_CALENDAR_INTERSECTION", "LIM_YAHOO_NOT_CERTIFIED"]
        if eng.market.fx_rows_used(list(weights) + ([ticker] if ticker else []), wr.i0, wr.i1):
            lims.append("LIM_FX_FFILL")
        return a.PerformanceResponse.model_validate({
            "window": window, "currency": profile.reporting_currency, "series": series, "benchmark": benchmark,
            "method": "M_PORT_CONST_WEIGHTS", "limitations": lims})

    def frontier(self, session_id: str, profile_id: str, query: dict) -> a.FrontierResponse:
        """Descriptive frontier (optimizer SPEC §6); never feeds a rule or a verdict."""
        from aplomb.optimizer.frontier import frontier

        profile = self.get(session_id, profile_id)
        query = dict(query or {})
        # Deterministic in the profile content, the snapshot and the query, and slow to solve
        # (seconds): cached per process. The key holds the full holdings and rules, so another
        # session's overlay or a later edit never reuses an entry.
        content = json.dumps({"portfolio": profile.portfolio.to_wire()["positions"], "rules": [r.to_wire() for r in profile.rules],
                              "currency": profile.reporting_currency, "risk": profile.risk_level}, sort_keys=True)
        key = (self.snapshot().data_version, hashlib.sha256(content.encode()).hexdigest(),
               json.dumps({k: v for k, v in query.items() if k != "lang"}, sort_keys=True, default=str))
        cached = self._frontier_cache.get(key)
        if cached is None:
            eng, _ = self._engine(profile, query, LocalLedger())
            cached = a.FrontierResponse.model_validate(frontier(eng, profile, query))
            if len(self._frontier_cache) >= 64:
                self._frontier_cache.pop(next(iter(self._frontier_cache)))
            self._frontier_cache[key] = cached
        return cached.model_copy(deep=True)

    # Set by the application composition: ``(session_id, profile_id, lang) -> (run | None, stale)``.
    brief_finder: Callable | None = None

    def brief(self, session_id: str, profile_id: str, query: dict):
        """Latest succeeded portfolio brief of this session/profile/language (api.md §3.12)."""
        if self.brief_finder is None:
            raise unavailable("Portfolio brief lookup")
        self.get(session_id, profile_id)
        run, stale = self.brief_finder(session_id, profile_id, (query or {}).get("lang") or "en")
        return a.CachedBriefResponse(run=run, stale=stale)


_OBJECTIVE = {
    "preserve": {"en": "Preserve capital while keeping some growth potential.", "fr": "Préserver le capital tout en gardant un potentiel de croissance."},
    "balanced": {"en": "Balanced capital growth over time.", "fr": "Croissance équilibrée du capital dans le temps."},
    "growth": {"en": "Grow capital over the long term.", "fr": "Faire croître le capital à long terme."},
}
