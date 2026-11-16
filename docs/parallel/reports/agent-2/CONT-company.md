# CONT — company stream (SEC company detail + disclosures)

> **Current status (wiring audit, 2026-11-15):** the owner removed every SEC source (`intelligence/capabilities.py` family `sec` is `removed`), so `CompanyResearch.tsx` and `SecExplorer.tsx` never rendered. Both components, `research/company_routes.py`, `research/sec_extra.py`, `GET /v1/research/company/{cik}`, the four `GET /v1/research/sec/*` routes, their `contracts/api.md` rows and the HTTP test were deleted. `research/company_detail.py` (its `cik_id` is imported by `research/disclosures.py`) and its unit tests remain. The rest of this report is the original change log.

## Bug fixed
`CompanyResearch.detail` was not idempotent. The only difference between two identical calls was the ledger fact `createdAt`, which came from the wall clock. The detail ledger now uses a fixed clock equal to the capture instant, so identical captures register identical facts (F-001…) with identical timestamps. The existing file `backend/tests/research/test_company_detail.py` passes: 8 tests, including `test_session_owned_idempotent_capture_and_graceful_partial_failure`. No new tests were written.

## Added
- `research/company_detail.py`
  - Submissions now include `acceptanceDateTime` as `accepted_at` (EDGAR acceptance/publication time; never guessed if missing or unparseable), `primaryDocDescription`, items, the primary document link, the raw document link and the filing index link.
  - The overview adds the fiscal year end, filer category, SEC-reported tickers/exchanges (labelled as labels, not identity) and a 13F-filer flag.
  - Form 3/4/5 XSL primary paths (`xslF345X05/x.xml`) are accepted, and the raw XML URL drops the XSL directory. Before, a slash in a primary document name raised `unsafe_filing_identifier` and failed the whole submissions section. Other unrecognized document names are now skipped and counted (`skipped_unrecognized_documents`).
  - Financials cover 14 us-gaap lines plus `dei:EntityCommonStockSharesOutstanding`, at 6 most recent rows per concept/unit. Each row carries the fiscal year/period, period, form, filed date, accession/filing link, `data_class: official_reported` and `estimate: false`. Only us-gaap USD/CAD rows are ledger-registered, because that is all the ledger re-verifies.
  - New insider section: up to the 5 most recent Form 4/4A filings for the CIK, parsed from the official XML and bound to the issuer CIK.
  - New holdings section: the most recent 13F-HR. Its `index.json` is fetched, and up to 2 candidate XML documents are tried until one parses as an `informationTable`.
  - Each section is captured independently with a per-section status: `available`, `partial`, `unavailable` or `not_applicable`. Each has its own source records (URL, sha256, capture time, acceptance time) and session-owned immutable store captures.
  - Error codes come from a closed list (`SAFE_CODES`), so provider messages never reach the client.
- `research/disclosures.py`
  - Form 4 additions: transaction code meanings, footnote ids and footnote text (shown as data), underlying security, trading symbol (reported label), and `data_class`. A quantity reported only in a footnote is now `null` and never 0; before, its absence failed the whole filing.
  - 13F additions: `cusip_as_reported`. The identity-join `cusip` stays `null` unless `cusip_rights` is set. Also adds voting authority and an explicit value-unit rule (before 2023-01-03 values are in thousands ×1000; from that date on they are in dollars).
  - New `summarize_holdings` computes in code the Decimal total of the reported values, the top 25 rows by value, and each row's % of the reported total.
  - DTD/ENTITY rejection is kept, as in `sec_structured.py`.
- `research/company_routes.py`
  - `StatusRecordingTransport` records the upstream HTTP status per URL. A 403 becomes the `sec_access_denied` code for that section only, and is not retried or bypassed.
  - The contact is read from `APLOMB_SEC_CONTACT`, falling back to `APLOMB_SOURCE_USER_AGENT`. If neither is set the route returns 503 "SEC source contact configuration". An invalid contact now also gives 503; before, it was wrongly reported as an invalid CIK. The CIK is validated before the rate limiter.
- `web/src/features/markets/CompanyResearch.tsx` has been rewritten.
  - Tabs (SegmentedControl): Overview, Financials, Filings, Insider transactions, Institutional holdings.
  - Each tab has its own unavailable or partial state with a readable reason (403, rate limit, too large, issuer mismatch, no information table).
  - Each tab shows source links, filing date, EDGAR acceptance time, capture time and SHA-256.
  - Financials are labelled "official reported, not estimates" and show the ledger verification status per fact.
  - When no contact is configured, all five sections render as explicitly unavailable.

## Shared-file edits
None. `app.py` already included `company_router`, and the routes live in `company_routes.py`.

## Env vars
- `APLOMB_SEC_CONTACT`: descriptive "Organization email" User-Agent. It is preferred over `APLOMB_SOURCE_USER_AGENT`.
- No contact is invented. `.env.example` was not edited because it is not owned by this stream.

## Limitations / not verified
- There was no live SEC call. The real SEC document shapes are taken from the code's assumptions and are unverified against live responses:
  - the `xslF345X..` prefix on Form 4 `primaryDocument`;
  - the 13F `index.json` `directory.item[].name` layout;
  - SEC content types for `.xml`.
- The new insider and holdings code paths were checked only by import, ruff and `tsc --noEmit`. No test or run exercised them.
- Large 13F information tables (more than 4 MB, e.g. very large managers) end as `response_too_large`, and the section shows unavailable.
- Raw captures of several MB are stored per section, which is the existing pattern. A DynamoDB item limit of 400 KB would reject large captures in AWS; this was not addressed.
- One detail request makes about 2 to 10 SEC requests, run serially with a 12 s timeout each. The route limit is 4 per minute per session.
- If the CIK is a reporting person rather than an issuer, its Form 4s fail with `disclosure_issuer_cik_mismatch` and are not attributed.
