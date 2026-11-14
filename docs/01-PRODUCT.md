# 01 — Product requirements and journeys

## Purpose and boundary

Question: “Does this hypothetical change fit this fictional investor's plan, and what supports the answer?” The main interaction is a decision review, useful for preparing a discussion or comparing scenarios. There is no brokerage connection or order placement. Facts, assumptions, historical scenarios, evidence and limitations remain distinct.

The full P0 + P1 plan is the owner's chosen scope (D-01). Detailed SRS and original plan were supplied in conversation but their originals are not in the repository (O-09). This document records the resulting requirements; it does not claim to reproduce those originals verbatim.

## User journeys

| Journey | Input | Observable result |
|---|---|---|
| Review Robert's request | Robert, +25 percentage points TSLA, explicit pro-rata funding | Conflict; six conflicting financial checks; 6.0-point first-conflict boundary, which can still be in tension |
| Contrast personas | Same TSLA request for Robert and Amira | Both conflict at 25 points, for different reasons; at 10 points Robert conflicts and Amira is in tension |
| Test preferences | Mateo, +10 CNQ.TO | Financial checks pass, direct Energy exclusion conflicts, controversy evidence is missing |
| Explore a goal | Theme, desired exposure and optional risk bounds | Best-fit hypothetical scenario plus 2–3 candidates when enough distinct feasible candidates exist; fewer with an explicit reason otherwise |
| Inspect a claim | Click a number or citation | Fact, method, period, currency, source version, availability and verification |
| Challenge an explanation | Sabotage a completed decision | Separate demonstration run; injected text, failed checks and repaired/struck output visible |
| Explore an event | Globe pin and selected profile | Cited event, documented exposure mechanisms, uncertainty; no invented causal price effect |
| Travel back | Supported historical date and request | Date-gated decision, withheld-row counts; future outcome available only through a separate reveal |

## Required capabilities

| ID | Tier | Requirement | Primary owner |
|---|---|---|---|
| EF-01–03 | P0 | Three personas, fictional holdings, editable plan assumptions | T06 |
| EF-04–05 | P0 | Asset/size input; explicit funding, window, currency; risk and concentration before/after | T05/T14 |
| EF-06–07 | P0 | Code evaluates every rule, aggregate verdict and largest size before first conflict | T06/T07 |
| EF-08–09 | P0 | ESG evidence gaps and aggressive-profile diversification remain visible | T06/T09 |
| EF-10–11 | P0 | Side-by-side contrast, deterministic slider and threshold edits | T14 |
| EF-12–14 | P0 | Facts/assumptions/limits, number drilldown and genuine execution trace | T08/T10/T14 |
| EF-15–16 | P0 | Source passports, simulation disclaimer and no execution tools | T04/T13 |
| EXT-01 | P1 | Goals, alternatives and funding comparison | T07/T08 |
| EXT-02 | P1 | Globe, event briefing and exposure layers | T11/T15 |
| EXT-03 | P1 | Sabotage demonstration | T10/T14 |
| EXT-04 | P1 | Historical gate and reveal | T12/T15 |
| EXT-05 | P1 | Profile creator, including confirmed text draft | T06/T08/T13 |
| EXT-06 | P1 | French UI and explanations; descriptive frontier | T13/T07 |

## Semantics users must understand

- `sizePct` adds points of the current portfolio value; it is not a target final weight. New-money funding changes the denominator.
- “Compatible” describes the enabled assumptions and available evidence, not suitability or a recommendation to transact.
- Verdict precedence is conflict → tension → insufficient → compatible. Evidence gaps remain displayed even when conflict or tension wins the headline.
- “Largest compatible size” in API identifiers actually permits tension and evidence gaps; UI label: **largest size before the first rule conflict**. Display unresolved evidence next to it.
- ETF sector/single-name look-through is informational unless contracts change. Listing country is not revenue exposure.
- Today's weights applied to past returns are simulated constant-weight history, not actual investor performance.

## Performance and failure behavior

Target completed analysis under 90 s, hard budget 180 s; visible progress comes from real persisted steps. Preview `/check` is code-only and targets 1.5 s warm. Cache Home briefs per session, profile version, data version, language and window. Unknown/short history yields explicit unavailability, never zero risk. Bedrock failure preserves deterministic figures and shows the failed run; it cannot silently produce a successful fixture run.
