# CONT-holdings — SEC N-PORT fund holdings pipeline

## Added
- `backend/aplomb/intelligence/fund_pipeline.py` (new)
  - SEC access goes through `fetch`, with HTTPS restricted to `www.sec.gov` and `data.sec.gov`. Redirects are not followed, size is capped (filing documents 15 MB, indexes 12 MB) and requests are spaced 0.15 s apart. It needs `APLOMB_SEC_CONTACT` (`Organization email`). Failures come back as stable codes: `operator_contact_unconfigured`, `source_forbidden` (403, not retried in any form), `source_not_found`, `source_rate_limited`, `source_unavailable`, `source_too_large`.
  - Discovery has three routes:
    - (a) Series ID only: EDGAR company-browse Atom (`browse-edgar?action=getcompany&CIK=S…&type=NPORT-P&output=atom`).
    - (b) With a registrant CIK: `data.sec.gov/submissions/CIK##########.json`, keeping NPORT-P and NPORT-P/A filings.
    - (c) With CIK plus an exact accession.
    Discovery results are not used to establish identity. The primary document's own `genInfo/seriesId` has to equal the requested series. At most 8 newest filings are scanned.
  - Availability:
    - When the submissions record lists the accession, availability is the EDGAR `acceptanceDateTime` wall clock + 5 h. That is the latest UTC instant consistent with reading the timestamp as either UTC or US Eastern, so it is a conservative upper bound. It is capped at retrieval time.
    - Otherwise availability is the retrieval time, and `availability_basis` says which basis was used.
    - The report date is never used as availability. A report date later than availability is rejected.
  - Persistence:
    - Captures are immutable and session-owned in table `cache`. Each capture has 3 items: raw XML (`FUND_NPORT_RAW#owner / RAW#sha`), the normalized record (`FUND_NPORT#owner / CAPTURE#id`) and a small index row (`FUND_NPORT_INDEX#owner`).
    - `capture_id` is the hash of {series, accession, source sha256, mapping id}. `dataset_version` is `sec-nport-<sha[:16]>`.
    - Re-ingesting identical content returns the original capture and its first retrieval time.
  - `compute_lookthrough(positions)` reports:
    - Exact-ISIN constituent weights: non-derivative long positions only, aggregated per ISIN, flagged `direct_equity` when the asset category is EC.
    - `covered_pct`, `direct_equity_pct`, and an explicit `unknown_remainder_pct` broken down into unidentified longs, derivatives at fair value, shorts and unexplained (cash and other assets/liabilities).
    - A derivatives/swaps warning stating that pctVal is fair value, not notional, and that direct holdings are not economic exposure. A warning when coverage exceeds 100%.
  - Functions for the portfolio side:
    - `look_through(store, session_id, fund_id, as_of, historical=False)` takes a series ID or a documented fund ISIN. A capture is visible when report date ≤ as_of and availability ≤ end of as_of (UTC). With `historical`, the retrieval time must also be ≤ as_of. A fund ISIN is visible only once its mapping's `available_at` is ≤ the cutoff.
    - `holdings_snapshot(...)` returns an `overlap.HoldingsSnapshot` keyed by ISIN, or a reason (unmapped / unrepresentable), and can be fed straight into `portfolio_lookthrough`. Its Evidence availability is the later of the filing and the mapping.
- `backend/aplomb/intelligence/holdings_ingest.py`: new `nport_positions(raw)` parser. It returns the header (series ID/name/LEI, registrant, report date, period end, net/total assets) and every `invstOrSec` with: name, title, LEI (checksum-validated), ISIN (checksum-validated; invalid ones flagged), CUSIP/ticker kept for display only, balance, units, currency, valUSD, pctVal, payoff, assetCat (including `assetConditional`), issuer category, country, derivative flag and kind. It rejects DTDs and entities and checks the namespace. The existing `nport_holdings_xml` and CSV parser are unchanged.
- `backend/aplomb/intelligence/data/fund-isin-mappings.json` (new) holds one documented mapping: S000076233 / C000235743 ↔ US25461A8743. It was copied from the fields and sources already in `sec-nport-aapu-indexed-excerpt.json`; no new mapping was invented.
- `web/src/features/markets/FundHoldings.tsx` (new) is a bilingual card. Inputs: series ID, optional CIK, optional accession (needs the CIK) and a cutoff date. It has two actions: fetch the latest filing, or view the stored capture. It shows:
  - the session's fund list
  - status and reason-code messages, including the contact-missing and 403 states
  - report date, availability and its basis
  - a top-50 constituents table
  - coverage, the unknown remainder and its breakdown
  - the derivative warning
  - links to the primary document, filing index and ISIN mapping sources
  - SHA-256, dataset version and capture time
  
  `DisclosureExample` is untouched.

## Shared-file edits (additive)
- `backend/aplomb/api/app.py` adds the following, inserted after `/v1/intelligence/disclosures/aapu`:
  - a helper `fund_pipeline_error`
  - `GET /v1/intelligence/funds`: the session's captures plus the documented ISIN mappings
  - `POST /v1/intelligence/funds/{series_id}?cik=&accession=`: ingest, returns 201; per-session limit of 6 per minute
  - `GET /v1/intelligence/funds/{fund_id}?as_of=&historical=&limit=`: look-through by series ID or documented ISIN
  
  Errors use the standard envelope with `details.reason`. Wire format is snake_case, like the other branch-local intelligence routes; it still needs reconciling with the contract and client.
- `web/src/features/markets/MarketsPage.tsx`: one import line plus `<FundHoldings />` after `<DisclosureExample />`.

## Env vars
- `APLOMB_SEC_CONTACT` is required, in descriptive `Organization email` form. Without it, every ingest returns `upstream_unavailable` with reason `operator_contact_unconfigured`.

## Verification actually performed
- Both modules import, and `aplomb.api.app` imports.
- `ruff check` passes on fund_pipeline.py, holdings_ingest.py and app.py. Ruff reports pre-existing I001 issues in other workers' master*.py files, which I did not touch.
- `npx tsc --noEmit -p .` in `web/` exits with status 0.

## Not verified / limitations
- No live SEC request was made. `APLOMB_SEC_CONTACT` is not set in this environment, and an earlier SEC access attempt returned 403. Nothing below has been checked against real responses:
  - that EDGAR browse-edgar accepts a series ID in `CIK` and returns entries for it, and its exact Atom field names (the parser accepts `accession-number` and `accession-nunber`, and takes the form from `filing-type` or the category term)
  - the submissions JSON shape and the N-PORT element paths. These follow the published formats as I understand them, but no real document was parsed in this session.
- No tests were written or run, as directed. The parser, look-through arithmetic, persistence conflicts and visibility gating have not been executed end to end.
- Registrant-CIK discovery only scans the 8 newest N-PORT filings. For large trusts filing many series, the series may not be found, so use the exact accession.
- Only one documented fund ISIN mapping exists. Every other fund is series-ID only and cannot enter `portfolio_lookthrough`, which needs an ISIN or listing ID.
- If the submissions index is unavailable, availability falls back to retrieval time. Filing date alone is not used for availability.
- Large funds can produce multi-MB normalized records. DynamoStore spills these to blob storage; this was not exercised.
