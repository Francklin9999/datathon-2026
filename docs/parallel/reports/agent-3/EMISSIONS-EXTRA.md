# Remaining emissions and energy sources

Two anonymous sources have genuine immutable captures and current World Explorer
observation consumption. No account, paid service, deployment, commit or new test
file was used. Catalogue and passport registrations are coordinated with the
integrating agent; this batch does not edit shared catalogue/passport files.

| Source | Result |
|---|---|
| SRC-195 Fraunhofer Energy-Charts API | Integrated selected German public net generation intervals, CC BY 4.0 |
| SRC-224 Global Carbon Project | Integrated selected Global Carbon Budget 2026 v0.1 annual global components, CC BY 4.0 via ICOS RI |
| SRC-221 EPA eGRID | Check only: workbook accessible; commercial reuse of every source field not established by the general EPA disclaimer |
| SRC-225 EDGAR EU Emissions | Check only: EU-owned data CC BY 4.0, but IEA fossil CO2 has CC BY-NC-ND restrictions; anonymous separate methane archive timed out |
| SRC-228 / MASTER-072 World Bank Climate Portal | Check only: official download page returned HTTP 403 |

## Captures

`world_energy_charts_de_power-2026-11-15-4234af144cb40133` contains
384 valid rows: solar, onshore wind, offshore wind and fossil gas, each with
96 fifteen-minute intervals on 2026-11-14 in Germany. Units are MW, not MWh.
Source local timestamps are converted to UTC; the local reporting day is retained
by the exact bounded source request. The response explicitly states CC BY 4.0;
the publisher OpenAPI document independently grants CC BY 4.0 for API data unless
otherwise specified. This endpoint's response states no exception. Source price
endpoints have separate restrictions and are not captured.

Normalized SHA-256:
`4234af144cb40133e28b452f252a0e94a87b5a41d6ae604bb6d9761499da3019`.
Original JSON SHA-256:
`423ce92a144746348e8a61a929a8c0e7d6a40bb5659bf8a1a9fbffee6d783aca`.

`world_global_carbon_budget_2026-2026-11-15-b1961f1ded4e66be` contains
469 valid rows: seven annual global components for 1959–2025 inclusive.
Components are fossil emissions excluding carbonation, land-use change emissions,
atmospheric growth, ocean sink, land sink, cement carbonation sink and budget
imbalance. Values retain GtC/yr; no conversion to CO2 or inferred geography.
Version 0.1 is a revised scientific estimate, with source uncertainty and future
revisions; it is not a live emissions stream.

The publisher metadata carries the original workbook SHA-256, independently
matched to downloaded bytes:
`b46051d3f255eb39f74c60f3c1a20450d36795a34865bb2dfb90949c0bf3e4a2`.
Normalized SHA-256:
`b1961f1ded4e66be42a681cea2516bd1e3c5d983000b7d5a463a4e0efc534b9a`.
Dataset metadata explicitly selects the ICOS data licence; its captured licence
page grants CC BY 4.0 and allows adaptation and commercial redistribution.
The original data citation, DOI `10.18160/GCP-2026`, source link and modification
notice are retained. Download uses the publisher's anonymous licence acceptance
flow with an ephemeral cookie jar. No registered user or credentials are needed.

Both captures retain complete original response/workbook and rights metadata
in `backend/aplomb/world/bundle/providers/<version>/`, with manifests and hashes.
Coordinates remain null because these are national/global aggregates.
No facility, operator, issuer, security, ESG score or financial exposure is inferred.
Original historical availability is unproven; every row gates at capture time,
including estimates whose reference year is decades earlier.

## Runtime and verification

Existing `/v1/world/observations` consumes these saved observations through energy
and environment modes, with search, country selection and ordinary pagination.
HTTP checks used the actual FastAPI app and TestClient with the active datastore,
and wrote `docs/evidence/parallel/agent-3/emissions-extra/runtime.json`.
Germany energy search returned 386 observations (384 new intervals plus two
existing Germany references); Global environment search returned 469.
Both corresponding `asOf=2026-11-14` requests returned zero.
The integrity loader separately proved exactly 384 and 469 records, verified
every raw and normalized checksum, and confirmed 853 null coordinate pairs.
No browser verification or newly created test suite is claimed.

Refresh from the repository root:

```bash
PYTHONPATH=backend .venv/bin/python -m aplomb.world.providers.emissions_extra --source energy
PYTHONPATH=backend .venv/bin/python -m aplomb.world.providers.emissions_extra --source gcb
```

Each publication is content addressed and immutable. Fixed source URLs, no
unexpected redirects, a 25-second timeout and a 2 MB payload cap constrain
captures. XML is parsed without executing macros or evaluating formulas;
uncompressed workbook contents have a 30 MB cap. The quality gate checks source
identity, units, selected series/components, years, finite values, source rights,
identifiers, timestamps and duplicate identity.

## Exact unresolved review

EPA detailed download resolves to
`https://www.epa.gov/egrid/detailed-data` and links the 2023 revision-two workbook.
The download was reachable and inspected, but the EPA generic disclaimer
distinguishes EPA-produced geospatial data from third-party copyrighted material
and warns that individual documents may have different conditions. A blanket
commercial reuse licence for the complete selected eGRID emissions fields was
not established. No eGRID product capture or parser is claimed.

EDGAR 2026 report and workbook distinguish EU-owned CC BY 4.0 material from
IEA-EDGAR fossil CO2 data licensed CC BY-NC-ND 4.0. The combined workbook was
inspected only to identify that restriction. The dedicated source methane ZIP
was discovered in the official dataset page, but its bounded request timed out;
no methane integration or dataset rights extrapolation to fossil CO2 is claimed.
The inspected eGRID and combined EDGAR workbook bytes were discarded;
access-review records retain response sizes, hashes and the reason for removal.
Only rights and publisher documentation remain in evidence.

Climate Knowledge Portal download access returned HTTP 403; WDI or NASA data
are not counted as this distinct source. Evidence of all successful and failed
requests is in `docs/evidence/parallel/agent-3/emissions-extra/review*.json`.
