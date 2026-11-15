# Policy/public source batch — 2026-11-15

## SRC-127 Wikipedia Recent Changes

Implemented `backend/aplomb/world/providers/recent_changes_extra.py` and captured one anonymous API page: ten newest main-namespace English Wikipedia edits/new pages. The request selects article titles, timestamps, page/revision/change identifiers and byte sizes. It excludes article text, editor identities, IP addresses and edit comments. Wikimedia Terms of Use §7 explicitly says contributed facts may be reused freely without attribution; the terms page is retained as immutable rights evidence. Attribution is nevertheless displayed.

Runtime dataset: `world_wikipedia_recent_changes`. Immutable version: `world_wikipedia_recent_changes-2026-11-15-1fe961c5e3f741b0`. The existing snapshot publisher records SHA-256 for normalized rows and both raw API/terms captures. One page is deliberately bounded to ten records; continuation availability is reported and pagination is not followed. Fetching uses a fixed URL allowlist, rejects redirects, caps each response at 500 kB, limits reads to 20 seconds and retries at most once.

The existing World Explorer observations endpoint consumes the saved capture in news mode. Descriptions explicitly label article edit activity and its limits. Article titles establish neither event geography nor issuer relationships; no map marker or country is invented. The edit timestamp is source observation time, not publication time of a real-world event. Saved rows are gated at retrieval and excluded from earlier replay.

Shared additive changes: `providers/ingest.py` imports the provider, adds the `wikipedia_recent_changes` CLI choice and routes it; `world/service.py` adds the news mode mapping and factual summary; `world/passports.py` registers the dataset ID. Existing World Explorer news lists consume this through the shared observations route without a separate frontend adapter.

Capture command: `.venv/bin/python -m aplomb.world.providers.ingest --source wikipedia_recent_changes`.

Verification evidence: `docs/evidence/parallel/agent-3/wikipedia-recent-changes-http-smoke.json`, generated using the real ASGI `/v1/world/observations` route with the saved production capture. It verifies ten current rows, absent geography, earlier as-of exclusion, viewport exclusion of unlocated rows, an `in_use` passport and raw/normalized integrity. No new tests were added.

## Exact blockers for remaining assigned candidates

| Source | Access/rights evidence | Blocker |
|---|---|---|
| SRC-143 / MASTER-048 Canada Gazette RSS | Official discovery page `https://gazette.gc.ca/rss/sc-rb-eng.html` advertises `https://gazette.gc.ca/rss/p1-eng.xml` and `https://gazette.gc.ca/rss/p2-eng.xml`; both return valid RSS. Its footer links `https://www.canada.ca/en/transparency/terms.html`. | Canada.ca terms under “Commercial reproduction” prohibit commercial redistribution without prior written permission unless otherwise specified. No broader Gazette RSS reuse permission was identified. Issue/index metadata was probed but not published or marked integrated. |
| SRC-144 EUR-Lex API | `https://eur-lex.europa.eu/content/help/data-reuse/reuse-contents-eurlex-details.html` states that webservices are for registered users, and data dumps need an EU login account. | Registered API access is required. Login/key setup is set aside under the user's instruction. The help page alone is not an integration. |
| SRC-137 / MASTER-054 UN Sanctions | Assigned consolidated-list page returns HTTP 202 with zero bytes here; official `https://scsanctions.un.org/resources/xml/en/consolidated.xml` returns XML (2,177,747 bytes). `https://www.un.org/en/about-us/terms-of-use` §(a) permits personal noncommercial copying only, “without any right to resell or redistribute them or to compile or create derivative works.” | A suitable redistribution/derivative permission has not been established. The accessible XML was not published or consumed by runtime. |

No paid provider, keys, login setup, deployment, commit or push was performed. Root owns the source/requirement/status ledgers.
