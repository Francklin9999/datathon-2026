# Research — source adapters and verified citations

**Track:** T09. **Tier:** P0 evidence missingness/verification; external enrichment P1. Read [tool signatures](../../../contracts/tools.md) §5 and [Evidence](../../../contracts/schemas.md) §6.

## 1. Responsibility and boundary

Collect public evidence that answers explicit questions. Preserve URL, publisher, publication/retrieval dates and cached source passage. Research returns evidence, not portfolio verdicts. No retrieval path can change holdings, thresholds or access credentials. Historical runs cannot call live research; the run registry enforces this restriction.

## 2. Adapter contract

`ResearchAdapter.search(query, context) -> SearchResult`; `fetch(url, context) -> FetchedDocument`; `verify_quote(document, quote) -> QuoteCheck`; `save_evidence(input, document_ref, context) -> Evidence`. Every adapter implements declared tool args/results from the catalog and receives an injectable HTTP client/cache/clock. FetchedDocument stores canonical URL, redirects, status, content type/hash, text, retrieval timestamp, publication metadata and availability confidence. Truncated passages retain offsets into cached text.

Adapters: EDGAR company/ticker resolution, submissions and filing text/company facts; GDELT cached article index; allow-listed page fetch; optional Browser; Wikimedia attention; issuer ETF holdings. Return explicit no-results/rate-limited/source-unavailable reasons, never invented citations. `attention.pageviews` is registered only when a verified ticker→article mapping is injected and `etf.holdings` only when a dated issuer file is injected; the application composition injects neither, so neither tool is offered there. The EDGAR tools are bound only with `research_tool_handlers(..., sec=True)`, which the application does not pass: the owner removed the SEC sources after HTTP 403 refusals (`intelligence/data/source_dispositions.json` SRC-034..SRC-042). `emissions.facilities` (registered in `api/runtime.build_registry`, not here) exists only with the world dataset and the `world_layer_facilities` flag, and is offered only in a run whose cutoff is on or after the facility capture day (`facility_capture_known`); before it the tool could only answer an evidence gap, so no research call is spent on it.

## 3. Document and number verification

Only evidence saved against a document fetched/loaded into the same run context can support prose. Normalize whitespace, then require quote substring match with offsets; retain original text/hash. A model-supplied URL or claim is not proof of retrieval. Quote <=400 characters by contract and additionally respect publisher usage terms. Numeric document values enter facts as `quote.figure` only from structured sources the ledger reparses (XBRL rows, issuer CSV weights), preserving source unit, not as model arithmetic; a figure quoted in prose is not registered as a fact. Missing/ambiguous units make the figure unverified.

Publication date is source-provided when found, else null. Retrieved today does not imply published today or historically available. Domain/publisher tier is computed, not asserted by model. News index headlines alone do not verify a full article's claim.

## 4. Tiers, network policy and verified references

Tier 1 = exact official regulator/central-bank/statistical-agency/issuer domains. Tier 2 = explicit reviewed publisher list. Tier 3 = other permitted sites. Maintain structured domain mapping with source/rationale and match subdomains correctly; substring matching is forbidden. Tier 3 alone cannot clear an evidence gap. Wikimedia is authoritative for its page-view count, not for investment quality.

Use HTTPS, validated public DNS targets, response byte/time limits, safe content types, limited redirects and a descriptive source user-agent. Reject localhost/private/link-local/metadata addresses and recheck redirects/DNS targets. Treat fetched text as untrusted data; instructions embedded in it have no tool authority. No cookies, account login or paywall bypass. `web.browse` ([browser.py](browser.py)) reads pages in the AgentCore managed browser (`aws.browser.v1`), behind `research_open_web`: one session per call, always stopped; CDP over the session's SigV4-signed automation stream with a deadline on every read; an allow-listed HTTPS start page (required) and only allow-listed links whose text or path names a task word (words of the site's own name do not count); the final URL after redirects must be allow-listed too; at most five pages, one capture per page. Each captured page is a run document (rendered markup hash, rendered text), so `research.save_evidence` verifies quotes against it exactly as for direct fetch. Without the flag the tool is not registered. An event brief whose source is an allow-listed official page gets a code-owned research question (`Q-EVENT-SOURCE`, preferred tools `web.browse` then `research.save_evidence`) when the browser exists, because the planner, told never to assume an effect, proposes none; the researcher still chooses the tool calls.

Primary references for implementers: [SEC developer resources](https://www.sec.gov/about/developer-resources), [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [Wikimedia analytics API](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/), [GDELT project](https://www.gdeltproject.org/). Exact endpoints, auth/headers, quotas and availability are `[VERIFY]` adapter-owner tasks; record a checkedAt and official link before enabling a live adapter. Favor cached batches and backoff on 429. Never interpret HTTP reachability as data/licence validation.

## 5. Mateo and exposure questions

Controversy search asks about a specific issuer, environmental/social topic, dates and source scope. Preserve the allegation/report status rather than generalizing to guilt. No result → evidence gap. Verified relevant tier-1/2 item → evidence-rule tension for user review, not automatic conflict or “ESG score.” Baseline Mateo remains insufficient without research. Any significant-controversy judgment remains unresolved by code.

ETF holdings: dated issuer files, exact constituent IDs, weights/coverage, partial-coverage flag. Event-to-holding claims must identify link type and supporting evidence; company named, listing-country proxy, documented operations/revenue and ETF look-through are different strengths of evidence. Price response, if computed, remains observation not causation.

## 6. Attention (`M_ATTENTION_RATIO`)

Use a documented ticker→article mapping with entity verification. Ratio = mean daily views over last 30 complete UTC days ÷ mean over preceding 365 complete days, with nonoverlapping windows. Require full expected daily coverage and positive baseline; otherwise unknown. Elevated = ratio >=2.0 (team assumption, informational). Record windows, page/project/access/agent dimensions, retrieval date and mapping evidence. Bots/API outages/ambiguous articles and a zero baseline cannot be interpreted as high attention. This signal never changes a verdict.

## 7. Cache and failure behavior

Cache keys include adapter/version, normalized args, retrieval day, data version and asOf/mode. Shared cached source bytes can be reused, but evidence IDs remain run-local. Record whether result came from cache and original retrieval time. Live failures use bounded jitter/backoff and honor Retry-After within run budget; no retry storms from globe clicks. Expired cache may be shown only with stale label and original dates.

RES-01 exact quote check/forged URL rejection. RES-02 domain tiers/redirect/private-IP rejection. RES-03 no results remains nee. RES-04 one source cannot certify absence of controversy. RES-05 full/partial attention and zero baseline. RES-06 replay cannot call transport. RES-07 prompt injection cannot register tools or change profile. RES-08 retry/cache behavior with recorded responses. Handoff a captured offline response per adapter plus a separately logged live smoke result.
