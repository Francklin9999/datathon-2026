"""Append a bounded EONET capture to the verified world bundle, retaining existing sources.

The source does not establish original publication/availability times. This snapshot is for
current exploration only; no historical replay gains access to these records.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from aplomb.contracts.models import WorldEvent
from aplomb.world.dataset import load_bundle
from aplomb.world.ingest import BUNDLE_DIR, build_bundle, http_get, parse_eonet, write_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='New output directory; existing artifacts are never overwritten')
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    args = parser.parse_args()
    # Parse dates before constructing a URL; bound each batch to one year.
    start, end = datetime.fromisoformat(args.start), datetime.fromisoformat(args.end)
    if start > end or (end - start).days > 366:
        parser.error('Use an ordered date window of at most 366 days')
    if args.out.exists():
        parser.error('Output directory already exists; choose a fresh directory')
    url = f'https://eonet.gsfc.nasa.gov/api/v3/events?status=all&start={args.start}&end={args.end}&limit=500'
    payload = http_get(url, timeout=20)
    events, rejected = parse_eonet(payload)
    if not events:
        raise SystemExit('No accepted EONET events; no bundle written')
    old = load_bundle(BUNDLE_DIR)
    now = datetime.now(timezone.utc)
    source = {'id': 'nasa_eonet', 'name': 'NASA EONET v3 natural events', 'url': url,
              'terms': 'https://eonet.gsfc.nasa.gov/what-is-eonet; linked third-party content has separate terms',
              'retrievedAt': now.strftime('%Y-%m-%dT%H:%M:%SZ'), 'status': 'ok', 'items': len(events),
              'rejected': rejected, 'payloadSha256': hashlib.sha256(payload).hexdigest(),
              'note': 'Bounded first 500 records; completeness not established. Observation is not publication.'}
    sources = [s for s in old.manifest['sources'] if s['id'] != 'nasa_eonet'] + [source]
    previous = [e for e in old.events if e['origin'] != 'eonet']
    files = build_bundle(previous + events, list(old.hazards), sources, built_at=now,
                         start=min(old.manifest['requestedWindow']['start'], args.start),
                         end=max(old.manifest['requestedWindow']['end'], args.end),
                         version_suffix='-eonet-' + source['payloadSha256'][:8])
    for event in json.loads(files['events.json']):
        WorldEvent.model_validate(event)
    write_bundle(files, args.out)
    load_bundle(args.out)
    print(json.dumps(source, indent=2))


if __name__ == '__main__':
    main()
