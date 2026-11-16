# CONT — dated relationship graph (GLEIF Level 2)

## Added
- `backend/aplomb/intelligence/gleif_relations.py` (new). GLEIF Level 2 reader for one exact LEI. It reads `/lei-records/{lei}`, `/{direct|ultimate}-parent-relationship`, `/{direct|ultimate}-parent-reporting-exception` (only called when no relationship record exists), `/{direct|ultimate}-child-relationships` (paged, 100 per page, 1–5 pages, with a truncation flag) and one batched `filter[lei]` lookup for related entity names (up to 200).
  - Every relationship row is checked against the LEI that was asked for. Rows with the wrong start/end node, the wrong type, an invalid LEI or a self-link are counted in `rejected_rows` and dropped. Name rows are accepted only for LEIs that were requested.
  - Each source state is reported separately: an HTTP 404 is `none_published`, which does not mean "no parent". A reporting exception is shown as "not reported: <reason>" with its own source hash.
  - Relationship period start/end come from `RELATIONSHIP_PERIOD`. Relationship status, corroboration level, registration status, accounting periods and the record's `validFrom` are kept as qualifiers.
  - Provenance: every response is SHA-256 hashed. Each record records the URL and hash of the page it came from. Availability is the capture time. The GLEIF golden-copy `publishDate` is kept as the documented publication time.
  - `capture_l2` stores each raw payload immutably in the session-owned partition `cache/GLEIF_L2#sha256(session)/CAPTURE#<sha>`, plus a same-day bundle (`BUNDLE#lei#pages#date`). A repeat request on the same day reuses the stored capture and is flagged `reused_capture`. `stored_payload` returns raw bytes only to the owning session and re-checks the hash. It also reads exact-pair captures from `ENTITY_PAIR#`.
  - `isin_candidates`: GLEIF `filter[isin]` LEIs, treated as candidates only.
- `backend/aplomb/intelligence/relationship_graph.py` (new). Node/Edge models and `RelationshipGraph`.
  - Evidence classes: direct, derived, model_inferred and unverified (the legacy `candidate` maps to unverified).
  - Each edge has `valid_from`/`valid_to` (`None` means not documented), `temporal` (interval or point_observation), `available_at`, a source (id, URL, sha256, licence, retrieved/published), qualifiers, and for derived edges a rule plus the input edge-id path.
  - Inputs: `add_relationship` (existing `entities.Relationship`, e.g. an exact ISIN→LEI pair), `add_gleif_l2` (ENTITY_PARENT_OF / ENTITY_ULTIMATE_PARENT_OF; exceptions become node annotations), `add_holdings` (`HoldingsSnapshot` → SECURITY_HELD_BY_PORTFOLIO as a point observation), `add_ledger` (LedgerView evidence → CLAIM_SUPPORTED_BY_SOURCE, which is direct only when the ledger quote check verified it and unverified otherwise; fact sources → FACT_SOURCED_FROM_DATASET).
  - `derive()`: security → issuer's ultimate parent, and portfolio → issuer via a held ISIN. The derived validity is the intersection of the input intervals. If the intervals do not overlap, no edge is derived and a `derivation_notes` entry explains why.
  - `view(root, as_of, depth, knowledge='as_of'|'latest', classes)`. It honours availability (in `as_of` mode) and validity, and returns hidden-edge counts by reason. (An earlier `neighbors` helper had no caller and was removed.)
  - `relationship_view(...)` is the orchestrator used by the route. It degrades gracefully: if the GLEIF candidate lookup, a pair check or Level 2 fails, that part is reported as unavailable and the other verified evidence is kept.
- `backend/aplomb/intelligence/entities.py` (additive only). Added RelationshipType values `ENTITY_ULTIMATE_PARENT_OF`, `SECURITY_ISSUER_ULTIMATE_PARENT`, `PORTFOLIO_HOLDS_ISSUER_SECURITY`, `FACT_SOURCED_FROM_DATASET`, and EvidenceClass `unverified`.
- `web/src/features/markets/IssuerEvidence.tsx` (rewritten; still mounted by MarketsPage).
  - Inputs: ISIN and/or LEI, as-of date, knowledge mode, subsidiary pages and an include-unverified toggle.
  - Shows issuer resolution (candidates and the exact-pair check status), then the corporate tree as a nested list (ultimate parent / direct parent / entity / direct and ultimate subsidiaries, with exception reasons).
  - Also shows an edge table (class, validity on the date, interval, availability, source link, sha256, licence), hidden counts, derivation notes and limitations. It is bilingual.
  - The previous pair-only check is covered: entering an ISIN and an LEI runs the same `capture_pair`.

## Shared-file edits
`backend/aplomb/api/app.py`: one anchored insertion after `/v1/intelligence/security-issuer`.
- `GET /v1/intelligence/relationships?lei=&isin=&as_of=&knowledge=as_of|latest&include_unverified=&max_pages=1..3`
- `GET /v1/intelligence/relationships/captures/{sha256}` (session-owned raw payload; 404 otherwise)

No edits to MarketsPage.tsx, client.ts or labels.ts. No environment variables.

## Limitations
- Only the GLEIF (Level 2 and exact ISIN/LEI) and holdings parts are wired to the route. Holdings use only the existing captured AAPU partial N-PORT transcript (loaded in `captured_holdings_snapshots`). `add_ledger` exists, but no route feeds a run ledger into the graph yet.
- No facility, revenue-geography or supply-chain edges are produced. The relation types exist, but no directly documented source is wired. Nothing is geo-inferred.
- For the AAPU holding, the derived "portfolio holds issuer" edge is expected not to form. The holding is dated 2026-01-31 and the exact-pair link is only documented from its capture date, so the code emits a derivation note instead of stretching the link back in time.
- GLEIF Level 2 describes accounting consolidation, not ownership percentage or control.
- A JSON-shape check against 2026-11-15 live GLEIF responses (Apple `HWUPKR0MPOU8FGXBT394` and one child, `2549008YU9EOMHFUA249`) guided the parser. Those exploratory responses were saved only in the session scratchpad, not in the repo.

## Verification
Done:
- Module imports for `relationship_graph`, `gleif_relations`, `entities` and `api.app`
- `ruff check` on the four Python files
- `npx tsc --noEmit -p .` in web/ (no errors)

Not done (per the user directive):
- The new functions have never been executed, not even once against the live API or the scratchpad payloads
- No route or HTTP call
- No UI render
- No new tests
