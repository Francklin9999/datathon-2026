# Ledger, writer grammar and audit

**Track:** T10. **Tier:** P0; sabotage P1. Public [Fact/Brief/AuditReport](../../../contracts/schemas.md) and [A01–A14](../../../contracts/catalog.md) are authoritative.

## 1. Ledger contract

```python
class Ledger(Protocol):
    def add_fact(self, fact: FactInput) -> str: ...
    def add_evidence(self, evidence: EvidenceInput, document: DocumentRef) -> str: ...
    def get_fact(self, fact_id: str) -> Fact: ...
    def get_evidence(self, evidence_id: str) -> Evidence: ...
    def export(self) -> LedgerView: ...
    def freeze(self) -> LedgerView: ...
```

Allocate deterministic run-local F-/E- IDs, minimum three digits expanding as needed; do not wrap at 999. FactKey includes metric, subject, scenario variant and window; immutable runs distinguish currency/asOf/version in their context. Do not reuse one key for different currency facts within a ledger: use distinct subject variant qualifiers such as `after:currency:USD`. Every input fact ID resolves in the same ledger, with acyclic dependency graph. Verified status requires the checks that actually ran; research facts are not verified just because a model supplied them.

Lineage rule as implemented (2026-11-15, needed for the first real signed decision): an `observed` or `evidence` fact is verified by dated sources; a `computed`, `scenario` or `rule_check` fact is verified when every input fact is verified or, with no input, when it carries dated dataset sources itself (a figure computed straight from gated rows). A declaration by the producer is never used. Producers therefore register what a figure derives from: quant registers the stipulated portfolio composition as an assumption and cites it in weight and concentration facts; rules register the rule definition for statuses that rest on no figure. In historical runs a fact without `availableAt` is accepted only when it is timeless (`core.is_timeless`): an input, an assumption, or a figure with no dataset source, derived only from timeless facts by one of the pure arithmetic or comparison methods in `core.TIMELESS_METHODS`. Figures that read dataset rows state them: weights grouped by a universe label cite `assets_universe` with its availability, and the first-conflict boundary cites the price rows its search read.

Types retain provenance using exact FactKind values: `computed`, `observed`, `assumption`, `input`, `scenario`, `rule_check`, `evidence`. A threshold assumption has a source/rationale/method even if it has no external dataset. `availableAt` is max availability of source inputs; null is permitted for timeless/user assumptions, never for an unknown temporal source presented as verified historical fact.

## 2. Formatting and writer input

Code formats numbers into Fact.display for English/French, with explicit unit/currency/period. Do not round calculations before comparison. Writer receives IDs, labels, values for comprehension, rule statuses, scenario identities and limitations; no raw unbounded source documents. It may propose prose around references but cannot supply numeric displays.

## 3. Writer output grammar (internal)

Return JSON sections with sentence IDs and raw template strings. Allowed references:

```text
{{fact:F-008}}
{{rule:limit.volatility}}
{{status:limit.volatility}}
{{evidence:E-001}}
```

Parser requires exact grammar and known identifiers, rejects nested tokens/unknown directives. It converts references to public Segment objects, computing each `display` from ledger/rules. Never trust a model-written `display`. Rule displays do not interpolate numbers outside references; numbers in trusted status/code/source titles are not treated as raw writer prose. Factual sentences need a fact/evidence token. Required section IDs: facts, assumptions, limits; summary/scenarios/next_checks optional. Sentence IDs unique, stable across audit markings; rewritten sentences receive new IDs or explicit mapping.

Reject digits (including Unicode digits), percentages, numeric literals and number words in free prose. English number-word lexicon: zero through nineteen, tens twenty–ninety, hundred, thousand, million, billion, half, quarter, double, triple. French counterparts: zéro–seize, dix-sept/dix-huit/dix-neuf, vingt/trente/quarante/cinquante/soixante, cent, mille, million, milliard, moitié, quart, double, triple; normalize accents/hyphens for checks. Context like “first” is permitted unless making a numeric claim; model review still checks unsupported quantities. Dates and numeric ticker names must be conveyed through trusted references/metadata, not exempted by ad hoc regex. A lexical filter alone is not a truth guarantee.

## 4. Deterministic audit

Implement A01 reference resolution, A02 literal prohibition, A04 factual citation requirement, A05 mandatory sections, A06 code disclaimer, A07 banned instructions/guarantees, A08 quote match, A11 availability, A12 all conflicting/tension assumptions mentioned, A13 append cited limitations, A14 no unsupported financial-impact statement.

A03 uses model-extracted relations `{leftFactId, operator, rightFactId|literalToken, sentenceId}` and evaluates compatible units/currencies/periods in code. No model confidence can override a false comparison. If extraction is ambiguous, strike rather than certify. Prevalidated relation templates can avoid a model for known comparisons. A09 checks unsupported causal/qualitative interpretation against cited material. Date cutoff compares timestamps to the next-day-exclusive boundary, not a midnight string cast.

When a fact/rule-only structural brief would claim unsupported completeness, fail or use an explicit refusal/limitations result. Strikes are visible in audit view and removed from normal final reading; final factual content must remain useful and mandatory sections intact. If after strikes a mandatory section is empty, rewrite once then fail if still empty. A12 rewrite second failure fails the run (same limit as A05).

## 5. Model review, Guardrails and sign

LLM review returns typed findings with sentence ID, issue and audit code; no self-authored replacement facts. Guardrail applied only when configured/available, record actual ID/action. Blocked text is replaced with fixed refusal and revalidated; never display blocked draft as normal signed output. An unavailable required model review fails signing honestly.

Canonical signing: UTF-8 JSON of `{facts,evidence}` only, sorted object keys recursively, no insignificant whitespace, Unicode preserved, finite numbers only. SHA-256 hex stored in AuditReport, with signedAt from injected clock. Freeze ledger after sign. Sorting sentence order is unnecessary because sentences are outside this hash; retain result-integrity metadata separately if required. A hash proves integrity of this bundle, not external correctness or digital identity.

## 6. Sabotage

Only a succeeded decision can be parent. New child references pinned parent facts, but uses distinct run identity. Modes: invented_number, false_comparison, unsupported_interpretation. Store exact injected instruction and visibly label “demonstration.” The false sentence is built by code from the parent's own verified facts (a real writer model declines to lie, which left nothing to audit): invented_number restates a cited figure with a wrong value, false_comparison reverses two comparable figures, unsupported_interpretation claims a positive impact no measured price move supports. The stored instruction says it is code-written. The audit that follows is the real one (code checks, model review, guardrail). `caught` requires an actually offending sentence and actual failed check. Display unsafe draft only in the clearly marked audit demonstration, struck where appropriate; never reuse it as ordinary brief.

## 7. Verification

LED-01 dangling/cross-run reference and cyclic input rejection. LED-02 EN/FR literal coverage, including comma decimals/Unicode minus and trusted dates. LED-03 reversed comparison/incompatible units. LED-04 quote mismatch and unverified evidence. LED-05 absent/empty mandatory section with one-rewrite bound. LED-06 future/unknown availability rejection in historical mode. LED-07 deterministic hash and changed value changes hash. LED-08 parent immutability/sabotage catch honesty. LED-09 every displayed numeric Segment resolves. LED-10 A12/A13 coverage and render-from-segments XSS safety.
