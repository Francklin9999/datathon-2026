"""Build the searchable candidate directory; never infer integration or reuse rights."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def build():
    rows = list(csv.DictReader((ROOT / 'data/catalog/worldwide-apis.csv').open(encoding='utf-8')))
    ids = set()
    output = []
    for row in rows:
        parsed = urlsplit(row['url'])
        if parsed.scheme != 'https' or not parsed.hostname or row['access'] not in set('AFDMSTPRU'):
            raise ValueError(f'Invalid candidate: {row["name"]}')
        source_id = 'src_' + hashlib.sha256((row['category'] + '|' + row['name'] + '|' + row['url']).encode()).hexdigest()[:16]
        if source_id in ids:
            raise ValueError('Duplicate candidate identity')
        ids.add(source_id)
        output.append({'sourceId': source_id, **row, 'integrationStatus': 'candidate', 'reuseStatus': 'unverified'})
    return json.dumps(output, indent=2, ensure_ascii=False) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    target = ROOT / 'web/src/data/source-directory.json'
    result = build()
    if args.check:
        if not target.exists() or target.read_text() != result:
            raise SystemExit('Source directory drift: run python scripts/build_source_directory.py')
    else:
        target.write_text(result)
