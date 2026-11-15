"""Strict writer grammar, deterministic checks and fail-closed signing."""

import html
import operator
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from aplomb.contracts.models import (
    AuditReport,
    Brief,
    BriefSection,
    ReviewFinding,
    RuleCheck,
    Sentence,
)

from .core import Ledger, LedgerView, is_timeless

DISCLAIMER = {
    "en": "Simulation with fictional profiles and portfolios. Not financial advice. No order is placed.",
    "fr": "Simulation avec des profils et portefeuilles fictifs. Aucun conseil financier. Aucun ordre transmis.",
}
TOKEN = re.compile(r"{{(fact|rule|status|evidence):([A-Za-z0-9_.-]+)}}")
# French "un"/"une" are the indefinite article, so alone they are not number words;
# UN_QUANTITY keeps them a literal when they count ("un seul") or size a fraction or magnitude.
WORDS = set(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand million billion half quarter double triple zero deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize vingt trente quarante cinquante soixante cent cents mille millions milliard milliards moitie quart".split()
)
UN_QUANTITY = re.compile(
    r"\bune?[\s-]+(?:seule?|tiers|demi\w*|dixieme|centieme|millieme|millier|pourcent"
    r"|points?\s+de\s+(?:pourcentage|base))\b"
)
BANNED = re.compile(
    r"\b(buy|sell|guarantee\w*|will rise|will fall|ach[eè]t\w*|vend(?!redi)\w*|garanti\w*|va augmenter|va baisser)\b",
    re.I,
)
# Applied to normalized() prose. French "plus"/"moins" count only in a comparative form:
# before "que"/"de", or before a degree adjective that no superlative determiner introduces
# ("la plus forte baisse" names a figure; "de plus" and "ne ... plus" compare nothing).
COMPARISON = re.compile(
    r"\b(?:more|less|higher|lower|greater|above|below|exceeds|equal)\b"
    r"|\b(?:superieur|inferieur)(?:e|s|es)?\b|\b(?:depass|exced)\w+|\begal(?:e|es|aux)?\b"
    r"|\b(?:au|en)[\s-]+dess(?:us|ous)\b"
    r"|\b(?:plus|moins)(?:\s+\w+)?\s+qu(?:e\b|['’])"
    r"|\b(?:plus|moins)\s+d(?:e\b|['’])"
    r"|(?<!\ble )(?<!\bla )(?<!\bles )(?<!\bsa )(?<!\bson )(?<!\bses )(?<!\bleur )(?<!\bleurs )"
    r"(?<!\bau )\b(?:plus|moins)\s+(?:elev|haut|bas|faible|fort|grand|petit|important|risqu"
    r"|volatil|concentr)\w*",
    re.I,
)
IMPACT = re.compile(r"\b(?:impact|incidence)\w*")
LOSS_GAIN = re.compile(r"\b(?:profits?|loss(?:es)?|gains?|pertes?|benefices?)\b")
STATUS_WORD = {
    "pass": {"en": "fits", "fr": "respectée"},
    "tension": {"en": "in tension", "fr": "en tension"},
    "conflict": {"en": "in conflict", "fr": "en conflit"},
    "nee": {"en": "not enough evidence", "fr": "preuve insuffisante"},
    "info": {"en": "information", "fr": "information"},
}


def normalized(text):
    return "".join(
        c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c)
    )


def has_literal(text: str) -> bool:
    plain = normalized(text)
    return (
        any(c.isnumeric() for c in text)
        or "%" in text
        or bool(set(re.findall(r"\w+", plain)) & WORDS)
        or bool(UN_QUANTITY.search(plain))
    )


def status_word(status, lang: str) -> str:
    return STATUS_WORD.get(str(status), {}).get(lang, str(status))


@dataclass(frozen=True)
class Relation:
    sentence_id: str
    left_fact_id: str
    operator: str
    right_fact_id: str | None = None
    literal_token: str | None = (
        None  # Must be an exact {{fact:F-...}} token, never an arbitrary model literal.
    )
    ambiguous: bool = False


@dataclass(frozen=True)
class ReviewResult:
    model: str
    findings: list[ReviewFinding] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)


@dataclass(frozen=True)
class GuardrailResult:
    id: str
    action: str  # none, blocked, masked; masked content is not signed without a new draft/review.


class AuditFailure(ValueError):
    def __init__(self, message, report=None, sections=None):
        super().__init__(message)
        self.report, self.sections = report, sections


def parse_draft(
    draft: dict, ledger: LedgerView, lang: str, rules=()
) -> tuple[list[BriefSection], list[dict]]:
    sections, checks, ids, section_ids = [], [], set(), set()
    rule_map = {str(r.rule_id): r for r in rules}

    def failure(code, sid, detail):
        checks.append(dict(code=code, ok=False, kind="code", detail=detail, sentenceIds=[sid]))

    if set(draft) != {"sections"} or not isinstance(draft["sections"], list):
        raise AuditFailure("Writer must return exactly a sections array")
    for raw in draft["sections"]:
        if set(raw) != {"id", "title", "sentences"} or raw["id"] in section_ids:
            raise AuditFailure("Invalid or repeated section")
        section_ids.add(raw["id"])
        sentences = []
        for raw_sentence in raw["sentences"]:
            if set(raw_sentence) != {"id", "template"}:
                raise AuditFailure("Sentence requires exactly id and template")
            sid, template = raw_sentence["id"], raw_sentence["template"]
            if not isinstance(sid, str) or not sid or sid in ids or not isinstance(template, str):
                raise AuditFailure("Invalid/duplicate sentence ID or template")
            ids.add(sid)
            segments, cursor = [], 0
            prose = TOKEN.sub("", template)
            if any(x in prose for x in ("{{", "}}", "{", "}")):
                failure("A01", sid, "Malformed or nested writer token")
            if has_literal(prose):
                failure("A02", sid, "Numeric content outside trusted references")
            if BANNED.search(prose):
                failure("A07", sid, "Instruction, guarantee or prediction")
            for match in TOKEN.finditer(template):
                if match.start() > cursor:
                    segments.append({"t": "text", "text": template[cursor : match.start()]})
                typ, ref = match.groups()
                obj = (
                    ledger.facts.get(ref)
                    if typ == "fact"
                    else ledger.evidence.get(ref)
                    if typ == "evidence"
                    else rule_map.get(ref)
                )
                if obj is None:
                    failure("A01", sid, "Unknown reference")
                    segments.append({"t": "text", "text": "[unresolved reference]"})
                elif typ == "fact":
                    segments.append(
                        {"t": typ, "factId": ref, "display": getattr(obj.display, lang)}
                    )
                    if obj.verification.status != "verified":
                        failure("A04", sid, "Cited fact has unverified provenance")
                elif typ == "evidence":
                    segments.append({"t": typ, "evidenceId": ref, "display": obj.title})
                    if obj.verification.status != "verified":
                        failure("A08", sid, "Evidence quote is unverified or mismatched")
                else:
                    segments.append(
                        {
                            "t": typ,
                            "ruleId": ref,
                            "display": obj.code if typ == "rule" else status_word(obj.status, lang),
                        }
                    )
                cursor = match.end()
            if cursor < len(template):
                segments.append({"t": "text", "text": template[cursor:]})
            if raw["id"] == "facts" and not any(s["t"] in ("fact", "evidence") for s in segments):
                failure("A04", sid, "Factual sentence lacks fact/evidence reference")
            # Free-standing quotations cannot be authenticated merely by citing a document title.
            quotes = re.findall(r'["“«]([^"”»]+)["”»]', prose)
            cited_quotes = [
                ledger.evidence[s["evidenceId"]].quote for s in segments if s["t"] == "evidence"
            ]
            if any(
                " ".join(q.split()) not in {" ".join(c.split()) for c in cited_quotes if c}
                for q in quotes
            ):
                failure("A08", sid, "Writer quotation does not exactly match cited evidence")
            sentences.append(
                Sentence.model_validate(
                    {
                        "id": sid,
                        "segments": segments,
                        "audit": {"status": "verified", "failedChecks": [], "note": None},
                    }
                )
            )
        # Titles are code-owned: raw writer titles are ignored, preventing numeric/XSS title claims.
        sections.append(
            BriefSection.model_validate(
                {
                    "id": raw["id"],
                    "title": {
                        "en": raw["id"].replace("_", " ").title(),
                        "fr": raw["id"].replace("_", " "),
                    },
                    "sentences": sentences,
                }
            )
        )
    for code, detail in (
        ("A01", "Exact writer grammar and references resolved"),
        ("A02", "Free prose checked for Unicode numeric characters and EN/FR number words"),
        ("A04", "Factual references and cited fact provenance checked"),
        ("A07", "Instruction, guarantee and prediction lexicon checked"),
        ("A08", "Cited evidence verification and writer quotations checked"),
    ):
        if not any(item["code"] == code and not item["ok"] for item in checks):
            checks.append(
                dict(code=code, ok=True, kind="code", detail=detail, sentenceIds=sorted(ids))
            )
    return sections, checks


def evaluate_relation(relation: Relation, view: LedgerView, cited: set[str]) -> bool:
    right_id = relation.right_fact_id
    if relation.literal_token:
        match = TOKEN.fullmatch(relation.literal_token)
        if not match or match[1] != "fact" or right_id:
            return False
        right_id = match[2]
    if relation.ambiguous or relation.left_fact_id not in cited or right_id not in cited:
        return False
    left, right = view.facts.get(relation.left_fact_id), view.facts.get(right_id)
    if not left or not right or (left.unit, left.currency) != (right.unit, right.currency):
        return False
    # A stated threshold has no period or window of its own: it bounds the figure whatever the
    # figure's window. Two measured figures must still share period and window.
    stated = any(
        f.kind == "assumption" and f.period is None and f.window is None for f in (left, right)
    )
    if not stated and (left.period, left.window) != (right.period, right.window):
        return False
    if type(left.value) not in (float, int) or type(right.value) not in (float, int):
        return False
    fn = {
        "<": operator.lt,
        "<=": operator.le,
        ">": operator.gt,
        ">=": operator.ge,
        "==": operator.eq,
        "!=": operator.ne,
    }.get(relation.operator)
    return bool(fn and fn(left.value, right.value))


def render_text(sections, *, include_struck=False) -> str:
    """Plain text, never HTML. Use render_html for safe audit demonstration markup."""
    return "\n".join(
        "".join(s.text if s.t == "text" else s.display for s in sentence.segments)
        for section in sections
        for sentence in section.sentences
        if include_struck or sentence.audit.status != "struck"
    )


def render_html(sections, *, include_struck=False) -> str:
    output = []
    for section in sections:
        output.append(f"<section><h2>{html.escape(section.title.en)}</h2>")
        for sentence in section.sentences:
            if sentence.audit.status == "struck" and not include_struck:
                continue
            content = html.escape(
                "".join(s.text if s.t == "text" else s.display for s in sentence.segments)
            )
            output.append(
                f"<p><s>{content}</s></p>"
                if sentence.audit.status == "struck"
                else f"<p>{content}</p>"
            )
        output.append("</section>")
    return "".join(output)


def audit_and_sign(
    ledger: Ledger,
    draft: dict,
    *,
    lang: str,
    model: str,
    rule_checks: tuple[RuleCheck, ...] = (),
    review: Callable | None = None,
    guardrail: Callable | None = None,
    rewrite: Callable | None = None,
    historical: bool = False,
    measured_impact_fact_ids: tuple[str, ...] = (),
) -> Brief:
    """review(sections, LedgerView)->ReviewResult; rewrite(draft, AuditReport)->dict.

    Review is required on every pass. Guardrail(text)->GuardrailResult. All callbacks
    are synchronous and must describe calls actually executed. A failed audit never freezes.
    """
    if review is None:
        raise AuditFailure("Required model review unavailable")
    if ledger._frozen:
        raise AuditFailure("Cannot sign frozen ledger again")
    for attempt in range(2):
        view = ledger.export()
        sections, checks = parse_draft(draft, view, lang, rule_checks)
        by_id = {s.id: s for sec in sections for s in sec.sentences}

        def check(code, ok, detail, ids=(), kind="code"):
            checks.append(dict(code=code, ok=ok, detail=detail, sentenceIds=list(ids), kind=kind))

        cutoff = datetime.combine(
            date.fromisoformat(ledger.as_of) + timedelta(days=1),
            datetime.min.time(),
            tzinfo=timezone.utc,
        )
        temporal_ok = all(
            (f.available_at is not None or is_timeless(f, view.facts) or not historical)
            and (
                not f.available_at
                or datetime.fromisoformat(f.available_at.replace("Z", "+00:00")) < cutoff
            )
            for f in view.facts.values()
        )
        evidence_temporal = all(
            (e.published_at is not None or not historical)
            and (not e.published_at or e.published_at <= ledger.as_of)
            for e in view.evidence.values()
        )
        check(
            "A11", temporal_ok and evidence_temporal, "Next-day-exclusive UTC availability boundary"
        )
        try:
            reviewed = review(sections, view)
        except Exception as exc:
            raise AuditFailure("Required model review unavailable") from exc
        if not isinstance(reviewed, ReviewResult) or not reviewed.model:
            raise AuditFailure("Model review must return typed result and actual model ID")
        for finding in reviewed.findings:
            if not isinstance(finding, ReviewFinding) or finding.sentence_id not in by_id:
                raise AuditFailure("Malformed review finding or unknown sentence")
            check(str(finding.code), False, finding.issue, [finding.sentence_id], "llm")
        check(
            "A09",
            not any(str(f.code) == "A09" for f in reviewed.findings),
            "Required interpretation review executed",
            kind="llm",
        )
        related = set()
        for relation in reviewed.relations:
            if not isinstance(relation, Relation) or relation.sentence_id not in by_id:
                raise AuditFailure("Malformed extracted relation")
            sentence = by_id[relation.sentence_id]
            cited = {s.fact_id for s in sentence.segments if s.t == "fact"}
            check(
                "A03",
                evaluate_relation(relation, view, cited),
                "Code evaluated extracted relation",
                [sentence.id],
            )
            related.add(sentence.id)
        # An event brief's ledger says so itself: its event fact carries the "impact not
        # established" limitation. There a loss or gain is the event's effect on a holding;
        # elsewhere it is a figure of the simulation (the replayed stress loss).
        event_run = bool(measured_impact_fact_ids) or any(
            "LIM_IMPACT_NOT_ESTABLISHED" in map(str, f.limitations) for f in view.facts.values()
        )
        for sid, sentence in by_id.items():
            prose = normalized(" ".join(s.text for s in sentence.segments if s.t == "text"))
            if COMPARISON.search(prose) and sid not in related:
                check("A03", False, "Comparison lacks unambiguous extracted relation", [sid])
            impact = IMPACT.search(prose)
            if not impact and not LOSS_GAIN.search(prose):
                continue
            cited = {s.fact_id for s in sentence.segments if s.t == "fact"}
            if impact or event_run:
                valid = cited & set(measured_impact_fact_ids)
                valid = {i for i in valid if view.facts[i].method.id == "M_PRICE_MOVE_AFTER_EVENT"}
                # Fixed uncertainty statements are safe; arbitrary impact assertions need measurement.
                safe = prose.strip(" .—-") in (
                    "financial impact not established",
                    "impact financier non etabli",
                    "incidence financiere non etablie",
                )
                check(
                    "A14",
                    bool(valid) or safe,
                    "Financial impact requires measured price-move provenance",
                    [sid],
                )
            else:
                check("A14", bool(cited), "Loss or gain statement cites a fact", [sid])
        guard = {"applied": False, "action": "none", "id": None}
        if guardrail:
            try:
                result = guardrail(render_text(sections, include_struck=True))
            except Exception as exc:
                raise AuditFailure("Configured guardrail unavailable") from exc
            if (
                not isinstance(result, GuardrailResult)
                or not result.id
                or result.action not in ("none", "blocked", "masked")
            ):
                raise AuditFailure("Invalid guardrail result")
            guard = {"applied": True, "action": result.action, "id": result.id}
            check(
                "A10",
                result.action == "none",
                "Configured guardrail executed",
                list(by_id) if result.action != "none" else [],
                "guardrail",
            )
        for item in checks:
            if not item["ok"]:
                for sid in item["sentenceIds"]:
                    sentence = by_id[sid]
                    sentence.audit.status = "struck"
                    sentence.audit.failed_checks.append(item["code"])
        # Append only limitations of citations which survive audit; code strings are trusted.
        limitations = sorted(
            {
                str(lim)
                for s in by_id.values()
                if s.audit.status != "struck"
                for seg in s.segments
                if seg.t == "fact"
                for lim in view.facts[seg.fact_id].limitations
            }
        )
        limits_section = next((s for s in sections if s.id == "limits"), None)
        if limits_section:
            for index, limitation in enumerate(limitations):
                sid = f"code-limit-{index}"
                while sid in by_id:
                    sid += "-x"
                limits_section.sentences.append(
                    Sentence.model_validate(
                        {
                            "id": sid,
                            "segments": [{"t": "text", "text": limitation}],
                            "audit": {"status": "verified", "failedChecks": [], "note": None},
                        }
                    )
                )
        check("A13", True, "Appended cited fact limitation codes")
        check("A06", True, "Code inserted simulation disclaimer")
        mandatory = all(
            any(
                sec.id == name
                and any(
                    s.audit.status != "struck"
                    and "".join(
                        seg.text if seg.t == "text" else seg.display for seg in s.segments
                    ).strip()
                    for s in sec.sentences
                )
                for sec in sections
            )
            for name in ("facts", "assumptions", "limits")
        )
        check("A05", mandatory, "Mandatory sections contain surviving sentences")
        mentioned = {
            str(seg.rule_id)
            for sec in sections
            if sec.id == "assumptions"
            for s in sec.sentences
            if s.audit.status != "struck"
            for seg in s.segments
            if seg.t in ("rule", "status")
        }
        required = {str(r.rule_id) for r in rule_checks if r.status in ("conflict", "tension")}
        check("A12", required <= mentioned, "Conflict/tension assumptions all cited")
        fatal = not temporal_ok or not evidence_temporal or guard["action"] != "none"
        structural = not mandatory or not required <= mentioned
        struck = sum(s.audit.status == "struck" for s in by_id.values())
        report = AuditReport.model_validate(
            {
                "status": "failed"
                if fatal or structural
                else ("passed_with_strikes" if struck else "passed"),
                "checks": checks,
                "sentencesChecked": len(by_id),
                "sentencesStruck": struck,
                "rewrites": attempt,
                "guardrail": guard,
                "llmReview": {"model": reviewed.model, "findings": reviewed.findings},
                "ledgerHash": view.digest(),
                "signedAt": ledger.clock(),
            }
        )
        if fatal:
            if guard["action"] != "none":
                # Unsafe blocked draft is never exposed as a normal returned brief.
                sections = [
                    BriefSection.model_validate(
                        {
                            "id": "limits",
                            "title": {"en": "Refusal", "fr": "Refus"},
                            "sentences": [
                                {
                                    "id": "code-refusal",
                                    "segments": [
                                        {
                                            "t": "text",
                                            "text": "Content unavailable after safety review.",
                                        }
                                    ],
                                    "audit": {
                                        "status": "verified",
                                        "failedChecks": [],
                                        "note": None,
                                    },
                                }
                            ],
                        }
                    )
                ]
            raise AuditFailure("Temporal or configured safety check failed", report, sections)
        if structural:
            if attempt == 0 and rewrite:
                new_draft = rewrite(draft, report)
                old = {
                    s["id"]: s["template"] for sec in draft["sections"] for s in sec["sentences"]
                }
                if any(
                    s["id"] in old and old[s["id"]] != s["template"]
                    for sec in new_draft["sections"]
                    for s in sec["sentences"]
                ):
                    raise AuditFailure("Rewritten sentences require new IDs", report, sections)
                draft = new_draft
                continue
            raise AuditFailure(
                "Mandatory structure/assumption check failed after bounded rewrite",
                report,
                sections,
            )
        if ledger.export().digest() != view.digest():
            raise AuditFailure("Ledger mutated during audit", report, sections)
        brief = Brief.model_validate(
            {
                "lang": lang,
                "sections": sections,
                "disclaimer": DISCLAIMER,
                "generatedAt": ledger.clock(),
                "model": model,
                "audit": report,
            }
        )
        ledger.freeze()
        return brief
    raise AuditFailure("Rewrite bound exceeded")


def sabotage_caught(
    report: AuditReport, sections: list[BriefSection], injected_sentence_ids: set[str]
) -> bool:
    """No claimed catch without an actual offending sentence and failed check.

    Writer refusal must pass an empty injected_sentence_ids set. The workflow owns
    the exact extra instruction and demonstration label and invokes a real writer.
    """
    struck = {s.id for sec in sections for s in sec.sentences if s.audit.status == "struck"}
    return any(
        not check.ok and set(check.sentence_ids) & struck & injected_sentence_ids
        for check in report.checks
    )
