"""Dated, source-backed relationship graph built only from captured evidence.

Edges carry an evidence class:
- ``direct``: the captured source states this exact link (GLEIF exact ISIN/LEI pair, a GLEIF
  Level 2 relationship record, a verified quote, a disclosed holding);
- ``derived``: a code rule composed direct/derived edges; the rule and the edge path are kept;
- ``model_inferred``: produced by a model; never shown unless explicitly requested;
- ``unverified``: documented but its source check failed or was not run (also legacy "candidate").

Every edge has a validity interval (``valid_from``/``valid_to``, ``None`` = not documented) and
an ``available_at`` time: the moment this system could first have known it. Queries honour
both. Names, tickers and geography never create an edge.
"""
from __future__ import annotations

import hashlib
import json
from collections import deque
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .entities import (
    EvidenceClass,
    Model,
    Relationship,
    RelationshipType,
    utc,
    valid_isin,
    valid_lei,
)

GraphClass = Literal['direct', 'derived', 'model_inferred', 'unverified']
NodeKind = Literal['security', 'entity', 'portfolio', 'claim', 'fact', 'source_document', 'dataset', 'listing']
Temporal = Literal['interval', 'point_observation']
CLASS_RANK = {'direct': 3, 'derived': 2, 'model_inferred': 1, 'unverified': 0}
DEFAULT_CLASSES = frozenset({'direct', 'derived'})


def graph_class(value: EvidenceClass) -> GraphClass:
    return 'unverified' if value == 'candidate' else value


def node_kind(node_id: str) -> NodeKind:
    prefix = node_id.split(':', 1)[0]
    kinds = {'lei': 'entity', 'claim': 'claim', 'fact': 'fact', 'document': 'source_document',
             'url': 'source_document', 'dataset': 'dataset'}
    if prefix == 'isin':
        return 'security'
    if node_id.startswith('listing_'):
        return 'listing'
    if prefix == 'portfolio':
        return 'portfolio'
    if prefix in kinds:
        return kinds[prefix]
    raise ValueError(f'unsupported node identifier: {node_id[:40]}')


def check_node_id(node_id: str) -> str:
    if not isinstance(node_id, str) or not 3 <= len(node_id) <= 200:
        raise ValueError('invalid node identifier')
    if node_id.startswith('isin:') and not valid_isin(node_id[5:]):
        raise ValueError('invalid ISIN node')
    if node_id.startswith('lei:') and not valid_lei(node_id[4:]):
        raise ValueError('invalid LEI node')
    node_kind(node_id)
    return node_id


def _end_of(day: date) -> datetime:
    return datetime.combine(day, time.max, timezone.utc)


def _dt(value) -> datetime:
    if isinstance(value, datetime):
        return utc(value)
    return utc(datetime.fromisoformat(str(value).replace('Z', '+00:00')))


class EdgeSource(Model):
    source_id: str = Field(min_length=1, max_length=120)
    url: str | None = Field(default=None, max_length=2048)
    content_sha256: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    licence: str = Field(min_length=1, max_length=300)
    retrieved_at: datetime
    published_at: datetime | None = None

    @field_validator('url')
    @classmethod
    def https(cls, value):
        if value is not None and not value.startswith('https://'):
            raise ValueError('source URL must be HTTPS')
        return value

    @field_validator('retrieved_at', 'published_at')
    @classmethod
    def aware(cls, value):
        return utc(value) if value else value


class Node(Model):
    id: str
    kind: NodeKind
    label: str | None = Field(default=None, max_length=300)
    attributes: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @field_validator('id')
    @classmethod
    def valid_id(cls, value):
        return check_node_id(value)


class Edge(Model):
    subject: str
    relation: RelationshipType
    object: str
    evidence_class: GraphClass
    valid_from: date | None = None
    valid_to: date | None = None
    temporal: Temporal = 'interval'
    available_at: datetime
    source: EdgeSource | None = None
    derivation: str | None = Field(default=None, max_length=500)
    path: tuple[str, ...] = ()
    qualifiers: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @field_validator('subject', 'object')
    @classmethod
    def valid_nodes(cls, value):
        return check_node_id(value)

    @field_validator('available_at')
    @classmethod
    def aware(cls, value):
        return utc(value)

    @model_validator(mode='after')
    def rules(self):
        if self.subject == self.object:
            raise ValueError('self edge')
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError('edge end precedes start')
        if self.evidence_class == 'derived':
            if not self.derivation or len(self.path) < 2:
                raise ValueError('derived edges need a rule and the input edge path')
        elif self.source is None:
            raise ValueError('non-derived edges need a captured source')
        if self.source and self.available_at < self.source.retrieved_at and self.source.published_at is None:
            raise ValueError('availability before retrieval needs a documented publication time')
        return self

    @property
    def edge_id(self) -> str:
        source = self.source
        token = '|'.join((self.subject, self.relation, self.object, str(self.valid_from), str(self.valid_to),
                          source.source_id if source else '', (source.content_sha256 or '') if source else '',
                          ','.join(self.path)))
        return 'edge_' + hashlib.sha256(token.encode()).hexdigest()[:24]

    def validity(self, as_of: date) -> Literal['valid', 'not_valid', 'unknown', 'observed']:
        if self.valid_from and as_of < self.valid_from:
            return 'not_valid'
        if self.valid_to and as_of > self.valid_to and self.temporal == 'interval':
            return 'not_valid'
        if self.temporal == 'point_observation':
            return 'observed' if self.valid_from else 'unknown'
        return 'valid' if self.valid_from else 'unknown'

    def wire(self, as_of: date | None = None) -> dict:
        data = self.model_dump(mode='json')
        data['id'] = self.edge_id
        if as_of is not None:
            data['validity_on_as_of'] = self.validity(as_of)
        return data


def _weakest(classes: list[GraphClass]) -> GraphClass:
    if all(c in ('direct', 'derived') for c in classes):
        return 'derived'
    return min(classes, key=CLASS_RANK.__getitem__)


class RelationshipGraph:
    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, Edge] = {}
        self.annotations: dict[str, list[dict]] = {}
        self.notes: list[str] = []

    # -- construction ---------------------------------------------------------------------
    def add_node(self, node_id: str, *, label: str | None = None, **attributes) -> Node:
        old = self.nodes.get(node_id)
        merged = {**(old.attributes if old else {}), **{k: v for k, v in attributes.items() if v is not None}}
        node = Node(id=node_id, kind=node_kind(node_id), label=label or (old.label if old else None),
                    attributes=merged)
        self.nodes[node_id] = node
        return node

    def add_edge(self, edge: Edge) -> str:
        for endpoint in (edge.subject, edge.object):
            if endpoint not in self.nodes:
                self.add_node(endpoint)
        self.edges.setdefault(edge.edge_id, edge)
        return edge.edge_id

    def annotate(self, node_id: str, note: dict) -> None:
        self.annotations.setdefault(node_id, []).append(note)

    def add_relationship(self, relation: Relationship) -> str:
        """Adopt an existing ``entities.Relationship`` record unchanged."""
        ev = relation.evidence
        return self.add_edge(Edge(
            subject=relation.subject_id, relation=relation.relation, object=relation.object_id,
            evidence_class=graph_class(relation.evidence_class), valid_from=relation.valid_from,
            valid_to=relation.valid_to, available_at=ev.available_at,
            source=EdgeSource(source_id=ev.source_id, url=ev.url, content_sha256=ev.content_sha256,
                              licence=ev.licence, retrieved_at=ev.retrieved_at, published_at=ev.published_at),
            derivation=relation.derivation if relation.evidence_class == 'derived' else None,
            qualifiers={'limitations': '; '.join(ev.limitations)[:500] or None}))

    def add_gleif_l2(self, capture: dict) -> list[str]:
        """Edges and exception annotations from a ``gleif_relations`` capture."""
        if capture.get('status') != 'captured':
            return []
        source = capture['source']
        retrieved, available = _dt(source['retrieved_at']), _dt(source['available_at'])
        subject = capture['entity']
        self.add_node('lei:' + subject['lei'], label=subject.get('legal_name'),
                      jurisdiction=subject.get('jurisdiction'), entity_status=subject.get('entity_status'),
                      registration_status=subject.get('registration_status'))
        added = []

        def edge(record: dict, kind: str) -> None:
            parent, child = 'lei:' + record['parent_lei'], 'lei:' + record['child_lei']
            for lei_id, info in ((parent, record.get('parent')), (child, record.get('child'))):
                if info:
                    self.add_node(lei_id, label=info.get('legal_name'), jurisdiction=info.get('jurisdiction'),
                                  entity_status=info.get('entity_status'))
            published = record.get('source_published_at')
            status = record.get('relationship_status')
            valid_to = record.get('period_end')
            added.append(self.add_edge(Edge(
                subject=parent, relation='ENTITY_PARENT_OF' if kind == 'direct' else 'ENTITY_ULTIMATE_PARENT_OF',
                object=child, evidence_class='direct',
                valid_from=date.fromisoformat(record['period_start']) if record.get('period_start') else None,
                valid_to=date.fromisoformat(valid_to) if valid_to else None,
                available_at=available,
                source=EdgeSource(source_id='entity_gleif_level2', url=record['source_url'],
                                  content_sha256=record['source_sha256'], licence=source['licence'],
                                  retrieved_at=retrieved, published_at=_dt(published) if published else None),
                qualifiers={'gleif_relationship_type': record['gleif_type'], 'relationship_status': status,
                            'gleif_record_id': record['record_id'][:200],
                            'registration_status': record.get('registration_status'),
                            'corroboration_level': record.get('corroboration_level'),
                            'inactive_without_end_date': status == 'INACTIVE' and not valid_to,
                            'basis': 'accounting consolidation (GLEIF Level 2)'})))

        for kind in ('direct', 'ultimate'):
            part = capture[f'{kind}_parent']
            if part['relationship']:
                edge({**part['relationship'], 'parent': part.get('parent')}, kind)
            elif part['exception']:
                self.annotate('lei:' + subject['lei'], {'type': 'reporting_exception', 'level': kind,
                              **{k: part['exception'].get(k) for k in ('category', 'reason', 'reference',
                                                                        'source_url', 'source_sha256')}})
            else:
                self.annotate('lei:' + subject['lei'], {'type': 'none_published', 'level': kind})
            for record in capture[f'{kind}_children']['items']:
                edge(record, kind)
        return added

    def add_holdings(self, snapshots) -> list[str]:
        """``overlap.HoldingsSnapshot`` → security HELD_BY portfolio, as point observations."""
        added = []
        for snap in snapshots:
            fund = 'portfolio:' + snap.fund_id
            self.add_node(fund, holdings_complete=snap.complete)
            ev = snap.evidence
            for holding in snap.holdings:
                added.append(self.add_edge(Edge(
                    subject=holding.security_id, relation='SECURITY_HELD_BY_PORTFOLIO', object=fund,
                    evidence_class='direct', valid_from=snap.effective_date, valid_to=snap.effective_date,
                    temporal='point_observation', available_at=ev.available_at,
                    source=EdgeSource(source_id=ev.source_id, url=ev.url, content_sha256=ev.content_sha256,
                                      licence=ev.licence, retrieved_at=ev.retrieved_at,
                                      published_at=ev.published_at),
                    qualifiers={'weight_pct_of_net_assets': holding.weight_pct,
                                'snapshot_complete': snap.complete,
                                'limitations': '; '.join(ev.limitations)[:500] or None})))
        return added

    def add_ledger(self, view, run_id: str, documents: dict | None = None) -> list[str]:
        """Claim→source (ledger evidence) and fact→dataset edges from a frozen ``LedgerView``."""
        if not isinstance(run_id, str) or not 1 <= len(run_id) <= 80 or ':' in run_id:
            raise ValueError('invalid run id')
        documents = documents or {}
        added = []
        for evidence in view.evidence.values():
            if not evidence.url.startswith('https://'):
                continue
            doc = documents.get(evidence.document_ref) if evidence.document_ref else None
            digest = doc.content_hash if doc is not None and doc.source_url == evidence.url else None
            target = 'document:' + digest if digest else 'url:' + hashlib.sha256(evidence.url.encode()).hexdigest()[:32]
            claim = f'claim:{run_id}:{evidence.id}'
            self.add_node(claim, label=evidence.claim.en[:300], evidence_tier=evidence.tier)
            self.add_node(target, label=evidence.title[:300], publisher=evidence.publisher[:120], url=evidence.url)
            retrieved = _dt(evidence.retrieved_at)
            published = _dt(evidence.published_at + 'T00:00:00Z') if evidence.published_at else None
            added.append(self.add_edge(Edge(
                subject=claim, relation='CLAIM_SUPPORTED_BY_SOURCE', object=target,
                evidence_class='direct' if evidence.verification.status == 'verified' else 'unverified',
                valid_from=published.date() if published else None, available_at=retrieved,
                source=EdgeSource(source_id='ledger_evidence', url=evidence.url, content_sha256=digest,
                                  licence=evidence.licence[:300], retrieved_at=retrieved,
                                  published_at=published if published and published <= retrieved else None),
                qualifiers={'verification': evidence.verification.status, 'run_id': run_id,
                            'quote_checked': any(c.ok for c in evidence.verification.checks)})))
        for fact in view.facts.values():
            for ref in fact.sources:
                if ref.source_url is not None and not ref.source_url.startswith('https://'):
                    continue
                retrieved = _end_of(date.fromisoformat(ref.retrieved_on))
                available = _dt(fact.available_at) if fact.available_at else retrieved
                fact_node = f'fact:{run_id}:{fact.id}'
                dataset = f'dataset:{ref.dataset_id}@{ref.data_version}'
                self.add_node(fact_node, label=fact.label.en[:300], metric=str(fact.metric))
                self.add_node(dataset, label=ref.source_name[:300], url=ref.source_url)
                added.append(self.add_edge(Edge(
                    subject=fact_node, relation='FACT_SOURCED_FROM_DATASET', object=dataset,
                    evidence_class='direct' if fact.verification.status == 'verified' else 'unverified',
                    valid_from=date.fromisoformat(fact.as_of), valid_to=date.fromisoformat(fact.as_of),
                    temporal='point_observation', available_at=max(available, retrieved),
                    source=EdgeSource(source_id='ledger_fact_source', url=ref.source_url,
                                      licence=ref.licence[:300], retrieved_at=retrieved),
                    qualifiers={'verification': fact.verification.status, 'run_id': run_id,
                                'rows_read': ref.rows_read})))
        return added

    # -- derivation -----------------------------------------------------------------------
    def derive(self) -> list[str]:
        """Compose explicit rules; each derived edge names its rule and input edge ids."""
        added = []
        by_relation: dict[str, list[tuple[str, Edge]]] = {}
        for edge_id, edge in list(self.edges.items()):
            by_relation.setdefault(edge.relation, []).append((edge_id, edge))
        ultimate = {}
        for edge_id, edge in by_relation.get('ENTITY_ULTIMATE_PARENT_OF', []):
            ultimate.setdefault(edge.object, []).append((edge_id, edge))
        issued = {}
        for edge_id, edge in by_relation.get('SECURITY_ISSUED_BY', []):
            issued.setdefault(edge.subject, []).append((edge_id, edge))
            for up_id, up in ultimate.get(edge.object, []):
                added.append(self._compose(
                    edge.subject, 'SECURITY_ISSUER_ULTIMATE_PARENT', up.subject, [(edge_id, edge), (up_id, up)],
                    'security issued by entity X, and X ultimately consolidated by Y (GLEIF Level 2)'))
        for edge_id, edge in by_relation.get('SECURITY_HELD_BY_PORTFOLIO', []):
            for issue_id, issue in issued.get(edge.subject, []):
                added.append(self._compose(
                    edge.object, 'PORTFOLIO_HOLDS_ISSUER_SECURITY', issue.object, [(edge_id, edge), (issue_id, issue)],
                    'portfolio disclosed holding of an exact ISIN, and that ISIN is issued by the entity',
                    temporal='point_observation'))
        return [a for a in added if a]

    def _compose(self, subject: str, relation: str, obj: str, inputs: list[tuple[str, Edge]], rule: str,
                 *, temporal: Temporal = 'interval') -> str | None:
        if subject == obj:
            return None
        edges = [e for _, e in inputs]
        starts = [e.valid_from for e in edges]
        ends = [e.valid_to for e in edges if e.valid_to]
        valid_from = max(starts) if all(starts) else None  # an unknown start keeps the composite unknown
        valid_to = min(ends) if ends else None
        if valid_from and valid_to and valid_to < valid_from:
            # Never stretch a link across dates its sources do not cover; say so instead.
            self.notes.append(f'{relation} {subject} -> {obj} not derived: input validity does not overlap '
                              f'(documented from {valid_from.isoformat()}, other input ends {valid_to.isoformat()}).')
            return None
        return self.add_edge(Edge(
            subject=subject, relation=relation, object=obj,
            evidence_class=_weakest([e.evidence_class for e in edges]),
            valid_from=valid_from, valid_to=valid_to, temporal=temporal,
            available_at=max(e.available_at for e in edges), derivation=rule,
            path=tuple(i for i, _ in inputs),
            qualifiers={'input_classes': ','.join(e.evidence_class for e in edges)}))

    # -- queries --------------------------------------------------------------------------
    def _visible(self, edge: Edge, as_of: date, knowledge: str, classes: frozenset[str]) -> str | None:
        """Why an edge is hidden at ``as_of``, or None when it is shown."""
        if edge.evidence_class not in classes:
            return 'excluded_class'
        if knowledge == 'as_of' and edge.available_at > _end_of(as_of):
            return 'not_yet_available'
        if edge.validity(as_of) == 'not_valid':
            return 'outside_validity'
        return None

    def _scan(self, node_id: str, as_of: date, knowledge: str, classes: frozenset[str]):
        if knowledge not in ('as_of', 'latest'):
            raise ValueError('knowledge must be as_of or latest')
        for edge_id, edge in self.edges.items():
            if node_id in (edge.subject, edge.object):
                yield edge_id, edge, self._visible(edge, as_of, knowledge, classes)

    def neighbors(self, node_id: str, as_of: date, *, knowledge: Literal['as_of', 'latest'] = 'as_of',
                  classes: frozenset[str] = DEFAULT_CLASSES) -> tuple[list[dict], dict[str, int]]:
        """Edges touching ``node_id`` shown at ``as_of``, plus counts of hidden edges by reason."""
        shown, hidden = [], {}
        for _, edge, reason in self._scan(node_id, as_of, knowledge, classes):
            if reason:
                hidden[reason] = hidden.get(reason, 0) + 1
                continue
            shown.append({**edge.wire(as_of),
                          'direction': 'outgoing' if edge.subject == node_id else 'incoming'})
        return shown, hidden

    def view(self, root: str, as_of: date, *, depth: int = 2, knowledge: Literal['as_of', 'latest'] = 'as_of',
             classes: frozenset[str] = DEFAULT_CLASSES, max_edges: int = 1000) -> dict:
        """Breadth-first neighbourhood of ``root`` with counts of what was hidden and why."""
        if type(depth) is not int or not 1 <= depth <= 4:
            raise ValueError('depth must be between 1 and 4')
        seen_nodes, edges, hidden_ids = {root}, {}, {}
        queue = deque([(root, 0)])
        while queue:
            node, level = queue.popleft()
            if level >= depth:
                continue
            for edge_id, edge, reason in self._scan(node, as_of, knowledge, classes):
                if edge_id in edges:
                    continue
                if reason or len(edges) >= max_edges:
                    hidden_ids[edge_id] = reason or 'edge_limit'
                    continue
                edges[edge_id] = edge.wire(as_of)
                other = edge.object if edge.subject == node else edge.subject
                if other not in seen_nodes:
                    seen_nodes.add(other)
                    queue.append((other, level + 1))
        hidden: dict[str, int] = {}
        for reason in hidden_ids.values():
            hidden[reason] = hidden.get(reason, 0) + 1
        nodes = [{**self.nodes[n].model_dump(mode='json'), 'annotations': self.annotations.get(n, [])}
                 for n in sorted(seen_nodes) if n in self.nodes]
        return {'root': root, 'as_of': as_of.isoformat(), 'knowledge': knowledge, 'depth': depth,
                'classes': sorted(classes), 'nodes': nodes, 'edges': list(edges.values()),
                'hidden': hidden, 'derivation_notes': list(self.notes)}


def captured_holdings_snapshots() -> list:
    """The repository's captured, source-indexed partial N-PORT observation (see disclosure_examples)."""
    from .entities import Evidence
    from .overlap import Holding, HoldingsSnapshot

    path = Path(__file__).resolve().parent / 'data/sec-nport-aapu-indexed-excerpt.json'
    raw = path.read_bytes()
    transcript = json.loads(raw)
    stamp = _dt(transcript['retrieved_at'])
    evidence = Evidence(source_id='fund_sec_nport_indexed_excerpt', url=transcript['source_url'],
                        content_sha256=hashlib.sha256(raw).hexdigest(), available_at=stamp, retrieved_at=stamp,
                        licence='SEC filing; indexed transcript', limitations=tuple(transcript['limitations']))
    return [HoldingsSnapshot(
        fund_id='isin:' + transcript['fund_isin'], effective_date=date.fromisoformat(transcript['effective_date']),
        holdings=(Holding(security_id='isin:' + transcript['constituent_isin'],
                          weight_pct=float(transcript['constituent_long_equity_net_asset_pct'])),),
        evidence=evidence, complete=False)]


def relationship_view(store, session_id: str, *, lei: str | None = None, isin: str | None = None,
                      as_of: date | None = None, knowledge: Literal['as_of', 'latest'] = 'as_of',
                      include_unverified: bool = False, max_pages: int = 1, l2_fetch=None,
                      pair_fetch=None, now=None) -> dict:
    """Resolve an exact ISIN and/or LEI, capture GLEIF evidence and return the dated graph view.

    An ISIN alone yields GLEIF *candidate* LEIs; only an exact-pair page inspection turns one into
    a SECURITY_ISSUED_BY edge. A failed or incomplete check leaves the issuer unresolved.
    """
    from .exact import capture_pair, captured_pairs_as_of
    from .gleif import GLEIFError, _fetch
    from .gleif_relations import capture_l2, captured_l2_as_of, fetch_status, isin_candidates

    l2_fetch = l2_fetch or fetch_status
    pair_fetch = pair_fetch or _fetch
    lei = lei.strip().upper() if lei else None
    isin = isin.strip().upper() if isin else None
    if not lei and not isin:
        raise ValueError('Provide an exact LEI or ISIN')
    if lei and not valid_lei(lei):
        raise ValueError('A valid LEI checksum is required')
    if isin and not valid_isin(isin):
        raise ValueError('A valid ISIN checksum is required')
    stamp = now or datetime.now(timezone.utc)
    as_of = as_of or stamp.astimezone(timezone.utc).date()
    historical = knowledge == 'as_of' and as_of < stamp.astimezone(timezone.utc).date()
    graph = RelationshipGraph()
    resolution = None
    issuers: list[str] = []
    if isin:
        graph.add_node('isin:' + isin)
        candidate_error = None
        checks = []
        if historical:
            try:
                pairs = captured_pairs_as_of(store, session_id, isin, as_of, lei=lei)
            except GLEIFError as exc:
                pairs, candidate_error = [], str(exc)[:80]
            candidates, candidate_capture = [p.object_id.removeprefix('lei:') for p in pairs], None
            for pair in pairs[:3]:
                candidate = pair.object_id.removeprefix('lei:')
                checks.append({'lei': candidate, 'status': 'verified_pair', 'pages_inspected': None})
                graph.add_relationship(pair)
                issuers.append(candidate)
        else:
            try:
                candidates, candidate_capture = ([lei], None) if lei else isin_candidates(isin, fetch=l2_fetch)[:2]
            except GLEIFError as exc:
                candidates, candidate_capture, candidate_error = [], None, str(exc)[:80]
            for candidate in candidates[:3]:
                try:
                    result = capture_pair(store, session_id, isin, candidate, fetch=pair_fetch)
                except GLEIFError as exc:
                    checks.append({'lei': candidate, 'status': 'source_unavailable', 'detail': str(exc)[:80]})
                    continue
                checks.append({'lei': candidate, 'status': result['status'],
                               'pages_inspected': result.get('pages_inspected')})
                if result['status'] == 'verified_pair':
                    graph.add_relationship(Relationship.model_validate(result['relationship']))
                    issuers.append(candidate)
        candidate_source = ('captured same-session pairs available by cutoff' if historical else
                            'provided LEI' if lei else 'GLEIF filter[isin] (candidates only)')
        resolution = {'isin': isin, 'candidate_source': candidate_source,
                      'candidate_capture': candidate_capture, 'checks': checks,
                      'status': 'verified' if issuers else ('source_unavailable' if candidate_error else
                                                            'no_candidates' if not candidates else 'unverified'),
                      'verified_issuer_leis': issuers}
    entity_leis = list(dict.fromkeys(([lei] if lei else []) + issuers))
    l2 = {}
    for entity in entity_leis[:2]:
        try:
            capture = (captured_l2_as_of(store, session_id, entity, as_of) if historical else
                       capture_l2(store, session_id, entity, fetch=l2_fetch, max_pages=max_pages, now=now))
            if capture is None:
                capture = {'status': 'not_available_at_cutoff', 'lei': entity, 'source': None,
                           'limitations': ['No same-session Level 2 capture was available by the requested cutoff.']}
        except GLEIFError as exc:
            # Keep verified issuer evidence; show the Level 2 gap explicitly.
            capture = {'status': 'source_unavailable', 'lei': entity, 'source': None,
                       'limitations': [f'GLEIF Level 2 unavailable ({str(exc)[:60]}); no parent/child edges shown.']}
        graph.add_gleif_l2(capture)
        l2[entity] = capture
        # A separately acquired exact-LEI Golden Copy record can enrich the node,
        # but it cannot create a security-to-issuer edge or backdate its capture.
        from .golden_copy import GoldenCopyError, latest_entity
        try:
            golden = latest_entity(store, session_id, entity, None if knowledge == 'latest' else as_of)
        except GoldenCopyError:
            golden = None
            graph.notes.append('Stored Golden Copy entity capture failed integrity verification.')
        if golden:
            record = golden['entity']
            graph.add_node('lei:' + entity, label=record['legal_name'],
                           golden_jurisdiction=record['jurisdiction'],
                           golden_entity_status=record['entity_status'])
            graph.annotate('lei:' + entity, {'kind': 'golden_copy_entity', 'source': golden['source'],
                                             'dataset_version': golden['dataset_version']})
    if isin:
        graph.add_holdings([s for s in captured_holdings_snapshots()
                            if s.fund_id == 'isin:' + isin or any(h.security_id == 'isin:' + isin for h in s.holdings)])
    graph.derive()
    classes = frozenset(CLASS_RANK) if include_unverified else DEFAULT_CLASSES
    root = 'isin:' + isin if isin else 'lei:' + lei
    view = graph.view(root, as_of, depth=3 if isin else 2, knowledge=knowledge, classes=classes)
    limitations = [
        'Edges come only from captured sources; absence of an edge is not evidence of no relationship.',
        'Availability is the capture time unless the source documents an earlier publication.',
        'Facility, revenue-geography and supply-chain edges are only added when directly documented; none are inferred here.',
    ]
    if knowledge == 'latest':
        limitations.append('Knowledge mode "latest" shows what is known now, including facts not available on the as-of date.')
    return {'query': {'lei': lei, 'isin': isin, 'as_of': as_of.isoformat(), 'knowledge': knowledge,
                      'include_unverified': include_unverified},
            'issuer_resolution': resolution,
            'corporate_tree': {k: _tree_summary(v) for k, v in l2.items()},
            **view, 'limitations': limitations}


def _tree_summary(capture: dict) -> dict:
    """Compact, UI-ready Level 2 summary (the full graph is in nodes/edges)."""
    if capture.get('status') != 'captured':
        return {'status': capture.get('status'), 'lei': capture.get('lei'), 'source': capture.get('source'),
                'limitations': capture.get('limitations', [])}

    def parent(part: dict) -> dict:
        rel = part['relationship']
        return {'state': part['state'], 'exception': part['exception'],
                'relationship': None if not rel else {
                    k: rel.get(k) for k in ('parent_lei', 'relationship_status', 'period_start', 'period_end',
                                            'corroboration_level', 'registration_status', 'source_url',
                                            'source_sha256')},
                'parent': part.get('parent')}

    def children(group: dict) -> dict:
        return {'total_reported_by_source': group['total_reported_by_source'], 'truncated': group['truncated'],
                'pages_inspected': group['pages_inspected'],
                'items': [{'lei': r['child_lei'], 'legal_name': (r.get('child') or {}).get('legal_name'),
                           'jurisdiction': (r.get('child') or {}).get('jurisdiction'),
                           'relationship_status': r.get('relationship_status'),
                           'period_start': r.get('period_start'), 'period_end': r.get('period_end'),
                           'source_url': r.get('source_url'), 'source_sha256': r.get('source_sha256')}
                          for r in group['items']]}

    return {'status': 'captured', 'entity': capture['entity'],
            'direct_parent': parent(capture['direct_parent']),
            'ultimate_parent': parent(capture['ultimate_parent']),
            'direct_children': children(capture['direct_children']),
            'ultimate_children': children(capture['ultimate_children']),
            'rejected_rows': capture.get('rejected_rows', 0), 'reused_capture': capture.get('reused_capture'),
            'source': capture['source'], 'limitations': capture.get('limitations', [])}
