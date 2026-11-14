# Evidence & Audit — inspect the result

**Owner:** T14. **Tier:** P0; sabotage P1. Route `/evidence-audit/?runId=...&factId=...`.

## Inputs and panels

Load full owned Run, or list session runs when no ID selected. Panels: brief with audit markings; fact/evidence ledger searchable by ID/metric/kind; rule checks and assumptions; audit A01–A14 results; actual step/tool timeline; data/source passports. “Passed” badge describes reported checks, not external data certification. Guardrail not configured is “Not applied,” never implied executed.

Fact drawer uses `/runs/{id}/facts/{factId}` for exact provenance, one-level input facts and usedBy sentence/rule IDs. Display kind/value/unit/currency/window/actual dates/asOf/availability, method/params, nObs, source/retrieval/licence/version, verification and limitations. Evidence drawer shows claim/quote/publisher/date/URL/tier and whether quote was verified. No raw internal model reasoning.

## Audit rendering

Normal brief hides struck unsafe content; this audit page shows it struck with exact failed codes and note. Repaired sentences distinguish original and final status without reusing old numeric values. Ledger hash and signedAt can be copied/downloaded with the bundle, described as integrity metadata, not proof of truth. Open external links safely without interpreting source text as markup.

## Sabotage

Visible toggle/button only for succeeded decision with flag on. Explicitly marked demonstration; choose injected-number/false-comparison/unsupported-interpretation mode, create child run and preserve parent. Show exact injected instruction, actual offending draft, failed checks and after-audit result. caught=false is a valid outcome (writer may refuse to lie); never force “auditor caught it” display. Struck lie remains confined to labelled audit panel.

## Verification

AUDUI-01 every reference resolves within proper run. AUDUI-02 fact/evidence missing/forbidden 404 state. AUDUI-03 audit kind/code/strike/repair rendering. AUDUI-04 parent immutable after sabotage. AUDUI-05 no catch claim without actual failed checks. AUDUI-06 keyboard drawer focus return and deep-link restore. AUDUI-07 failed runs retain useful trace/facts with no signed-result claim.
