"""Publish a pinned Bank of Canada FX capture as a new snapshot (never activates it)."""
import argparse
import json
from pathlib import Path

from aplomb.datastore.global_fx import publish_global_fx, read_capture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, default=Path('data'))
    parser.add_argument('--base-version', default='snap-20261114-sourced')
    parser.add_argument('--new-version', default='snap-20261115-globalfx')
    parser.add_argument('--capture', type=Path, default=Path('data/inputs/global-fx/boc-20261115.json.gz'))
    parser.add_argument('--metadata', type=Path, default=Path('data/inputs/global-fx/boc-20261115.metadata.json'))
    args = parser.parse_args()
    manifest = publish_global_fx(args.data_root, args.base_version, args.new_version,
                                 read_capture(args.capture), json.loads(args.metadata.read_text()))
    print(json.dumps({'version': manifest['dataVersion'], 'fx': manifest['datasets']['fx_boc_global']}, indent=2))


if __name__ == '__main__':
    main()
