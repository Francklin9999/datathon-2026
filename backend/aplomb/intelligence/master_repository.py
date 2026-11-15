"""Versioned, session-owned listing records, published only by trusted source adapters.

This module exposes no user-supplied listing mutation endpoint. An adapter must validate
source-specific identity fields and rights before calling publish; matching bytes alone do
not prove that a document supports a listing assertion.
"""
from __future__ import annotations

import base64
import copy
import hashlib
from datetime import date, datetime

from aplomb.api.errors import Conflict
from aplomb.api.storage import Write, canonical

from .entities import Evidence, valid_isin
from .master import (
    IdentifierAssertion,
    InstrumentMaster,
    ListingRecord,
    captured_master,
    listing_wire,
    route_hint,
)

MAX_RECORD_BYTES = 250_000
MAX_ASSERTIONS_PER_PUBLISH = 200
MAX_ROWS = 5000


class InstrumentRepository:
    def __init__(self, store, session_id: str):
        if not session_id:
            raise ValueError('session required')
        self.store, self.session_id = store, session_id
        self.owner = hashlib.sha256(session_id.encode()).hexdigest()
        self.partition = 'INSTRUMENT#' + self.owner
        self.identifier_partition = 'IDENTIFIER#' + self.owner

    def publish(self, record: ListingRecord, *, source_bytes: dict[str, bytes], rights_confirmed: bool):
        """Store immutable evidence and normalized listing in one atomic record.

        Only trusted, source-specific acquisition code may call this method, after checking
        the claimed identity, licensed use and each URL. It rejects missing/mismatched bytes;
        it cannot independently prove semantic identity or rights from caller assertions.
        """
        if rights_confirmed is not True:
            raise ValueError('source reuse rights must be confirmed by adapter')
        if not isinstance(record, ListingRecord):
            raise TypeError('validated ListingRecord required')
        hashes = {e.content_sha256 for e in record.evidence}
        if set(source_bytes) != hashes:
            raise ValueError('evidence bytes must exactly cover source hashes')
        if any(not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != digest
               for digest, raw in source_bytes.items()):
            raise ValueError('source hash mismatch')
        raw = {digest: base64.b64encode(source_bytes[digest]).decode('ascii') for digest in sorted(hashes)}
        value = {'revision': 1, 'sessionId': self.session_id, 'listing': record.model_dump(mode='json'),
                 'sourceBytesBase64': raw, 'rightsConfirmed': True}
        serialized = canonical(value)
        if len(serialized) > MAX_RECORD_BYTES:
            raise ValueError('listing record exceeds storage bound')
        key = 'VERSION#' + record.listing_id + '#' + hashlib.sha256(serialized).hexdigest()
        try:
            self.store.transact([Write('cache', self.partition, key, value, None)])
        except Conflict:
            old = self.store.get('cache', self.partition, key)
            if old != value:
                raise ValueError('listing version integrity mismatch') from None
        return record.listing_id

    def snapshot(self, as_of: date):
        """Newest available version per lifecycle; earlier versions remain queryable at prior cutoffs."""
        versions = {}
        rows = self.store.query('cache', self.partition)
        if len(rows) > MAX_ROWS:
            raise ValueError('listing repository exceeds bound')
        for raw in rows:
            if raw.get('sessionId') != self.session_id or raw.get('rightsConfirmed') is not True:
                raise ValueError('listing owner or rights invalid')
            record = ListingRecord.model_validate(raw['listing'])
            encoded = raw.get('sourceBytesBase64', {})
            try:
                stored = {k: base64.b64decode(v, validate=True) for k, v in encoded.items()}
            except (ValueError, TypeError) as exc:
                raise ValueError('invalid stored source bytes') from exc
            if set(stored) != {e.content_sha256 for e in record.evidence} or any(
                hashlib.sha256(v).hexdigest() != k for k, v in stored.items()
            ):
                raise ValueError('stored source hash mismatch')
            if not record.visible(as_of):
                continue
            observed = max(e.retrieved_at for e in record.evidence)
            rank = (observed, hashlib.sha256(canonical(raw['listing'])).hexdigest())
            existing = versions.get(record.listing_id)
            if existing is None or rank > existing[0]:
                versions[record.listing_id] = (rank, record)
        # Baseline examples remain available even when a session has no acquisitions.
        # Caller-sourced versions override baseline IDs, and carry their own date/evidence.
        baseline = {r.listing_id: r for r in captured_master().listings if r.visible(as_of)}
        baseline.update({key: pair[1] for key, pair in versions.items()})
        return InstrumentMaster(list(baseline.values()))

    def publish_assertions(self, assertions: list[IdentifierAssertion], *, source_bytes: bytes,
                           rights_confirmed: bool):
        """Store identifier assertions from ONE captured source payload, with that payload.

        Every assertion must cite the hash of ``source_bytes``. Evidence classes are stored as
        supplied by the adapter and never upgraded here.
        """
        if rights_confirmed is not True:
            raise ValueError('source reuse rights must be confirmed by adapter')
        if not isinstance(source_bytes, bytes):
            raise TypeError('raw source bytes required')
        if not assertions:
            return []
        if len(assertions) > MAX_ASSERTIONS_PER_PUBLISH:
            raise ValueError('too many assertions for one source capture')
        digest = hashlib.sha256(source_bytes).hexdigest()
        if any(not isinstance(a, IdentifierAssertion) or a.evidence.content_sha256 != digest for a in assertions):
            raise ValueError('every assertion must cite the captured source hash')
        raw_key = 'SOURCE#' + digest
        raw_value = {'revision': 1, 'sessionId': self.session_id, 'kind': 'source',
                     'sourceBytesBase64': base64.b64encode(source_bytes).decode('ascii')}
        if len(canonical(raw_value)) > 4 * MAX_RECORD_BYTES:
            raise ValueError('source capture exceeds storage bound')
        self._put_once(self.identifier_partition, raw_key, raw_value)
        ids = []
        for item in assertions:
            value = {'revision': 1, 'sessionId': self.session_id, 'kind': 'assertion',
                     'assertion': item.model_dump(mode='json'), 'sourceKey': raw_key}
            self._put_once(self.identifier_partition, 'ASSERTION#' + item.assertion_id, value)
            ids.append(item.assertion_id)
        return ids

    def _put_once(self, pk, sk, value):
        try:
            self.store.transact([Write('cache', pk, sk, value, None)])
        except Conflict:
            old = self.store.get('cache', pk, sk)
            if old == value:
                return
            # The same source bytes can be fetched again later. Preserve the first
            # immutable capture time; no other assertion fields may change.
            if old and old.get('kind') == value.get('kind') == 'assertion':
                before, after = copy.deepcopy(old), copy.deepcopy(value)
                for item in (before, after):
                    evidence = item['assertion']['evidence']
                    evidence.pop('retrieved_at', None)
                    evidence.pop('available_at', None)
                if before == after:
                    return
            raise ValueError('immutable record integrity mismatch') from None

    def published_assertions(self, ids: list[str]) -> list[IdentifierAssertion]:
        """Return original, owned immutable assertions after idempotent registration."""
        result = []
        for assertion_id in ids:
            record = self.store.get('cache', self.identifier_partition, 'ASSERTION#' + assertion_id)
            if not record or record.get('sessionId') != self.session_id or record.get('kind') != 'assertion':
                raise ValueError('published assertion missing or foreign')
            item = IdentifierAssertion.model_validate(record['assertion'])
            if item.assertion_id != assertion_id:
                raise ValueError('published assertion integrity mismatch')
            result.append(item)
        return result

    def assertions(self, subject: str, as_of: date):
        """Assertions about ``subject`` whose capture was available by the cutoff."""
        rows = self.store.query('cache', self.identifier_partition)
        if len(rows) > MAX_ROWS:
            raise ValueError('identifier repository exceeds bound')
        sources = {}
        for raw in rows:
            if raw.get('sessionId') != self.session_id:
                raise ValueError('identifier record owner invalid')
            if raw.get('kind') == 'source':
                data = base64.b64decode(raw['sourceBytesBase64'], validate=True)
                sources['SOURCE#' + hashlib.sha256(data).hexdigest()] = True
        out = []
        for raw in rows:
            if raw.get('kind') != 'assertion':
                continue
            item = IdentifierAssertion.model_validate(raw['assertion'])
            if raw.get('sourceKey') != 'SOURCE#' + item.evidence.content_sha256 or raw['sourceKey'] not in sources:
                raise ValueError('assertion source capture missing or mismatched')
            if item.subject == subject and item.evidence.visible(as_of, historical=True):
                out.append(item)
        return sorted(out, key=lambda a: (a.scheme, a.value, a.origin, a.evidence.retrieved_at))


def _evidence_wire(e: Evidence):
    return {'source_id': e.source_id, 'url': e.url, 'content_sha256': e.content_sha256,
            'available_at': e.available_at.isoformat(), 'retrieved_at': e.retrieved_at.isoformat(),
            'published_at': e.published_at.isoformat() if e.published_at else None,
            'licence': e.licence, 'limitations': list(e.limitations)}


def _session_captures(store, session_id: str, prefix: str):
    owner = hashlib.sha256(session_id.encode()).hexdigest()
    rows = store.query('cache', prefix + owner)
    if len(rows) > MAX_ROWS:
        raise ValueError('capture partition exceeds bound')
    return [r for r in rows if r.get('sessionId') == session_id]


def crosswalk(store, session_id: str, isin: str, as_of: date):
    """Every identifier recorded for an exact ISIN, each with its own source, class and hash.

    Sources: published listing records (including the captured baseline example), identifier
    assertions from trusted adapters, exact GLEIF pairs captured in this session, and Wikidata
    ISIN candidate captures in this session. Corroboration is reported, never used to upgrade
    an unverified assertion's evidence class.
    """
    if not isinstance(isin, str) or not valid_isin(isin):
        raise ValueError('Valid exact ISIN with checksum required')
    repo = InstrumentRepository(store, session_id)
    listings = repo.snapshot(as_of).discover(as_of=as_of, isin=isin)
    rows = []

    def add(scheme, value, role, evidence_class, origin, evidence, *, stated_from=None, stated_to=None,
            derivation=None, listing_id=None):
        rows.append({'scheme': scheme, 'value': value, 'role': role, 'evidence_class': evidence_class,
                     'origin': origin, 'stated_from': stated_from, 'stated_to': stated_to,
                     'derivation': derivation, 'listing_id': listing_id,
                     'sources': [_evidence_wire(e) for e in evidence]})

    for item in listings:
        ev = item.evidence
        add('isin', item.isin, 'security', 'direct', 'listing_record', ev, listing_id=item.listing_id)
        if item.mic:
            add('mic_ticker', f'{item.mic}:{item.ticker}', 'listing', 'direct', 'listing_record', ev,
                stated_from=item.valid_from and item.valid_from.isoformat(),
                stated_to=item.valid_to and item.valid_to.isoformat(), listing_id=item.listing_id)
        if item.provider:
            add('provider_asset_id', f'{item.provider}:{item.provider_asset_id}', 'provider_asset', 'direct',
                'listing_record', ev, listing_id=item.listing_id)
        if item.series_lei:
            add('lei', item.series_lei, 'fund_series_lei', 'direct', 'listing_record', ev, listing_id=item.listing_id)
        if item.registrant_cik:
            add('cik', item.registrant_cik, 'registrant_cik', 'direct', 'listing_record', ev,
                listing_id=item.listing_id)
        add('listing_id', item.listing_id, 'listing', 'derived', 'aplomb_master', ev, listing_id=item.listing_id,
            derivation='sha256(MIC|ticker|lifecycle anchor) or sha256(provider|asset id|anchor), first 24 hex')

    for a in repo.assertions('isin:' + isin, as_of):
        add(a.scheme, a.value, a.role, a.evidence_class, a.origin, (a.evidence,),
            stated_from=a.stated_from and a.stated_from.isoformat(),
            stated_to=a.stated_to and a.stated_to.isoformat(), derivation=a.derivation)

    # Captures made through the standalone GLEIF pair and Wikidata candidate endpoints.
    for raw in _session_captures(store, session_id, 'ENTITY_PAIR#'):
        rel = raw.get('relationship') or {}
        if rel.get('subject_id') != 'isin:' + isin or not str(rel.get('object_id', '')).startswith('lei:'):
            continue
        ev = Evidence.model_validate(rel['evidence'])
        if hashlib.sha256(raw['raw'].encode('utf-8')).hexdigest() != ev.content_sha256:
            raise ValueError('stored GLEIF capture hash mismatch')
        if ev.visible(as_of, historical=True):
            add('lei', rel['object_id'][4:], 'issuer_lei', 'direct', 'gleif_exact_pair', (ev,))
    for raw in _session_captures(store, session_id, 'WIKIDATA#'):
        result = raw.get('result') or {}
        if result.get('isin') != isin:
            continue
        if hashlib.sha256(raw['raw'].encode('utf-8')).hexdigest() != result.get('source_sha256'):
            raise ValueError('stored Wikidata capture hash mismatch')
        stamp = datetime.fromisoformat(result['retrieved_at'])
        ev = Evidence(source_id='wikidata_sparql_isin', url=result['source_url'],
                      content_sha256=result['source_sha256'], available_at=stamp, retrieved_at=stamp,
                      licence=result['licence'], limitations=tuple(result.get('limitations', ())))
        if ev.visible(as_of, historical=True):
            for cand in result.get('items', []):
                add('wikidata_qid', cand['item_id'], 'community_item', 'unverified', 'wikidata_isin_candidate', (ev,))

    # Merge identical (scheme, value, role, class, origin) rows and their sources.
    merged = {}
    for row in rows:
        key = (row['scheme'], row['value'], row['role'], row['evidence_class'], row['origin'],
               row['stated_from'], row['stated_to'], row['listing_id'])
        if key in merged:
            seen = {s['content_sha256'] for s in merged[key]['sources']}
            merged[key]['sources'] += [s for s in row['sources'] if s['content_sha256'] not in seen]
        else:
            merged[key] = row
    rows = list(merged.values())
    strong = {}
    for row in rows:
        if row['evidence_class'] in ('direct', 'derived'):
            strong.setdefault((row['scheme'], row['value']), []).append(row['origin'])
    for row in rows:
        row['corroborated_by'] = (sorted(set(strong.get((row['scheme'], row['value']), [])))
                                  if row['evidence_class'] == 'unverified' else [])
        row['identity_use'] = ('identity_evidence' if row['evidence_class'] == 'direct'
                               else 'computed' if row['evidence_class'] == 'derived'
                               else 'lead_only')
    order = {'direct': 0, 'derived': 1, 'unverified': 2}
    rows.sort(key=lambda r: (order[r['evidence_class']], r['scheme'], r['value']))

    mics = {}
    for item in listings:
        if item.mic:
            mics.setdefault(item.mic, {'basis': 'listing_record', **route_hint(item.mic, asset_class=item.asset_class)})
    for row in rows:
        if row['scheme'] == 'mic_ticker' and row['evidence_class'] == 'unverified':
            mic = row['value'].split(':', 1)[0]
            mics.setdefault(mic, {'basis': 'unverified_candidate', **route_hint(mic)})
    return {'isin': isin, 'as_of': as_of.isoformat(), 'identifiers': rows,
            'listings': [listing_wire(item) for item in listings],
            'routing': sorted(mics.values(), key=lambda r: (r['basis'], r['mic'])),
            'counts': {k: sum(r['evidence_class'] == k for r in rows) for k in order},
            'limitations': [
                'Only identifiers recorded in this session or the captured baseline are shown; absence is not proof.',
                'Unverified community assertions are leads; corroboration does not change their class.',
                'Listing-record identifiers cite all record evidence; per-field attribution is not stored.',
                'Routing is a code-owned table per MIC; each adapter still needs its exact provider identifier.']}
