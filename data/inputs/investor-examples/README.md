# Shared investor examples and public filing captures

These inputs create five **fictional** shared profile templates, fifteen accounts,
five map records, and five attributed public 13F captures. The locations describe
fictional residences and account custody locations, not issuer exposure or actual
people's whereabouts. All account balances and investor circumstances are examples.
Account conversion receipts use the app's existing foreign-exchange data.

Prepare the records without writing to a database:

```sh
.venv/bin/python scripts/prepare_investor_examples.py
```

The output is `.artifacts/investor-examples/seed-records.json`. Create these records
conditionally in the existing profiles/cache tables; never overwrite a session
partition or an existing shared record. Profiles use `SHARED#PROFILES`, map records
use `SHARED#INVESTOR_MAP`, and filings use `SHARED#13F`. The hosted seed and its
verification report are preserved under
`s3://aplomb-data666c94c7-wb93thujcyb4/investor-examples/5de4f6dd964d85ae2d764c8e01db8f5462a2bea2a1534affa6a336aa14c34f74/`.

The filing JSON files contain the complete rows displayed by the attributed
13f.info index at capture time. `filings/manifest.json` records the source links,
SEC accession links, dates, units, checksums, and limitations. The SEC originals
returned HTTP 403 during this capture, so these are explicitly third-party
transcriptions, not verified original SEC information tables. Index totals can
differ from row sums; options and all source rows remain available in the capture.
The HTML pages are not bundled; the manifest preserves their original filenames
and recorded hashes as provenance, but those hashes cannot be verified locally.
An associated investor's name describes their connection to the manager and does
not identify their personal holdings or net worth.

The comparison includes only positive, non-option positions whose exact ticker
and CUSIP match available prices. Coverage is measured against the sum of all
captured indexed rows, including options, which can differ from the source's
reported total. It displays the covered proportion and
normalizes that subset to 100. Both sides use the selected profile's reporting
currency and a common period starting no earlier than the indexed filing date.
The strategy uses its time-weighted index, excluding external deposits and
including configured trading costs. The filing subset is held without trading,
fees, or taxes. Scion has no covered long positions and cannot produce a comparison.

Capture happened after the price snapshot. The output is a retrospective
hypothetical scenario; it is not a point-in-time backtest or a fund's actual
performance. It excludes undisclosed cash, shorts, other assets, leverage, and
subsequent trades.
