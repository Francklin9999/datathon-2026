# 08 — Submission and evidence plan

**Owner:** T16, with T02 for AWS proof and all owners for method validation. Language default: English (A-26). Actual names and submission destination must be confirmed by the team. Dates come from team logistics, not verified organizer files in this repository.

| Deliverable | Due EST | Content / completion condition |
|---|---|---|
| Code and repository | Sun Nov 15, 23:59 | Runnable implementation, pinned dependencies, setup/env/data/reproduction instructions, licenses and passing P0 report |
| Real AWS captures | Before Mon Nov 16, 13:59 | Actual cloud run, correlated service logs and screenshots before account shutdown |
| Video | Mon Nov 16, 14:00 | Approximately five minutes, complete decision journey and real AWS proof |
| Technical documentation | Mon Nov 16, 14:00 | Agents, governance, maths, sources, traced explanation, validation and limitations |
| One-pager | Mon Nov 16, 14:00 | Problem, user, product value, architecture, evidence and measured limits |

## Five-minute demo outline

| Time | Show | Evidence |
|---|---|---|
| 0:00–0:30 | Fictional Robert, plan assumptions and hypothetical TSLA request | Persona, holdings, disclaimer |
| 0:30–1:35 | Real run, conflict, failed rules and lower-size boundary | Live persisted tools, actual computed figures |
| 1:35–2:15 | Click a figure; move slider and compare Amira | Fact source/method, different outcomes at 10 points |
| 2:15–2:50 | Mateo/CNQ | Exclusion vs missing evidence; financial checks alone are insufficient |
| 2:50–3:30 | Sabotage if working, otherwise deeper genuine audit | Exact offending sentence and actual check result |
| 3:30–4:10 | Best working P1 flow, if integrated | Globe exposure or date gate; visible limitations |
| 4:10–5:00 | Genuine AWS service evidence and value | Bedrock call, S3, Lambda, DynamoDB; no invented proof |

Fit the story to working features. Cuts do not remove the core decision, citations, assumptions, or cloud proof. Do not spend video time describing unfinished screens.

## Technical-document outline

1. Use case, fictional personas and scope; how the owner decisions extend the SRS minimum.
2. Architecture diagram and justified service roles; six roles versus deterministic components.
3. Request-to-verdict sequence including revision, budgets and safe failure.
4. Methods: adjusted returns, FX, master calendar, constant weights, risk measures, thresholds and size grid.
5. One fully traced number from request to CSV rows to fact to signed sentence.
6. Research tiers, quote verification, ESG missingness and no causal impact claims.
7. Test report with measured performance and cloud evidence.
8. Limitations: snapshot vintages, macro revisions, model knowledge, no ETF rule look-through, assumed budgets and sample dependence.

## Capture manifest and release checklist

Store final artifacts under `docs/deliverables/` once produced. Include a manifest with file, description, UTC capture time, code revision, run ID/data version and whether genuine runtime evidence or illustrative material. Redact account identifiers as needed and remove secrets/session capabilities. Record the exact code revision in video notes.

Before shutdown: capture a decision from the deployed UI, model ID/usage, S3 data/version read, DynamoDB persisted result and CloudWatch correlation; download sanitized result/logs. Do not label these exports an offline application mode. D-38 explicitly rejects that mode. Confirm final artifact URLs and permissions manually before submitting.
