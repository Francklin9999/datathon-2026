# Official anonymous macro captures

Implemented 2026-11-15 within the free anonymous source scope. No new tests, credentials, paid plans, commits, pushes or cloud changes. The existing observation runtime automatically discovers these immutable provider manifests. Catalogue/passport registration is a shared additive integration task communicated to the integrator.

| Directory IDs | Exact captured series | Runtime dataset | Actual records |
| --- | --- | --- | --- |
| SRC-093, MASTER-035 | ECB ILM.W.U2.C.T000000.Z5.Z01: Eurosystem total assets/liabilities, weekly 2024, EUR millions | `world_ecb_eurosystem_assets_2024` | 52 |
| SRC-094, MASTER-036 | BIS WS_DSR Q.US.P: United States private nonfinancial sector debt service, quarterly 2024, percent of income | `world_bis_us_debt_service_2024` | 4 |
| SRC-103 | Federal Reserve charge-off release, All Banks SA, TOTAL loans and leases cells, quarterly 2024, annualized percent of average loans net of recoveries | `world_fed_chargeoffs_2024` | 4 |

SRC-103 uses the anonymous official tabular release associated with the Data Download Program. The interactive DDP UI and all other Fed series remain unimplemented. The parser identifies the source's `TOTAL` cell headers rather than assuming column positions. This is an aggregate of insured U.S.-chartered commercial banks, with seasonal adjustment disclosed.

## Access and rights

All three fixed data URLs returned HTTP 200 anonymously. Full official ECB, BIS and Federal Reserve reuse terms also returned HTTP 200. Exact URLs, response hashes and relevant excerpts are in `docs/evidence/parallel/agent-3/official-macro/terms-evidence.json`.

ECB permits accurate reuse with attribution and disclosure of changes. Sold documents must disclose that the information can be obtained free from the ECB before payment and whenever the information is accessed. The normalized rows and runtime limitations include ECB attribution, selection disclosure and the free-source notice. A future sales/subscription flow must also meet the prepayment requirement.

BIS permits source-attributed reuse without misleading endorsement; translations must be marked unofficial, and inclusion in a commercial product must cause no additional charge to users. The current captures are part of this free datathon product. Runtime limitations preserve the no-additional-charge and unofficial-translation conditions. Changing the product's charging model requires review against these terms.

Board-produced Federal Reserve information is public domain unless marked otherwise. Only Board statistical table values are normalized; no external images or third-party articles are included. The raw capture is the official HTML response, with the statistical source and interpretation retained. No government endorsement is implied.

## Capture, normalization and runtime

`backend/aplomb/world/providers/official_macro.py` provides strict fixed endpoints, a 500,000-byte cap, 20-second connection/read limits, rejection of redirects, up to two bounded retries, series/dimension/unit checks, finite numeric validation, reference-period validation and duplicate rejection. ECB weekly ISO periods map to Monday; quarterly periods map to quarter start. These dates are display anchors rather than measurement instants.

Provider publication uses the existing immutable SHA-256 protocol, stores raw responses plus normalized rows, and gates availability at retrieval. The three version directories are:

- `world_ecb_eurosystem_assets_2024-2026-11-15-816cfa0805b73d25`
- `world_bis_us_debt_service_2024-2026-11-15-e2a4d21e8be9ffd2`
- `world_fed_chargeoffs_2024-2026-11-15-c7ebfd5663589807`

All are beneath `backend/aplomb/world/bundle/providers/`. `captures.json` in the evidence directory contains the complete manifests and raw/normalized checksums. The capture run reused the exact anonymous responses acquired earlier in this task; capture timestamps conservatively mark later normalization/publication time as first proven availability.

Existing `/v1/world/observations?mode=macro&q=...` and the World Explorer source-observation panel consume the records. Titles expose the selected period, numeric value and unit. ECB has a supranational geographic role with no invented country; BIS and Fed have `countryIso3=USA`. All have no point coordinates, and viewport-only searches therefore exclude them. No globe marker, issuer relationship, exposure or financial effect is inferred.

Reconstruction:

```sh
PYTHONPATH=backend .venv/bin/python -m aplomb.world.providers.official_macro --source ecb --source bis --source fed
```

This explicitly refreshes the three sources and creates new immutable captures; runtime viewing never makes provider requests.

## Verification and boundaries

Manual verification used the existing configured FastAPI app through `TestClient`, with real default services and loaded captures. Each source returned HTTP 200, with counts of 52/4/4, `timeBasis=reference_period`, and null point locations. All three historical queries at `asOf=2024-12-31` returned zero rows. Evidence: `docs/evidence/parallel/agent-3/official-macro/runtime.json`. Existing snapshot loading verified every raw and normalized hash and all row counts. No test files were added or changed.

Coverage is intentionally limited to the three selected 2024 series. The capture does not establish current-quarter coverage, a comprehensive provider integration, original publication vintages, a historical replay archive or a modeled financial input. No pre-existing raw capture or active manifest was edited.
