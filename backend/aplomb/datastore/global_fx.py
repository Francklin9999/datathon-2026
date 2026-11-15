"""Publish a separately versioned Bank of Canada FX snapshot without altering its parent.

Only current-mode reads use an assumed publication time; historical-mode reads are withheld
until the actual capture timestamp because this capture does not establish original vintages.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import os
import re
import secrets
import shutil
from pathlib import Path

from .availability import fx_row
from .errors import IngestionError, SnapshotIntegrityError
from .integrity import canonical_sha256, sha256_hex
from .snapshot import LocalDataStore, _check_version_label
from .timeutil import normalize_ts, parse_date


def normalize_capture(payload: bytes, metadata: dict, as_of: str) -> tuple[bytes, dict]:
    """Validate the whole response and emit sorted CAD-per-unit rows; never infer missing data."""
    if hashlib.sha256(payload).hexdigest() != metadata.get('rawSha256'):
        raise IngestionError('Bank of Canada FX raw capture hash mismatch')
    retrieved = normalize_ts(metadata['retrievedAt'], 'retrievedAt')
    cutoff = parse_date(as_of, 'as_of')
    if retrieved[:10] < as_of:
        raise IngestionError('capture predates the requested snapshot end date')
    url = metadata.get('sourceUrl', '')
    if not url.startswith('https://www.bankofcanada.ca/valet/observations/'):
        raise IngestionError('unexpected FX source URL')
    codes = metadata.get('series')
    if not isinstance(codes, list) or not codes or len(codes) != len(set(codes)):
        raise IngestionError('invalid currency list')
    if any(not isinstance(c, str) or not re.fullmatch('[A-Z]{3}', c) or c in {'CAD', 'USD'} for c in codes):
        raise IngestionError('unexpected currency code')
    try:
        document = json.loads(payload)
        observations, details = document['observations'], document['seriesDetail']
    except (KeyError, TypeError, ValueError) as exc:
        raise IngestionError('invalid Valet response') from exc
    if not isinstance(observations, list) or not isinstance(details, dict):
        raise IngestionError('invalid Valet response structure')
    if any('FX' + code + 'CAD' not in details for code in codes):
        raise IngestionError('requested currency is absent from Valet metadata')
    rows = []
    seen = set()
    for record in observations:
        try:
            day = parse_date(record['d'], 'observation date')
            if day > cutoff:
                continue
            for code in codes:
                item = record.get('FX' + code + 'CAD')
                if item is None or item.get('v') in ('', None):
                    continue
                rate = float(item['v'])
                key = (code, day.isoformat())
                if key in seen or not math.isfinite(rate) or rate <= 0:
                    raise ValueError('duplicate or non-positive/non-finite FX rate')
                seen.add(key)
                rows.append((day.isoformat(), code, format(rate, '.12g'), fx_row(day).current, retrieved))
        except (KeyError, TypeError, ValueError) as exc:
            raise IngestionError(f'invalid Valet FX row: {exc}') from exc
    if not rows or any(not any(row[1] == code for row in rows) for code in codes):
        raise IngestionError('FX capture contains no data for at least one requested currency')
    rows.sort(key=lambda row: (row[1], row[0]))
    out = io.StringIO(newline='')
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(('date', 'currency', 'cad_per_unit', 'available_at', 'available_at_historical'))
    writer.writerows(rows)
    meta = {'schemaVersion': 1, 'rowCount': len(rows), 'firstDate': min(r[0] for r in rows),
            'lastDate': max(r[0] for r in rows), 'sha256': sha256_hex(out.getvalue().encode()),
            'availabilityPolicy': 'boc_2130_current_capture_historical',
            'checks': [{'name': 'Valet FX validated', 'ok': True,
                        'detail': 'Unique dated positive finite CAD-per-unit quotes; raw capture SHA-256 matched.',
                        'checkedAt': retrieved}],
            'details': {'sourceUrl': url, 'retrievedAt': retrieved, 'currencies': codes,
                        'historicalVintage': 'unknown; no rows visible before capture'}}
    return out.getvalue().encode(), meta


def publish_global_fx(data_root: Path, base_version: str, new_version: str, payload: bytes, metadata: dict) -> dict:
    """Publish a complete new snapshot; parent files and active pointer remain unchanged."""
    _check_version_label(new_version)
    data_root = Path(data_root)
    base = LocalDataStore(data_root).open(base_version)
    manifest = base.manifest
    normalized, fx_meta = normalize_capture(payload, metadata, base.data_as_of)
    target_manifest = data_root / 'manifests' / f'{new_version}.json'
    targets = [data_root / 'raw' / new_version, data_root / 'normalized' / new_version, target_manifest]
    expected = json.loads(target_manifest.read_text()) if target_manifest.exists() else None
    if any(path.exists() for path in targets[:2]):
        raise SnapshotIntegrityError(f'snapshot {new_version} already exists')
    staging = data_root / '.staging' / f'{new_version}.{secrets.token_hex(6)}'
    try:
        raw_dir, norm_dir = staging / 'raw', staging / 'normalized'
        raw_dir.mkdir(parents=True)
        norm_dir.mkdir()
        for source in manifest['sources']:
            blob = (data_root / source['path']).read_bytes()
            if canonical_sha256(blob) != source['sha256']:
                raise SnapshotIntegrityError(f"parent raw source {source['file']} hash mismatch")
            (raw_dir / source['file']).write_bytes(blob)
            source['path'] = f"raw/{new_version}/{source['file']}"
        for ds_id, meta in manifest['datasets'].items():
            blob = (data_root / meta['path']).read_bytes()
            if sha256_hex(blob) != meta['sha256']:
                raise SnapshotIntegrityError(f'parent dataset {ds_id} hash mismatch')
            (norm_dir / f'{ds_id}.csv').write_bytes(blob)
            meta['path'] = f'normalized/{new_version}/{ds_id}.csv'
        raw_name = 'boc_global_fx.json'
        (raw_dir / raw_name).write_bytes(payload)
        (norm_dir / 'fx_boc_global.csv').write_bytes(normalized)
        fx_meta['path'] = f'normalized/{new_version}/fx_boc_global.csv'
        manifest['datasets']['fx_boc_global'] = fx_meta
        manifest['sources'].append({'file': raw_name, 'path': f'raw/{new_version}/{raw_name}',
            'origin': metadata['sourceUrl'], 'sha256': canonical_sha256(payload),
            'sha256Bytes': sha256_hex(payload), 'bytes': len(payload)})
        manifest['parentVersion'] = base_version
        manifest['dataVersion'] = new_version
        manifest['createdAt'] = normalize_ts(metadata['retrievedAt'], 'retrievedAt')
        # Validate checksums and schema against the exact proposed bytes before publishing.
        from .snapshot import Snapshot
        Snapshot(manifest, {ds: (norm_dir / f'{ds}.csv').read_bytes() for ds in manifest['datasets']})
        if expected is not None and expected != manifest:
            raise SnapshotIntegrityError('Rebuilt global FX snapshot does not match the pinned manifest')
        for target in targets[:2]:
            target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(raw_dir, targets[0])
        os.replace(norm_dir, targets[1])
        target_manifest.parent.mkdir(parents=True, exist_ok=True)
        tmp = target_manifest.with_name('.' + target_manifest.name + '.' + secrets.token_hex(4) + '.tmp')
        tmp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        os.replace(tmp, target_manifest)
        LocalDataStore(data_root).open(new_version)
        return manifest
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def read_capture(path: Path) -> bytes:
    return gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()


def materialize_pinned_global_fx(data_root: Path, reference_data: Path, version: str) -> dict:
    """Reproduce a checked-in snapshot in a clean data root, without network or activation."""
    from .ingest import ingest_starter

    data_root, reference_data = Path(data_root), Path(reference_data)
    pinned = json.loads((reference_data / 'manifests' / f'{version}.json').read_text())
    parent = pinned['parentVersion']
    for label in (parent, version):
        expected = json.loads((reference_data / 'manifests' / f'{label}.json').read_text())
        path = data_root / 'manifests' / f'{label}.json'
        if path.exists():
            if json.loads(path.read_text()) != expected:
                raise SnapshotIntegrityError(f'{label}: existing manifest differs from the pinned reference')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(expected, indent=2) + '\n')
    ingest_starter(reference_data.parent / 'Datathon2026' / 'alphaforge_starter', data_root, parent,
                   metadata_dir=reference_data / 'inputs' / parent, activate=False)
    if (data_root / 'normalized' / version).exists():
        return LocalDataStore(data_root).open(version).manifest
    capture_date = pinned['datasets']['fx_boc_global']['details']['retrievedAt'][:10].replace('-', '')
    capture = reference_data / 'inputs' / 'global-fx'
    return publish_global_fx(data_root, parent, version, read_capture(capture / f'boc-{capture_date}.json.gz'),
                             json.loads((capture / f'boc-{capture_date}.metadata.json').read_text()))
