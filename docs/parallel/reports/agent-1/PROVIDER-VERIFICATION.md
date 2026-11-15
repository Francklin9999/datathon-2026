# Anonymous provider connector verification

All new tests below use **synthetic source-format bytes**, a local in-memory store and a mocked transport. They do not establish permission to use, redistribute, or query a live financial data provider. No real source permission flag was changed and no credentials were used.

`UV_CACHE_DIR=/tmp/aplomb-agent-1-uv-cache uv run pytest backend/tests/unit/datastore/test_financial_providers.py -q` — **13 passed**. Focused Ruff passes on the affected connector, API router and test module.

The synthetic cases cover French daily ZIP percentage conversion; AQR workbook/sheet selection and current-capture-only date guard with source units left uninterpreted; Cboe OHLC, invalid ranges and duplicate dates; OCC source-row retention; FINRA short volume with exempt quantities and volume/interest distinction; and rejection of the login-required FINRA short-interest acquisition route. A separate synthetic position-parsing case passed before that route was set aside. They also cover permission denial before any request, deferred paid/login providers, session-isolated capture and inspection, one-hour cache reuse, historical capture cutoff, permission revocation, corrupted raw and normalized response data, and graceful malformed-source failure.

## Repairs identified

- Provider capture cache records have `sessionId` at the top level. The shared `Store.get_owned` method is specific to run records and checks `run.sessionId`. The prior call therefore prevented cache hits and capture inspection. Reads now check the actual cache record owner explicitly.
- Cached and direct inspections now re-check the rights gate, raw content SHA-256 and a normalized-response checksum. Permission revocation or data corruption returns an unavailable error rather than exposing stale or silently altered data.
- FINRA short-interest request operators now use the documented `EQUAL` and `LTE`, rather than the unsupported `lesserOrEqual`. Ingestion failures map to a clear unavailable response. Cboe duplicate dates and malformed ranges are rejected; provider-reported days-to-cover is finite/nonnegative or unknown. Spreadsheet inline strings and malformed CSV fail cleanly.
- These checks prove code behavior for supplied synthetic inputs only. They do not prove live source formats, live access, full issuer coverage, or deployment readiness. The Cboe, OCC and AQR source-use permissions still require explicit review, and the French download host previously reset connections.

## FINRA endpoint/access clarification

[FINRA's documentation](https://developer.finra.org/docs) identifies group `otcMarket` and production dataset `consolidatedShortInterest`; the documented metadata quicklink points to the [synthetic mock dataset metadata](https://api.finra.org/metadata/group/otcmarket/name/consolidatedShortInterestMock). A HEAD request returns 404 even for this documented metadata URL while the documented GET returns JSON; therefore HEAD 404 is not proof the production dataset does not exist. HEAD against the data endpoint returns 405, consistent with a method restriction. No production FINRA market-data response was retrieved.

The same official documentation states that **an API credential is required for FINRA API-platform requests** and that credentials are provisioned through a FINRA Gateway login. The production `consolidatedShortInterest` API is set aside under the user's no-login instruction, and acquisition requests are rejected before network access. The separately hosted public daily short-volume file is a different source and must not be described as a short-interest position.
