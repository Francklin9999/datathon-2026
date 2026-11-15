"""Capture current-only airport references from the official OurAirports data repository."""
import argparse
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

from aplomb.world.airports import SOURCE_URL, load_airports, parse_airports
from aplomb.world.ingest import http_get


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--capture', type=Path)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Choose a new output directory')
    payload = args.capture.read_bytes() if args.capture else http_get(SOURCE_URL, timeout=20)
    crosswalk = http_get('https://api.worldbank.org/v2/country?format=json&per_page=1000', timeout=15)
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    rows, manifest = parse_airports(payload, crosswalk, now)
    args.out.mkdir(parents=True)
    (args.out / 'airports.json').write_text(json.dumps(rows, ensure_ascii=False, sort_keys=True, indent=1) + '\n')
    (args.out / 'airports_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (args.out / 'airports.csv.gz').write_bytes(gzip.compress(payload, mtime=0))
    (args.out / 'country_crosswalk.json.gz').write_bytes(gzip.compress(crosswalk, mtime=0))
    load_airports(args.out)
    print(f"Verified {len(rows)} airport references; {manifest['rejected']} rejected")


if __name__ == '__main__':
    main()
