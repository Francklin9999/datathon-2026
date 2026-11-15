# CONT — regional research (JP/KR financials, ownership, listed issue info)

## Status: PAUSED — deferred: requires login/key
By owner decision (2026-11-15), sources that need a login or API key are set aside for now. J-Quants and OpenDART both need keys, so no further regional features will be added. The code below is left in a consistent state. Re-checked after the pause: the module imports (`aplomb.research.regional`, `aplomb.api.app`), `ruff check` on regional.py passes, and `npx tsc --noEmit` passes (exit 0). Without `APLOMB_*_KEY` + `APLOMB_*_RIGHTS_CONFIRMED=true`, every kind returns `status: "unavailable"` and makes no provider call. The UI shows this as an `Unavailable` state. That fail-closed path is the only one reachable in the current deployment. Before resuming, review the live response shapes and plan rights against a licensed account.

## Added
- `GET /v1/intelligence/regional?kind=` now dispatches per region. JP: `prices`, `company`, `financials`, `ownership`. KR: `filings`, `financials`, `ownership`. `overview` is kept as a backwards-compatible alias (JP→prices, KR→filings). An unsupported kind for a region gives a `validation_error`.
- **J-Quants listed issue info** (`/v2/equities/master`, code + `date`=end): company name (JP/EN), 17/33-sector code+name, scale category, market segment code+name, margin flag, product category, `asOf`. The code must match exactly. An empty result returns `company: null`. Per the spec, that can mean the issue was not listed on that date. The provider does not give listing or delisting dates.
- **J-Quants financial summary** (`/v2/fins/summary`). Fixed the previous field `NxFNP`; the spec spells it `NxFNp`. The rows are flattened to period / account / section / value / unit / disclosure date+time (TDnet time, JST→UTC) / DocType. They cover results, non-consolidated results, actual and forecast annual dividends, the FY forecast and the next-FY forecast. Each forecast is linked to its own fiscal-year period. Values are exact decimal strings in yen (the spec says it applies no unit conversion). Ratio items (EqAR, ROE, payout) are left out on purpose, because their units are not asserted.
- **J-Quants EDINET large-volume holding reports** (`/v2/edinet/large-volume-shareholders`, JP ownership). JSON numbers are parsed as `Decimal` (`parse_float=Decimal`), never float. The provider's decimal ratios are converted exactly to percent. The ratio change in pp is computed by code from `TotalShsRatioLast`. Amendments (`DocTypeCode 360`, `ParDocId`) are flagged. The note about the 2026-05-01 rule change is included in the limitations. Row `url` is `null`: I did not verify an EDINET viewer URL pattern, so none is invented.
- **OpenDART full financial statements** (`fnlttSinglAcntAll`): adds `sj_nm`, `account_detail`, the cumulative `thstrm_add_amount`, prior `frmtrm_nm/amount`, `ord`, and `currency`. Receipt date is `null` with the label "date not in source". The response carries no receipt date, and none is derived from `rcept_no`.
- **OpenDART ownership** — `majorstock` (report_tp, repror, stkqy, stkqy_irds, stkrt, stkrt_irds, ctr_stkqy, ctr_stkrt, report_resn) and `elestock` (repror, isu_exctv_rgist_at, isu_exctv_ofcps, isu_main_shrholdr, sp_stock_lmp_cnt / _irds_cnt / _rate / _irds_rate). There is an exact 8-digit `corp_code` match per row. The date is `rcept_dt` only; both documented forms (YYYYMMDD / YYYY-MM-DD) are accepted. Rows are filtered to the requested range after retrieval. Blank or `-` amounts become `null`, never 0. A malformed amount also becomes `null` and its field name is listed in `limitations`.
- Shared behaviour is unchanged: key + rights gating, fail-closed `unavailable`, credential-free `sourceUrl`/`sourceUrls`, a rejected response if it echoes the key, session-hashed immutable captures (`kind` is part of the capture identity), and sanitized `provider_*` → 503 unavailable.
- UI `RegionalResearch.tsx` has:
  - a region-aware kind selector
  - a company `<dl>`
  - a financials table (period, account, section, value, unit, disclosed/receipt) and an ownership table (reporter/position, report type/reason/amendment, shares, change + pp, ratio %, receipt date + DART link)
  - source link(s), capture time, dataset version
  - an explicit partial/first-page label (or "no further pages reported")
  - `Unavailable` / `Empty` / `Loading` states and a sanitized error message
  - limitations in a `<details>`
  - exact-string thousands grouping (no float)

## Files changed
- `backend/aplomb/research/regional.py` (rewritten; owned)
- `web/src/features/markets/RegionalResearch.tsx` (rewritten; owned)
- Shared `backend/aplomb/api/app.py`: one-line change to the `kind` query pattern in `regional_research` (`^(overview|prices|company|filings|financials|ownership)$`).

## Env vars (unchanged)
`APLOMB_JQUANTS_KEY`, `APLOMB_JQUANTS_RIGHTS_CONFIRMED=true`, `APLOMB_OPENDART_KEY`, `APLOMB_OPENDART_RIGHTS_CONFIRMED=true`.

## Docs checked (2026-11-15, via web fetch summaries)
- jpx-jquants.com/en/spec/eq-master, /fin-summary, /edinet-large-volume-shareholders, /pagination, /spec (index)
- opendart guide DS003/2019020 (fnlttSinglAcntAll), DS004/2019021 (majorstock), DS004/2019022 (elestock)

These were read through a summarising fetch tool, not raw pages. The `rcept_dt` format differs between the two summaries; that is why both forms are accepted. The OpenDART majorstock page states no format for its amount fields, so parsing is lenient: unparseable values become null and are flagged.

## Not verified / limitations
- No live provider call was made (there is no licensed key). Real response shapes, plan entitlement (EDINET needs the Standard plan or higher) and coverage are unverified.
- Verification was limited to: module import, `ruff check` on regional.py (pass), and `npx tsc --noEmit` (pass). No tests were run or written. The existing `backend/tests/unit/test_regional_research.py` was not re-run. It uses the default kind, which still maps to the same prices/filings handlers.
- No browser/UI check.
- Pagination is not followed. `partial` is true when J-Quants returns `pagination_key` or DART `total_page > 1`. The majorstock/elestock/fnlttSinglAcntAll docs show no paging, so `partial: false` there.
- Generated contract/schema types for this response are still not added.

## Removed after completion (owner decision 2026-11-15)

JP `ownership` (J-Quants EDINET large-volume holding reports) was removed from backend dispatch, `KINDS`, and the UI selector because the endpoint requires a paid J-Quants Standard-or-higher plan. All of J-Quants and OpenDART are additionally deferred because they require a login/API key; the existing key-gated code remains and returns "unavailable" without keys.
