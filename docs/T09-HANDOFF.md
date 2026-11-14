# T09 Research handoff

Implemented `aplomb.research` without a new dependency. `research_tool_handlers(service, gdelt=..., attention=..., etf=...)` returns the schema/callable pairs accepted by T08 `ToolRegistry.register`. Each callable accepts `ctx, **args` and returns its `ToolResult`. Inject `ResearchService(transport, clock, cache, documents)`; production transport is `PublicHTTP(descriptive_contact_user_agent)`. No import or default constructor makes a network call.

The T08 context may carry `ResearchContext(run_id, as_of, mode, data_version)` in `research_context`; identity/cutoff must match. `ctx.historical` and mode `replay` deny access before cache/DNS/HTTP. The fallback research data version identifies this implementation snapshot; production composition should supply its pinned data version explicitly.

## Evidence and network boundary

HTTPS only, exact reviewed domain registry (no substring/subdomain trust), public DNS only, numeric-IP pinned connection with original TLS SNI/certificate verification, revalidation on every redirect, at most four request attempts, bounded DNS, overall fetch deadline, content bytes/types and identity encoding. Header/body reads enforce the absolute socket deadline, including slow drip headers. No proxy, cookie, authentication or browser session is used. One bounded Retry-After retry supports numeric seconds up to two; longer delays and date-form Retry-After fail closed as rate limited. SEC requests are sequential, cached, and far below the documented maximum in the executed smoke; deployment must share a source budget across workers.

Every immutable capture retains original-byte SHA256 (`content_hash`), extracted-text SHA256 (`text_hash`), canonical URL, redirect chain, status/type, timestamp and original text. Quote offsets refer explicitly to whitespace-normalized extracted text; original text/hash are retained. Quotes must be nonempty, at most 400 characters and match normalized text. Save requires a same-run fetched document; supplied URL, publisher, publication date and tier cannot establish provenance. Publisher/tier come from the exact-domain registry; publication is conservatively null unless captured source metadata is implemented. T10 `DocumentRef` retains same-run text for A08. Evidence cannot prove absence of controversy; all index searches retain that limitation.

Cache keys contain adapter version, URL/args, retrieval day, asOf, mode and data version. Hits retain original retrieval time, relabel run-local document context and mark `from_cache`; no stale cross-day hit is silently reused. Redirect aliases are reattached on hits.

`ResearchService.save_figure` is a code-facing path through T10 `add_quote_figure`: exact source literal and explicit compatible unit must occur in a verified quote. It creates `quote.figure` with source URL and unknown availability date; it does not infer publication timing or arithmetic. Raw source prose remains untrusted data and has no registration/profile authority.

## Supported catalog behavior and precise limitations

| Tool | Implemented behavior | Live readiness / limitations |
|---|---|---|
| edgar.find_company | Exact ticker/name from official ticker JSON | Runtime SEC 403; source_unavailable, not invented results |
| edgar.list_filings | Official submissions recent arrays, form/date filtering, validated archive URL | Recent batch only; no older submissions expansion; runtime 403 |
| edgar.filing_text | Fetch accession URL established by same-run list_filings, normalized passages | Unknown accession rejected; runtime SEC unavailable |
| edgar.company_facts | Official us-gaap concept capture and available units | Figures withheld pending explicit quoted unit registration; no inferred XBRL semantics |
| gdelt.search | Injected cached query/date/country batch; no full-article verification | Empty cache -> cached_index_unavailable; live API smoke timed out; quota/terms for live loading unverified |
| web.fetch | Allowlisted public text/HTML/JSON/CSV capture and bounded passages | Registry currently SEC, Wikimedia analytics, issuer, GDELT domains; no general news publisher list |
| web.browse | Explicit browser_disabled | T02 start/stop alone is not navigation/evidence capture verification |
| attention.pageviews | Configured reviewed entity/article mapping; daily en.wikipedia.org/all-access/user; exact 395-day coverage, positive 365-day baseline, following 30-day mean | No default reviewed ticker mapping; unknown. Internal parser computes ratio and threshold >=2. Tool suppresses unregistered ratio and returns unknown/fact_registration_required because T10 has no verified daily-series derivation registration path. No verdict effect |
| etf.holdings | Injected dated issuer CSV configuration, exact identifier column, validated weights, partial top subset | No default issuer configuration. Attempted IVV CSV URL returned HTML despite text/csv; rejected. Tool returns identities only and weight_fact_registration_required; no holdings/profile writes |
| research.save_evidence | Same-run document capture -> T10 evidence with code-assigned publisher/tier, normalized quote verification | Only verified quotes enter saved evidence through this service |

## Checked official references and live proof

Official references browsed on **2026-11-14**: [SEC API definitions](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [SEC developer/fair-access policy](https://www.sec.gov/about/developer-resources), [Wikimedia API reference](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html), [Wikimedia access/licence/user-agent policy](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/access-policy.html), [GDELT official DOC API documentation](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/), and [iShares issuer page](https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf). SEC public JSON needs no keys and fair-access maximum is 10 requests/second across machines. Wikimedia analytics data is CC0, requires contact user-agent, and advises sequential requests. Issuer public reachability does not establish redistribution rights. The attempted CSV URL is recorded as an unsuccessful format check, not a verified supported endpoint.

`backend/tests/research/fixtures/live-smoke.json` is sanitized actual request metadata, separate from offline tests: SEC ticker/submissions/companyfacts/developer page 403; Wikimedia two-day historical pageviews 200 (captured JSON); iShares page 200 (captured excerpt); GDELT TimeoutError; attempted issuer CSV 200/text-csv but HTML (captured excerpt). The final deadline-aware transport was separately rerun against the same Wikimedia URL: 200, 305 bytes. No denial was bypassed. No full historical SEC/GDELT/holdings success is claimed. Captured payloads are cropped only for offline fixtures; synthetic SEC/CSV/GDELT structural fixtures are explicitly labeled and never described as live captures.

## Validation

`UV_CACHE_DIR=/tmp/aplomb-uv uv run pytest backend/tests/research -q`: **23 passed**. RES-01–08 cover forged/cross-run references, normalized quote offsets, exact-domain/redirect/private-IP rejection, unknown/no-results, inability to certify controversy absence, complete/partial/duplicate/zero-baseline attention, replay before HTTP/cache, hostile instruction text, bounded retry and original timestamp cache reuse. Additional tests cover observed Wikimedia payload, actual mislabeled issuer HTML rejection, explicit sourced quote.figure, safe content/status/size failures and slow-header deadline enforcement. Ruff checks pass. Root independently verified research -> Ledger -> audit and historical denial. No AWS, browser navigation, model credentials, holdings or threshold changes occur here.
