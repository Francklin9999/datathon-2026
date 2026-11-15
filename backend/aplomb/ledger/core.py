"""Run-local provenance ledger. Public objects are shared contract models."""

import hashlib
import json
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping

from aplomb.contracts.models import Evidence, Fact, I18nText, Verification


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class DocumentRef:
    reference: str
    text: str
    source_url: str
    run_id: str

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


# Methods that are arithmetic or a comparison on stipulated values only. A derived fact produced
# by any other method must state when its data became available.
TIMELESS_METHODS = frozenset({"M_PROFILE_ASSUMPTION", "M_WEIGHTS_AFTER_MOVE", "M_USER_INPUT", "M_RULE_COMPARE"})


def is_timeless(fact, facts) -> bool:
    """True when a fact carries no dated source: a user input, a stated assumption, or a figure
    derived only from such facts (a weight of the stipulated portfolio, a rule status comparing
    it with a threshold). A fact that read dataset rows is never timeless; it needs ``availableAt``."""
    if fact.kind in ("input", "assumption"):
        return True
    if fact.sources or not fact.inputs or fact.method.id not in TIMELESS_METHODS:
        return False
    return all(i in facts and is_timeless(facts[i], facts) for i in fact.inputs)


@dataclass(frozen=True)
class LedgerView:
    facts: dict[str, Fact]
    evidence: dict[str, Evidence]

    def canonical_bytes(self) -> bytes:
        bundle = {
            "facts": {
                k: v.model_dump(mode="json", by_alias=True, exclude_unset=True)
                for k, v in self.facts.items()
            },
            "evidence": {
                k: v.model_dump(mode="json", by_alias=True, exclude_unset=True)
                for k, v in self.evidence.items()
            },
        }
        return json.dumps(
            bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


def format_value(value, unit: str, currency=None, period=None) -> I18nText:
    def fmt(lang):
        if value is None:
            result = "Unavailable" if lang == "en" else "Indisponible"
        elif isinstance(value, bool):
            result = ("Yes" if value else "No") if lang == "en" else ("Oui" if value else "Non")
        elif isinstance(value, (int, float)):
            if unit in ("cad", "usd") or (unit in ("count", "days") and float(value).is_integer()):
                decimals = 0
            elif unit == "pts":
                decimals = 1
            else:  # percentages, ratios and other measures keep two decimals (0.25% stays 0.25%)
                decimals = 2
            result = f"{value:,.{decimals}f}"
            if lang == "fr":
                result = result.replace(",", "\u202f").replace(".", ",")
            result = result.replace("-", "−")
            suffix = {
                "pct": "%" if lang == "en" else " %",
                "pts": " pts",
                "ratio": "×",
                "count": " count" if lang == "en" else " éléments",
                "days": " days" if lang == "en" else " jours",
                "cad": " CAD",
                "usd": " USD",
            }.get(unit, "")
            result += suffix
            if currency and unit not in ("cad", "usd"):
                result += f" {currency}"
        else:
            result = str(value)
        if period:
            result += f" ({period['start']} – {period['end']})"
        return result

    return I18nText(en=fmt("en"), fr=fmt("fr"))


class Ledger:
    def __init__(self, run_id: str, as_of: str, *, clock: Callable[[], str] = utc_now):
        self.run_id, self.as_of, self.clock = run_id, as_of, clock
        self._facts, self._evidence, self._documents, self._keys = {}, {}, {}, {}
        self._frozen = False

    def _writable(self):
        if self._frozen:
            raise ValueError("Ledger is frozen")

    @contextmanager
    def transaction(self):
        """Rollback this synchronous run-local registration batch on any exception."""
        self._writable()
        state = (self.export(), dict(self._documents), dict(self._keys), self._frozen)
        try:
            yield self
        except BaseException:
            view, self._documents, self._keys, self._frozen = state
            self._facts, self._evidence = view.facts, view.evidence
            raise

    def add_source_fact(self, fact: Fact | Mapping, document: DocumentRef, extraction: dict) -> str:
        from .sources import source_fact

        with self.transaction():
            return source_fact(self, fact, document, extraction)

    def add_pageviews_ratio(
        self, fact: Fact | Mapping, document: DocumentRef, *, article: str
    ) -> str:
        from .sources import pageviews_ratio

        with self.transaction():
            return pageviews_ratio(self, fact, document, article=article)

    def register_document(self, document: DocumentRef) -> None:
        self._writable()
        if document.run_id != self.run_id:
            raise ValueError("Cross-run document")
        if (
            document.reference in self._documents
            and self._documents[document.reference] != document
        ):
            raise ValueError("Document reference cannot be replaced")
        self._documents[document.reference] = document

    def add_fact(self, fact: Fact | Mapping) -> str:
        self._writable()
        data = (
            fact.model_dump(mode="json", by_alias=True, exclude_unset=True)
            if isinstance(fact, Fact)
            else dict(fact)
        )
        # Round-trip shared model normalizes aliases and rejects invalid/nonfinite values.
        data.setdefault("id", f"F-{len(self._facts) + 1:03d}")
        data.setdefault("key", "pending|request:pending|na|full")
        data.setdefault("display", {"en": "", "fr": ""})
        data.setdefault("createdAt", self.clock())
        data.setdefault("verification", {"status": "unverified", "checks": []})
        candidate = Fact.model_validate(data)
        if candidate.as_of != self.as_of:
            raise ValueError("Fact cutoff differs from ledger cutoff")
        if any(i not in self._facts for i in candidate.inputs):
            raise ValueError("Dangling/cross-run/cyclic fact dependency")
        if len(set(candidate.inputs)) != len(candidate.inputs):
            raise ValueError("Repeated fact input")
        window = candidate.window.model_dump(mode="json") if candidate.window else None
        window_key = (
            json.dumps(window, sort_keys=True, separators=(",", ":"))
            if window and window["code"] == "custom"
            else (window["code"] if window else "full")
        )
        key = f"{candidate.metric}|{candidate.subject.type}:{candidate.subject.id}|{candidate.subject.variant}|{window_key}"
        dependencies = [self._facts[i] for i in candidate.inputs]
        dates = [f.available_at for f in dependencies if f.available_at]
        if dates:
            if candidate.available_at:
                dates.append(candidate.available_at)
            candidate.available_at = max(
                dates, key=lambda t: datetime.fromisoformat(t.replace("Z", "+00:00"))
            )
        if any(f.available_at is None and not is_timeless(f, self._facts) for f in dependencies):
            candidate.available_at = None
        provenance = bool(candidate.method.description.en and candidate.method.description.fr)
        if candidate.kind in ("observed", "evidence"):
            provenance = (
                provenance and bool(candidate.sources) and candidate.available_at is not None
            )
        elif candidate.kind in ("computed", "scenario", "rule_check"):
            # Lineage is either verified input facts or, for a figure computed straight from
            # gated dataset rows, the same structure required of an observed fact (dated sources).
            # A producer's own "verified" declaration is never part of this decision.
            if dependencies:
                anchored = all(f.verification.status == "verified" for f in dependencies)
            else:
                anchored = bool(candidate.sources) and candidate.available_at is not None
            provenance = provenance and anchored
        # Incoming model declarations never count as evidence that a check ran.
        candidate.verification = Verification.model_validate(
            {
                "status": "verified"
                if provenance and candidate.created_by != "research"
                else "unverified",
                "checks": [
                    {
                        "code": "LED_PROVENANCE",
                        "ok": provenance,
                        "detail": "Code validated method, source/dependency provenance",
                    }
                ],
            }
        )
        candidate = Fact.model_validate(
            {
                **candidate.model_dump(by_alias=True, exclude_unset=True),
                "id": f"F-{len(self._facts) + 1:03d}",
                "key": key,
                "verification": candidate.verification,
                "display": format_value(
                    candidate.value,
                    candidate.unit,
                    candidate.currency,
                    candidate.period.model_dump() if candidate.period else None,
                ),
            }
        )
        if key in self._keys:
            existing = self._facts[self._keys[key]]
            # Allocation, rendering and verification are ledger-owned outputs. Caller
            # verification declarations were already discarded above; preserve the
            # actual checks on an existing identical registration (including A08).
            excluded = {"id", "display", "created_at", "verification"}
            existing_content = existing.model_dump(mode="json", by_alias=True, exclude=excluded)
            candidate_content = candidate.model_dump(mode="json", by_alias=True, exclude=excluded)
            if existing_content != candidate_content:
                raise ValueError(
                    "Duplicate FactKey has changed value or provenance; qualify scenario/currency variant"
                )
            return existing.id
        self._facts[candidate.id] = candidate
        self._keys[key] = candidate.id
        return candidate.id

    def add_evidence(
        self, evidence: Evidence | Mapping, document: DocumentRef | None = None
    ) -> str:
        self._writable()
        if document:
            self.register_document(document)
        data = (
            evidence.model_dump(mode="json", by_alias=True, exclude_unset=True)
            if isinstance(evidence, Evidence)
            else dict(evidence)
        )
        data.setdefault("id", f"E-{len(self._evidence) + 1:03d}")
        data.setdefault("verification", {"status": "unverified", "checks": []})
        item = Evidence.model_validate(data)
        doc = self._documents.get(item.document_ref)

        def normalize(text):
            return " ".join(text.split())

        ok = bool(
            doc
            and doc.source_url == item.url
            and item.quote
            and normalize(item.quote) in normalize(doc.text)
        )
        item = Evidence.model_validate(
            {
                **item.model_dump(by_alias=True, exclude_unset=True),
                "id": f"E-{len(self._evidence) + 1:03d}",
                "verification": {
                    "status": "verified" if ok else ("failed" if doc else "unverified"),
                    "checks": [
                        {
                            "code": "A08",
                            "ok": ok,
                            "detail": "Exact quote matched cached same-run source"
                            if ok
                            else "Quote/source not verified",
                        }
                    ],
                },
            }
        )
        self._evidence[item.id] = item
        return item.id

    def add_quote_figure(
        self, fact: Fact | Mapping, evidence_id: str, *, value_text: str, unit_text: str
    ) -> str:
        """Register a numeric research fact only after literal value+unit quote validation.

        value_text is source notation (decimal dot/comma; no thousands separators).
        A quote verifier proves presence, not that the source's financial claim is true.
        """
        evidence = self.get_evidence(evidence_id)
        if evidence.verification.status != "verified" or not evidence.quote:
            raise ValueError("Quote figure requires verified evidence")
        normalized_quote = " ".join(evidence.quote.split())
        numeric_pattern = r"(?<![0-9.,])" + re.escape(value_text) + r"(?![0-9]|[.,][0-9])"
        unit_pattern = r"(?<![A-Za-z])" + re.escape(unit_text) + r"(?![A-Za-z])"
        pair_pattern = (
            "(?:"
            + numeric_pattern
            + r"\s*"
            + unit_pattern
            + "|"
            + unit_pattern
            + r"\s*"
            + numeric_pattern
            + ")"
        )
        if not value_text or not unit_text or not re.search(pair_pattern, normalized_quote):
            raise ValueError("Value and explicit unit must occur in verified quote")
        if not re.fullmatch(r"[−+\-]?[0-9]+(?:[.,][0-9]+)?", value_text):
            raise ValueError("Ambiguous source numeric notation")
        data = (
            fact.model_dump(mode="json", by_alias=True, exclude_unset=True)
            if isinstance(fact, Fact)
            else dict(fact)
        )
        numeric = float(value_text.replace("−", "-").replace(",", "."))
        if type(data.get("value")) not in (float, int) or data["value"] != numeric:
            raise ValueError("Fact value differs from source literal")
        unit = str(data.get("unit"))
        allowed_units = {
            "pct": {"%", "percent", "pour cent"},
            "cad": {"CAD", "C$"},
            "usd": {"USD", "US$"},
            "days": {"days", "jours"},
            "count": {"count", "nombre"},
            "ratio": {"ratio", "×"},
            "pts": {"pts", "points"},
        }
        if unit_text not in allowed_units.get(unit, set()):
            raise ValueError("Source unit incompatible with fact unit")
        sources = data.get("sources", [])

        def source_url(source):
            if hasattr(source, "source_url"):
                return source.source_url
            return source.get("sourceUrl", source.get("source_url"))

        if not any(source_url(source) == evidence.url for source in sources):
            raise ValueError("Fact source must match verified evidence URL")
        data["kind"], data["createdBy"] = "evidence", "research"
        data["method"] = {
            "id": "M_QUOTE_VERBATIM",
            "description": {
                "en": "Exact value and unit in verified source quote",
                "fr": "Valeur et unité exactes dans la citation vérifiée",
            },
            "params": {"evidenceId": evidence_id},
        }
        fact_id = self.add_fact(data)
        saved = self._facts[fact_id]
        saved.verification = Verification.model_validate(
            {
                "status": "verified",
                "checks": [
                    {
                        "code": "A08",
                        "ok": True,
                        "detail": f"Literal value/unit matched {evidence_id}; document {self._documents[evidence.document_ref].content_hash}",
                    }
                ],
            }
        )
        return fact_id

    def get_fact(self, fact_id: str) -> Fact:
        return self._facts[fact_id].model_copy(deep=True)

    def get_evidence(self, evidence_id: str) -> Evidence:
        return self._evidence[evidence_id].model_copy(deep=True)

    def export(self) -> LedgerView:
        return LedgerView(
            {k: v.model_copy(deep=True) for k, v in self._facts.items()},
            {k: v.model_copy(deep=True) for k, v in self._evidence.items()},
        )

    def checkpoint(self) -> dict:
        """Internal persistence only; never accept this state from writer/tool arguments."""
        view = self.export()
        return {
            "runId": self.run_id,
            "asOf": self.as_of,
            "frozen": self._frozen,
            "facts": {k: v.to_wire() for k, v in view.facts.items()},
            "evidence": {k: v.to_wire() for k, v in view.evidence.items()},
            "documents": [
                {
                    "reference": d.reference,
                    "text": d.text,
                    "source_url": d.source_url,
                    "run_id": d.run_id,
                    "content_hash": d.content_hash,
                }
                for d in self._documents.values()
            ],
            "hash": view.digest(),
        }

    @classmethod
    def restore(cls, run_id: str, as_of: str, state: Mapping, *, clock=utc_now):
        if state["runId"] != run_id or state["asOf"] != as_of:
            raise ValueError("Checkpoint run/cutoff mismatch")
        ledger = cls(run_id, as_of, clock=clock)
        ledger._facts = {k: Fact.model_validate(v) for k, v in state["facts"].items()}
        ledger._evidence = {k: Evidence.model_validate(v) for k, v in state["evidence"].items()}
        expected_facts = [f"F-{i:03d}" for i in range(1, len(ledger._facts) + 1)]
        expected_evidence = [f"E-{i:03d}" for i in range(1, len(ledger._evidence) + 1)]
        if set(ledger._facts) != set(expected_facts) or set(ledger._evidence) != set(
            expected_evidence
        ):
            raise ValueError("Checkpoint has discontinuous IDs")
        seen = set()
        for key in expected_facts:
            fact = ledger._facts[key]
            if fact.id != key or fact.as_of != as_of or any(i not in seen for i in fact.inputs):
                raise ValueError("Checkpoint fact graph invalid")
            if fact.key in ledger._keys:
                raise ValueError("Checkpoint duplicate FactKey")
            ledger._keys[fact.key] = key
            seen.add(key)
        if any(e.id != k for k, e in ledger._evidence.items()):
            raise ValueError("Checkpoint evidence ID mismatch")
        for raw in state["documents"]:
            raw = dict(raw)
            expected_hash = raw.pop("content_hash")
            document = DocumentRef(**raw)
            if document.content_hash != expected_hash:
                raise ValueError("Checkpoint document integrity mismatch")
            ledger.register_document(document)
        if ledger.export().digest() != state["hash"]:
            raise ValueError("Checkpoint bundle integrity mismatch")
        ledger._frozen = bool(state["frozen"])
        return ledger

    def freeze(self) -> LedgerView:
        self._frozen = True
        return self.export()


def fork_for_sabotage(parent_run, parent_ledger: Ledger, child_run_id: str) -> Ledger:
    """Pin a succeeded decision parent's bundle into an isolated demonstration ledger."""
    if (
        parent_run.status != "succeeded"
        or parent_run.kind != "decision"
        or parent_run.result is None
    ):
        raise ValueError("Sabotage requires a succeeded decision parent")
    if parent_run.run_id != parent_ledger.run_id or child_run_id == parent_run.run_id:
        raise ValueError("Sabotage requires distinct run identity and matching parent")
    if not parent_ledger._frozen:
        raise ValueError("Sabotage parent must be signed/frozen")
    pinned = parent_ledger.export()
    if parent_run.facts != pinned.facts or parent_run.evidence != pinned.evidence:
        raise ValueError("Parent bundle differs from pinned ledger")
    child = Ledger(child_run_id, parent_ledger.as_of, clock=parent_ledger.clock)
    child._facts, child._evidence = pinned.facts, pinned.evidence
    child._keys = {f.key: f.id for f in pinned.facts.values()}
    child._documents = dict(parent_ledger._documents)
    return child
