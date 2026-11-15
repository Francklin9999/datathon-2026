# openFDA aggregate drug enforcement capture

SRC-239 is integrated as `world_fda_drug_enforcement_counts`. An anonymous HTTPS capture on **2026-11-15T17:27:51Z** loaded **4 aggregate observations** representing **738 matching drug enforcement records** into the existing immutable provider bundle. The source reports its last update as **2026-11-04**.

| Classification | Matching records |
| --- | ---: |
| Class I | 38 |
| Class II | 641 |
| Class III | 57 |
| Not Yet Classified | 2 |

The fixed [API request](https://api.fda.gov/drug/enforcement.json?search=report_date:%5B20260101+TO+20261115%5D&count=classification.exact) filters `report_date` inclusively from 2026-01-01 through 2026-11-15 and groups by `classification.exact`. Each count is a count of matching enforcement records, not unique recall events, patients, adverse outcomes, incidence, media attention, or a safety score. This is a bounded health regulatory aggregate observation. It carries no geography or coordinates; FDA jurisdiction does not establish product distribution geography.

## Rights and access evidence

The current [openFDA terms](https://open.fda.gov/terms/) and [data licensing page](https://open.fda.gov/license/) state that openFDA data are public domain with CC0 1.0 dedication unless otherwise noted; copying, modification and commercial distribution are permitted. The terms reserve exclusions for third-party copyrightable works and specifically restrict GMDN content. This capture requests only FDA classification labels and numeric counts. It includes no product descriptions, recall reasons, patient data, manufacturer identity, drug labeling text, GMDN codes/names/definitions, logos or imagery. The [drug enforcement documentation](https://open.fda.gov/apis/drug/enforcement/) contains no contrary rights warning for these numeric aggregate fields.

Credit is supplied in the manifest and every row: “Data provided by the U.S. Food and Drug Administration (https://open.fda.gov). Adapted by Aplomb; no FDA endorsement.”

The [authentication page](https://open.fda.gov/apis/authentication/) contains inconsistent wording: it first says an API key is required, then expressly lists **no-key limits of 240 requests per minute and 1,000 requests per day per IP**. The actual count request succeeded without a key, login, Authorization header or payment. This documents anonymous access observed at capture time and does not promise continued access. The manual collection makes one API call and five official documentation calls; no limit bypass, key acquisition or background poller is added.

FDA warns that this endpoint **should not be used to issue public recall alerts or track recall lifecycles**, and that openFDA must not guide medical decisions. Those limits are recorded in both manifest and rows. It does not establish a current active recall count or current public safety alert: reports can be revised, source updates are weekly, and the queried report date is distinct from recall initiation and current status.

## Implementation and validation

New adapter: `backend/aplomb/world/providers/fda_extra.py`.

```sh
PYTHONPATH=backend .venv/bin/python -m aplomb.world.providers.fda_extra \
  --directory backend/aplomb/world/bundle/providers
```

Retrieval accepts six fixed official HTTPS URLs, refuses redirects, uses 25-second socket and elapsed read limits, caps each body at 2 MB and checks response content types. The parser requires the expected aggregate envelope, official terms/license URLs, a nonfuture source update, only the four documented classification values, unique groups and positive integer counts; individual aggregate records must contain exactly `term` and `count`. Rows are validated before publication.

Version: `world_fda_drug_enforcement_counts-2026-11-15-098d854b2a80f3d8`.

The version directory contains `observations.json`, `manifest.json` and six SHA-256 indexed raw captures, including exact rights/access/source documentation. The existing provider loader successfully loaded all 4 rows and verified raw and normalized checksums. Live evidence is in `docs/evidence/parallel/agent-3/fda-extra/`; `capture-validation.json` records the version, counts and integrity result. No tests were added or run.

All rows gate availability at capture time. The query window and `sourceLastUpdated` are reference metadata, not proof that the observed aggregate was available in the past. No historical replay, issuer link, exposure, financial effect, public attention or causal health claim is established.

Only the new adapter, report, evidence and provider version are added. Registration and source ledger updates remain with the parent agent.
