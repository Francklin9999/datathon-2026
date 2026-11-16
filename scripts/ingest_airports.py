"""Capture current-only airport references from the official OurAirports data repository."""
import argparse
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

from aplomb.datastore.global_fx import read_capture
from aplomb.world.airports import SOURCE_URL, load_airports, parse_airports
from aplomb.world.ingest import http_get

CROSSWALK_URL = 'https://api.worldbank.org/v2/country?format=json&per_page=1000'


def captured_at(value: str) -> str:
    try:
        datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
    except ValueError as exc:
        raise argparse.ArgumentTypeError('expected YYYY-MM-DDTHH:MM:SSZ') from exc
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--capture', type=Path, help='airports CSV, plain or .gz (e.g. data/inputs/airports/airports.csv.gz)')
    parser.add_argument('--crosswalk-capture', type=Path,
                        help='World Bank country list, plain or .gz (e.g. data/inputs/airports/country_crosswalk.json.gz)')
    parser.add_argument('--captured-at', type=captured_at,
                        help='UTC retrieval time of the captures, YYYY-MM-DDTHH:MM:SSZ (default: now); '
                             'a replay of data/inputs/airports/ takes capturedAt from the committed airports_manifest.json')
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error('Choose a new output directory')
    payload = read_capture(args.capture) if args.capture else http_get(SOURCE_URL, timeout=20)
    crosswalk = read_capture(args.crosswalk_capture) if args.crosswalk_capture else http_get(CROSSWALK_URL, timeout=15)
    now = args.captured_at or datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
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
