"""Create a new, separately versioned current-only WDI country snapshot.

No existing file is overwritten. Copy the two validated outputs into a candidate bundle only
as part of a reviewed, paired release. Example: uv run python scripts/ingest_world_bank.py --out /tmp/wdi-new
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path

from aplomb.world.country_macro import collect_indicators, load_snapshot, serialize_snapshot
from aplomb.world.ingest import http_get


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Output already exists; use a new directory')
    rows, metadata = collect_indicators(lambda url: http_get(url, timeout=15), retrieved_at=datetime.now(timezone.utc))
    payload, manifest = serialize_snapshot(rows, metadata)
    args.out.mkdir(parents=True)
    (args.out / 'country_macro.json').write_text(payload, encoding='utf-8', newline='\n')
    (args.out / 'country_macro_manifest.json').write_text(manifest, encoding='utf-8', newline='\n')
    _, checked = load_snapshot(args.out)
    print(f"Validated {checked['rowCount']} observations for {checked['countryCount']} countries: {checked['dataVersion']}")


if __name__ == '__main__':
    main()
