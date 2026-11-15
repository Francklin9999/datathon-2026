# Official policy metadata captures

Captured on 2026-11-15 UTC using `PYTHONPATH=backend .venv/bin/python -m aplomb.world.providers.feeds_extra --source ecb --source uk_sanctions`. Bounded HTTPS, retries and byte cap are in the standalone module. It writes checksum-addressed immutable snapshots through `snapshot.publish`. Refresh is manual; no deployed schedule or network call in the API.

| Source | IDs to register | Capture | Scope |
| --- | --- | --- | --- |
| ECB RSS: [feed](https://www.ecb.europa.eu/rss/press.html), [feed directory](https://www.ecb.europa.eu/home/html/rss.en.html) | `world_ecb_press`; SRC-105, MASTER-047 | `world_ecb_press-2026-11-15-1e30427e9fbb2fae`: 4 releases of 15 feed entries, 11 rejected as non-release records | Current feed page only; title, link and publication time. Speeches and interviews are excluded from normalized rows. No full articles, geography or issuer links. |
| UK Sanctions List [change history](https://www.gov.uk/government/publications/the-uk-sanctions-list), [content API](https://www.gov.uk/api/content/government/publications/the-uk-sanctions-list) | `world_uk_sanctions_updates`; SRC-139 | `world_uk_sanctions_updates-2026-11-15-9132e6eedf76d8f8`: 50 notes of 491 provided | First 50 change notes, not the list itself. No names are matched to securities, no locations inferred from named sanctions regimes. |

ECB normalized SHA-256 `1e30427e9fbb2faed46d28d4d82222fd5cc1927551b81104f708a2ea65ec810d`; raw SHA-256 `1a602fc5e042a4e0de84004e880ecf4bf985836a09beb2da9b22802e13ad09ae`. UK normalized SHA-256 `9132e6eedf76d8f8446bdb0dbdfbd972d94561c8bbee87f50e87492b00212a51`; raw SHA-256 `bb89cc5c8d5549f6d9f424ad98a76dce0733e531847a75fce33a7577e58a2879`. Both retrieved at `2026-11-15T17:11:42Z`; publication timestamps are not proof of historical availability. Snapshots are gated at retrieval.

## Rights and display

ECB [copyright terms](https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html) permit free use of directly obtained information provided it is reproduced accurately, the ECB is cited, and modifications are stated. Sold documents containing the information must notify buyers before payment and each time they access it that it is free on the ECB website. Business or promotional links must load the ECB site in the browser's entire window. Reproduction of authored documents in a different publication needs explicit prior authorization; only press release metadata is normalized. The raw capture is the metadata-only RSS, including titles of non-release feed entries, not linked articles. Do not import article text or frame the original site. Display the source and change disclosure and implement any applicable sales and link conditions before redistribution.

The UK government [terms](https://www.gov.uk/help/terms-conditions) and the source page identify GOV.UK content as Crown copyright licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/), unless otherwise stated. Credit the Foreign, Commonwealth & Development Office and include the OGL link; the notes have whitespace trimmed and are adapted. Linked third-party content is not copied. The raw API response is the official publication's metadata and page content; reuse remains subject to the stated OGL exclusions. Consult the current list and relevant law before any sanctions decision.

## Registration and validation handoff

1. Add `world_ecb_press` and `world_uk_sanctions_updates` to the shared `DatasetId` contract and `PROVIDER_DATASET_IDS` in `backend/aplomb/world/passports.py`, with corresponding contract/OpenAPI artifacts as required. The generic snapshot loader and `provider_passports()` already discover both manifests; `policy` observations currently enter news mode. Source identifiers and scope must also be added to the shared source catalogue.
2. Ensure the source/detail UI exposes the attribution and licence URL, ECB free-access notice where applicable, and opens the source without framing. Generic observation projections currently omit the row's `properties.attribution`, so a visible source name alone does not establish every reuse condition.
3. Shared contract integration remains necessary: with unregistered IDs, `GET /v1/datasets` fails validation and returns 500. The existing HTTP contract test reached that endpoint and failed there; 11 existing provider tests passed and `ruff check` passed. `load_provider_snapshots()` verified both checksums and `provider_passports()` built both records; enum validation rejected both as expected until registration. No new tests were added under the assignment.
4. These are bounded, current metadata captures. No hard completeness, live monitoring, sanctions screening, historical replay, issuer relationship, event location or financial impact claim is supported.

OFAC's recent-actions index was reachable, but no OFAC capture or licence conclusion was established in this assignment; its sanctions-list source rows remain outstanding.

## Subsequent integration

The ECB and UK captures are now registered in the dataset contract, catalog, passport and observations API. ECB publications appear in macro mode and UK list-change notes in conflicts mode, both without map pins. The observation detail displays source attribution and limitations. The registration steps and initial validation failure above describe the pre-integration state; `/v1/datasets` now validates both passports. The selected feeds remain publication metadata and are not sanctions screening or full articles.
