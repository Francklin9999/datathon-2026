# Global social and food statistics batch

Implemented one bounded genuine ILOSTAT capture for SRC-108. Acquisition uses the official anonymous ILOSTAT CSV API, rather than claiming the catalogue's SDMX transport has been implemented. The saved dataset contains 2024 total-sex, ages-15-and-over unemployment rates for Canada, Japan and Brazil. Original survey codes, classification/source notes and observation statuses remain inspectable. Percent is a share of the labor force.

The linked official ILO rights page explicitly includes databases, datasets and accompanying metadata under CC BY 4.0 when published from 3 May 2023. Completed-year 2024 observations meet that date condition. The full rights page and three source CSV responses are included in the immutable capture. Attribution and the prescribed adaptation notice are carried into the passport and observation detail.

Capture: `world_ilo_unemployment_2024-2026-11-15-1cb0e3dc60f581d7`; 3 observations; normalized SHA-256 `1cb0e3dc60f581d7ae16bd1eca9d7c6868dc793021b636fe6231000887795fb7f`. The immutable manifest contains exact retrieval time and raw checksums.

Run `python -m aplomb.world.providers.ingest --source ilo` or `python -m aplomb.world.providers.ilo_extra`. Runtime discovery uses the existing saved-capture loader. The World Explorer macro feed exposes the three annual statistics with national country tags and no invented point coordinates. Source-passport discovery is inherited from that loader. The service summary identifies the denominator, year and source survey code. A service already running before this capture needs its normal process refresh because provider discovery is cached.

Runtime validation in `docs/evidence/parallel/agent-3/global-social-stats/runtime-validation.json` checks real saved-data integrity, all three countries, actual `WorldServiceImpl.observations` output, absent point coordinates, annual reference-period precision and exclusion on an as-of date preceding capture. No test files were added and no test suite was run, per the current user instruction.

Shared edits: additive `ilo_extra` import/choice/dispatch in `backend/aplomb/world/providers/ingest.py`, and one dataset-specific observation summary in `backend/aplomb/world/service.py`. New adapter: `backend/aplomb/world/providers/ilo_extra.py`. No active manifest was changed; no deployment, commit or push.

The remaining provider states are precise access/rights blockers:

| Source | Access evidence | Rights evidence and blocker |
|---|---|---|
| SRC-107 UNICEF SDMX | Official SDMX request for Canada 2023 under-five mortality returns HTTP 200 with a genuine one-row CSV. Dataflow metadata also returns HTTP 200. | `https://data.unicef.org/legal/` returns HTTP 403. The reachable UNICEF official general terms at `https://www.unicef.org/legal` require express prior written permission for uses beyond personal/educational purposes and for reproduction beyond de minimis content. No dataset-specific redistribution exemption was established; no UNICEF values were published to runtime. A confirmed dataset-specific reuse grant is needed. |
| SRC-109 WHO GHO | Official WHO dataset terms retrieved successfully, HTTP 200. | `https://www.who.int/about/policies/publishing/data-policy/terms-and-conditions` grants use of the datasets **for public health purposes**; adaptations beyond minimal figure/table style changes require prior written agreement. Investor-platform purpose and normalized distribution are not covered by the retrieved grant. No WHO data acquired for runtime. A compatible purpose/adaptation grant is needed. |
| SRC-110, SRC-200, MASTER-087 FAOSTAT | Official Fenix QCL query for Canada wheat production 2023 returns HTTP 521; official bulk price-download host returns HTTP 403. The FAOSTAT application shell returns HTTP 200, with no statistical payload. | General FAO website terms at `https://www.fao.org/contact-us/terms/en/` permit noncommercial use with attribution and require authorization for commercial reuse. A more specific FAOSTAT licence could supersede those terms, but was not verified from the application shell. Restore access to an authorized official payload and verify its dataset licence; shell reachability is not integration. |

Requests were bounded and anonymous; no keys, logins, subscriptions or paid routes were attempted. Successful UNICEF and ILO source probes outside the published ILO capture remain temporary files only. Rights review evidence and endpoint statuses are retained in `docs/evidence/parallel/agent-3/global-social-stats/access-rights-review.json`.
