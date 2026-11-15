# USGS weekly earthquake GeoJSON

The [USGS weekly magnitude 4.5+ feed](https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson) was captured without a key or payment. The official USGS [copyright notice](https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits) describes United States Government public-domain works. The adapter in `backend/aplomb/world/providers/quake_feed.py` retains source reported point epicenters and times for magnitude 4.5 to below 6; magnitude 6+ rows are excluded because the baseline catalog already includes that range. The bounded captured feed had 118 source events and yielded 117 selected rows in `world_usgs_geojson-2026-11-15-9667d308a445ab36`. Its manifest records raw and normalized hashes, quality counts, rights and coverage.

An epicenter is a source point, not an affected area or proof of damage, issuer exposure or financial impact. Source reported magnitudes and locations may change. This is the current weekly feed only, with no original historical vintages; replay is gated at the capture timestamp. Refresh manually with `PYTHONPATH=backend .venv/bin/python -m aplomb.world.providers.ingest --source quake`.

The new dataset is registered in the contract, passports and hazard observation list. Source IDs: SRC-171 and MASTER-066.
