# CONT — timemachine stream (point-in-time SEC data)

> **Current status (wiring audit, 2026-11-15):** the SEC part described below has been removed. The owner removed every SEC source (`intelligence/capabilities.py` family `sec` is `removed`; SRC-034/035 are `removed: owner excluded SEC access-refused sources`), so the panels never rendered. `sec_pit.py`, `PointInTimePanel.tsx` and the three SEC routes (`/point-in-time/{cik}`, `/point-in-time/{cik}/published-later`, `/sec-ticker-candidates`) were deleted. Still present: `records.py` (tested on synthetic records), `alfred_access()` and `GET /v1/timemachine/vintages/status` in `pit_routes.py`, whose ALFRED status line is now shown by `web/src/features/timemachine/VintageStatus.tsx` in the Time Machine cutoff card. The rest of this report is the original change log.

## Added

- `backend/aplomb/timemachine/sec_pit.py` (new): SEC point-in-time reconstruction.
  - Fetches through the shared bounded `ResearchService`/`PublicHTTP` (read-only reuse of `research/company_detail.py`: `cik_id`, `CONCEPTS`, `FORMS`; that file is not edited).
  - Submissions: parses `filings.recent` columns including `acceptanceDateTime`, plus up to 3 older `filings.files` pages overlapping `[cutoff − 2y, today]`.
  - XBRL: `companyfacts` for the 7 existing us-gaap concepts (USD, CAD, USD/shares, CAD/shares). If companyfacts exceeds the 4 MB capture limit (`response_too_large`), falls back to one `companyconcept` document per concept.
  - Builds `records.py` `PointInTimeRecord`s: a fundamental record is one `(concept, unit, start, end)`, and each accession that reported it is one revision. Availability is the EDGAR acceptance time of that accession. If the accession is outside the fetched submission pages, availability is the filing date at 23:59:59.999Z, labelled `filing_date_end_of_day`. Availability is never later than the capture time. Conflicting values inside one filing, and different values with identical availability, are excluded with explicit reasons instead of being guessed.
  - `point_in_time(capture, cutoff)` returns figures available at the cutoff (latest 8 periods per concept, plus totals and counts by availability basis). It also returns the withheld set with reasons (`published_after_cutoff`, `revision_after_cutoff` with `value_at_cutoff`/`value_changed`, `unknown_availability`, `observation_after_cutoff`), the count superseded before the cutoff, and the filings timeline: accepted ≤ cutoff vs withheld after, by reason and by form, plus lists of the listed forms.
  - `published_later(capture, cutoff, until)` is reveal-only: new figures, figures whose value was revised, and filings in `(cutoff, until]`. It is flagged `separate_from_run: true`.
  - Per-session, per-day LRU cache of parsed captures (32 entries; raw documents are not retained).
- `backend/aplomb/timemachine/pit_routes.py` (new): all routes require the session and `feature("time_machine")`.
  - `GET /v1/timemachine/point-in-time/{cik}?cutoff=`
  - `GET /v1/timemachine/point-in-time/{cik}/published-later?cutoff=&until=`
  - `GET /v1/timemachine/sec-ticker-candidates?ticker=`: exact current SEC ticker matches, shown as candidates only. The user picks the CIK; a ticker never selects identity.
  - `GET /v1/timemachine/vintages/status`
  - Dates must fall between 1994-01-01 and yesterday (UTC), and `until` must be after `cutoff`. Session rate limit is 6 per 60 s. Without a valid `APLOMB_SEC_CONTACT` the routes return `{"status":"unavailable","reason":"sec_contact_unconfigured"}` and fetch nothing. A record-validation failure returns `unavailable`, not a partial guess.
- `backend/aplomb/timemachine/vintages.py`: added `alfred_access()`, a rights gate that reports status only. It is `unavailable` unless both `APLOMB_ALFRED_RIGHTS_CONFIRMED=true` and `APLOMB_FRED_KEY` are set. Even then the status is `rights_confirmed_ingestion_not_wired`. Nothing is fetched or ingested from FRED/ALFRED, and the key is never echoed.
- `web/src/features/timemachine/PointInTimePanel.tsx` (new):
  - `PointInTimePanel`: a card on the Time Machine page that uses the chosen cutoff. It has a CIK field and an optional exact-ticker candidate lookup. It shows tables of available and withheld figures with UTC availability timestamps and basis, a withheld-reason breakdown, the filings timeline with counts, sources with SHA-256 hashes and limitations, and the ALFRED status line.
  - `PublishedLaterPanel`: rendered inside `RevealView` after the signed-ledger block, as a separate request.
  - Both show the fixed caveat that restricting tools does not erase an LLM's pretrained knowledge, and that deterministic calibration is not a model predicting history.
- `web/src/features/timemachine/TimeMachinePage.tsx`: import plus two insertions: `<PointInTimePanel>` before the run card, and `<PublishedLaterPanel>` at the end of `RevealView`.

## Shared-file edits

- `backend/aplomb/api/app.py`: 2 lines after the wikidata router include (`point_in_time_router(store, session, feature)`).
- `web/src/api/client.ts` and `labels.ts` were not touched. The panel uses a direct `fetch(API_BASE…)` like `CompanyResearch.tsx` does.

## Env vars

- `APLOMB_SEC_CONTACT` ("Name email", same format check as `intelligence/sec_structured.py`). Required for any SEC call.
- `APLOMB_ALFRED_RIGHTS_CONFIRMED`, `APLOMB_FRED_KEY`. These only change the reported status; nothing is ingested.

## Isolation

The endpoints never read, write or feed a replay run. Captures retrieved now are never injected into historical runs (the replay path still blocks research via `ResearchContext.allow()` in `mode="replay"`; these routes use their own `mode="point_in_time"` context). The reveal comparison is fetched separately and does not touch the signed run or the reveal record.

## Limitations / not verified

- Verification run: module imports (`aplomb.api.app`, `pit_routes`, `sec_pit`, `vintages`), `ruff check` on the time-machine files and `app.py` (pass), and `npx tsc --noEmit -p .` in `web/` (pass).
- Not run: no live SEC call (no `APLOMB_SEC_CONTACT` in this environment), no HTTP request against the routes, no unit tests (none written, per directive), no browser check.
- These SEC formats are assumed, not observed in this session:
  - `acceptanceDateTime` format and its UTC labelling. It is used exactly as stated, and an unparseable value falls back to filing date.
  - Shape of older submission pages: top-level columns are accepted, and so is `filings.recent`.
  - `companyconcept` field names (`taxonomy`, `tag`, `units`).
- companyfacts reflects SEC's current XBRL processing; it may not hold every superseded presentation. Filing counts cover only the fetched submission pages (`filings_cover_from` is shown).
