# Additional world event capture

The gzip file retains the original USGS GeoJSON response for the 2025-11-12 to
2026-11-12 earthquake window at magnitude 5.0 or greater. Its SHA-256 and retrieval
time are recorded in the packaged world manifest. The response contains 1,999
source events, with no rejected records. Stable source URLs identify duplicates
against the prior magnitude-6 archive, resulting in 1,860 additional earthquakes,
all below magnitude 6.0.

The expanded bundle keeps all prior official releases and the magnitude-6 archive.
Every captured earthquake is one of its 2,528 hazard records. The event feed
keeps natural disasters only as USGS earthquakes of magnitude 6.0 or more (team
decision, `method.naturalDisasterRule` in the manifest), so it contains 751
events: 83 official releases and 668 earthquakes. The 1,860 additional
earthquakes and the 479 NASA EONET records are not in the feed. Occurrence dates
do not establish historical application availability. Epicenters do not
establish damage, affected areas or portfolio impact.

Reproduce into a fresh directory:

```bash
PYTHONPATH=backend .venv/bin/python scripts/expand_world_events.py \
  --out /tmp/aplomb-expanded-world \
  --start 2025-11-12 --end 2026-11-12 --min-magnitude 5.0
```

Source: [USGS Earthquake Catalog](https://earthquake.usgs.gov/fdsnws/event/1/).
USGS data is a United States Government work; see the
[USGS credits policy](https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits).
Measurements may be revised by the source after capture.
