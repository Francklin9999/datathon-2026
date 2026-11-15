# New provider interface and validation

Owned new paths: `backend/aplomb/world/providers/`,
`backend/aplomb/world/bundle/providers/`,
`backend/tests/test_world_public_providers.py`,
`docs/evidence/parallel/agent-3/source-audit/`, SOURCES.csv and BLOCKERS.md.
No existing service, contract or frontend file was edited by the source worker.

```python
from aplomb.world.providers.snapshot import load_provider_snapshots
rows, manifests = load_provider_snapshots()
# Optional historical inspection gates at capture, not observation:
rows, manifests = load_provider_snapshots(as_of="2026-11-14T00:00:00Z")
```

Rows carry `id`, `sourceId`, `category`, `title`, `sourceUrl`, `retrievedAt`,
`availableAt`, optional `observedAt`/`publishedAt`, optional `latitude`/`longitude`,
optional `countryIso3`, and `properties`. Source categories are energy, aviation,
hazards and policy. GDACS adds bounded worldwide disaster alerts to hazards.
The loader validates all normalized/raw hashes, counts,
coordinates, identities and availability gates. An absent directory yields unavailable
empty tuples. Corruption raises ValueError and should remain an isolated optional-source error.

The parent service consumes captures through a narrow adapter. Policy records have country
jurisdiction but no point. NOAA polygon anchors are display positions with original polygons
preserved in properties. Aviation records are weather stations, never aircraft tracking.
WRI reported-owner text is reference metadata, never an established issuer/security relation.
Captures are latest/current references and never original historical vintages.

Refresh command:

```sh
PYTHONPATH=backend .venv/bin/python -m aplomb.world.providers.ingest \
  --source aviation --source noaa --source plants --source policy --source gdacs
```

Each source fails independently and prior captures remain intact. Snapshot directories are content
addressed with capture date; repeated identical publication is idempotent and attempted changes
to an existing version fail. The source directory remains a branch-owned capture collection,
without changes to the active shared snapshot pointer.

Transport uses fixed HTTPS host allowlists, pre-request redirect restrictions, per-provider rate
limits, socket/read deadlines, byte caps and bounded retries for transient HTTP/network failures.
No third-party source call occurs on runtime reads. Eleven targeted synthetic tests verify parser
failure/geometry/pagination/future-date rules and immutable/temporal/integrity behavior.
Real capture validation and documentation access evidence are saved separately.

Source quality/rights evidence:

- `source-audit/capture-validation.json`: actual captured counts and raw/normalized hashes.
- `source-audit/documentation-reachability.json`: 160 distinct assigned documentation URLs;
  source access and reuse rights are not inferred from response codes.
- `source-audit/{noaa_terms,aviation_docs,wri_readme,ucdp_terms}.json`: document hashes,
  captured dates and short rights/quota excerpts.
- `source-audit/provider-tests.txt`: focused test result.

The WRI repository CSV is labeled a hash-pinned repository snapshot. Its last named release is
v1.3.0, and maintenance ended in 2022; this capture does not imply live plant observations.
GDACS content is attributed to GDACS/European Commission JRC under the Commission's linked
copyright notice. Only structured alert metadata was captured; linked third-party reports and
images were excluded. Its newest 100-record page is intentionally incomplete, and a
representative point is not a disaster impact footprint.
Cross-agent source/service/frontend integration and browser acceptance belong to the parent task
and their verified status is tracked in the per-source report.

NASA POWER provides 31 daily gridded 2 m temperature values for each of six
requested locations. The October 2026 period is fixed and bounded. Its `LST`
calendar dates are rendered as day anchors, without inventing an exact UTC
measurement time or claiming a station observation. Its six public requests
are captured separately with checksums.
