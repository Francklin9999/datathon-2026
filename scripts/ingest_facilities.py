"""Capture a projected ECCC dataset without retaining public contact/personal columns."""
import argparse
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

from aplomb.datastore.global_fx import read_capture
from aplomb.world.facilities import SOURCE, load_facilities, normalize, project_source


def captured_at(value: str) -> str:
    try:
        datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
    except ValueError as exc:
        raise argparse.ArgumentTypeError('expected YYYY-MM-DDTHH:MM:SSZ') from exc
    return value

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--capture', type=Path,
                        help='ECCC CSV, plain or .gz: an original download or the retained data/inputs/eccc/facilities_source.csv.gz')
    parser.add_argument('--captured-at', type=captured_at,
                        help='UTC retrieval time of the capture, YYYY-MM-DDTHH:MM:SSZ (default: now); '
                             'a replay of data/inputs/eccc/ takes capturedAt from the committed facilities_manifest.json')
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error('Choose a new output directory')
    if args.capture:
        payload = read_capture(args.capture)
    else:
        with urlopen(SOURCE, timeout=20) as response:
            payload = response.read(16_000_001)
        if len(payload) > 16_000_000:
            raise ValueError('ECCC response exceeds bounded capture limit')
    projected = project_source(payload)
    # A retained projection is not the original download, whose hash is then unknown.
    original_sha256 = None if projected == payload else hashlib.sha256(payload).hexdigest()
    now = args.captured_at or datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    rows, meta = normalize(projected, now, original_sha256=original_sha256)
    args.out.mkdir(parents=True)
    (args.out / 'facilities_source.csv.gz').write_bytes(gzip.compress(projected, mtime=0))
    (args.out / 'facilities.json').write_text(json.dumps(rows, ensure_ascii=False, sort_keys=True, indent=1) + '\n')
    (args.out / 'facilities_manifest.json').write_text(json.dumps(meta, indent=2, ensure_ascii=False) + '\n')
    load_facilities(args.out)
    print(json.dumps({'rows': len(rows), 'year': meta['reportingYear'], 'rejected': meta['rejected']}))


if __name__ == '__main__':
    main()
