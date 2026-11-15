"""Capture a bounded public GLEIF candidate search; does not establish instrument mappings."""
import argparse
import json
from pathlib import Path

from aplomb.intelligence import GLEIFClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output already exists; choose a new path')
    raw = args.output.with_suffix('.raw.json')
    if raw.exists():
        parser.error('raw output already exists; choose a new path')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = GLEIFClient(capture=lambda body: raw.write_bytes(body)).search(args.query)
    result['source']['raw_capture'] = raw.name
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"Stored {result['returned']} candidate records; total search results: {result['total']}")


if __name__ == '__main__':
    main()
