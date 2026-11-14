# 06 — Challenge constraints translated into implementation

This file is a product constraint map, not legal or investment guidance. Official challenge files remain under `Datathon2026/`. Profile wording is from the brief; portfolios, thresholds and classification assumptions are ours.

| Constraint | Enforcement | Acceptance evidence |
|---|---|---|
| Simulation and fictional profiles | Code-inserted disclaimer on every page and brief; `Portfolio.isFictional = true`; no execution tool or broker credentials | AT-10 |
| No predictions from past returns | Metrics labelled historical, frontier illustration excluded from verdicts and thresholds | AT-06/AT-17 |
| Verifiable explanations | Ledger references, fixed numeric display, comparison/citation checks, facts/assumptions/limits sections | AT-07/AT-08 |
| Observable actions, no internal model reasoning | Timeline records actual roles/tools/durations/inputs and data references; summaries are code templates | AT-09 |
| Public-source documentation | Every dataset has a passport, retrieval date, processing and terms; unknown terms remain unknown | AT-11 |
| Point-in-time consistency | Temporal gate on every tool read, unavailable monthly vintages withheld from replay | AT-13 |
| Real AWS contribution | Bedrock decisions, S3 data reads, Lambda computations, DynamoDB stored runs | AT-12 |
| No confidential client data | Fictional forms only; no contact/account fields; redact prompts from broad logs | AT-10 |

## Fixed disclaimer

EN: “Simulation only. Fictional profiles. Not financial advice.” FR: “Simulation uniquement. Profils fictifs. Ceci n'est pas un conseil financier.” Display in the shell, print view and brief. Never allow model text or a feature flag to remove it.

## Evidence and wording

“No controversy found” is not a clean bill. Mateo's direct Energy exclusion is an editable assumption, not the brief's definition of ESG. The absence of verified evidence remains explicit. Listing-country and ETF theme labels cannot establish revenue exposure or financial impact. A measured price move after an event is not causal evidence. The auditor checks English and French instructions/guarantees and unsupported interpretations.

## Data history limits

Publication date is not reference date. Fixed-lag monthly macro is context with a limitation, never sufficient for historical proof. FRED revisions, Yahoo retrospective adjustments, the 2026-selected universe and model knowledge mean the Time Machine is an availability-constrained illustration, not a historical-vintage backtest. See [historical spec](../backend/aplomb/timemachine/SPEC.md).

## AWS and submission honesty

Capture real traces before shutdown; label screenshots with UTC timestamp, run ID, region, model ID and code revision. Store sanitized exports, not credentials or full private prompts. A JSON fixture or `/meta` flag cannot prove a cloud service executed. The technical document distinguishes verified services from planned/disabled services.
