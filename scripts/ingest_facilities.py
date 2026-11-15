"""Capture a projected ECCC dataset without retaining public contact/personal columns."""
import argparse
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

from aplomb.world.facilities import SOURCE, load_facilities, normalize, project_source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--capture', type=Path)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Choose a new output directory')
    if args.capture:
        payload = args.capture.read_bytes()
    else:
        with urlopen(SOURCE, timeout=20) as response:
            payload = response.read(16_000_001)
        if len(payload) > 16_000_000:
            raise ValueError('ECCC response exceeds bounded capture limit')
    projected = project_source(payload)
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    rows, meta = normalize(projected, now, original_sha256=hashlib.sha256(payload).hexdigest())
    args.out.mkdir(parents=True)
    (args.out / 'facilities_source.csv.gz').write_bytes(gzip.compress(projected, mtime=0))
    (args.out / 'facilities.json').write_text(json.dumps(rows, ensure_ascii=False, sort_keys=True, indent=1) + '\n')
    (args.out / 'facilities_manifest.json').write_text(json.dumps(meta, indent=2, ensure_ascii=False) + '\n')
    load_facilities(args.out)
    print(json.dumps({'rows': len(rows), 'year': meta['reportingYear'], 'rejected': meta['rejected']}))


if __name__ == '__main__':
    main()
