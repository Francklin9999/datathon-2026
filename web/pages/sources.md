# Sources — dataset passports and limitations

**Owner:** T13; data supplied by T04/T09/T11. **Tier:** P0. Route `/sources/?datasetId=...`.

## Information architecture

Use `/datasets` for list/traps and `/datasets/{id}` for detail. Cards/table show name, role, in_use/planned/rejected, provider, retrieval date, coverage, frequency, row count and version. Planned sources have no fabricated retrieval dates, checks or data. Rejected sources explain reason. Source terms link to actual provider terms, with unknown licence clearly stated.

Detail shows schema, processing transformations, availability rule, actual quality-check timestamps/results and limitations. Trap panel explicitly maps calendar alignment, FX holiday fill, adjusted prices/actions, CNQ factor, crypto dates, monthly publication/revisions, survivor bias and missing ESG to handled/disclosed/open state. “Handled” requires an implemented tested treatment, not merely a spec paragraph.

Source URLs open externally; preserve publisher/date and protect against markup injection. Dataset drilldown from a FactDrawer retains run/data version; warn if currently displayed passport differs from signed fact's snapshot and retrieve pinned passport if supported. Display stale cache with original retrieval timestamp.

## Verification

SRC-01 every used dataset has a passport and provenance. SRC-02 planned vs in_use status truthful. SRC-03 missing licence remains unknown. SRC-04 data-version drift visible. SRC-05 source traps/limitations readable by keyboard/mobile. SRC-06 network/empty states and no computed source-health claims from HTTP 200 alone. Source page remains reachable from all P0 evidence flows.
