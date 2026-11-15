"""Conservative identifier and source-backed relationship types.

A ticker is a listing attribute, not a globally unique security identifier. No names,
addresses or geographic proximity are used to establish identity or ownership.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, time, timezone
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)


def valid_isin(value: str) -> bool:
    """ISO 6166 check digit; validates syntax/checksum, not issuance or entitlement."""
    if not re.fullmatch(r'[A-Z]{2}[A-Z0-9]{9}[0-9]', value):
        return False
    digits = ''.join(str(ord(c) - 55) if c.isalpha() else c for c in value)
    total = sum((n * 2 - 9 if n * 2 > 9 else n * 2) if i % 2 else n
                for i, n in enumerate(map(int, reversed(digits))))
    return total % 10 == 0


def valid_lei(value: str) -> bool:
    """ISO 17442 structure and ISO 7064 MOD 97-10 check digits."""
    if not re.fullmatch(r'[A-Z0-9]{18}[0-9]{2}', value):
        return False
    number = ''.join(str(ord(c) - 55) if c.isalpha() else c for c in value)
    return int(number) % 97 == 1


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('timestamps must be timezone-aware')
    return value.astimezone(timezone.utc)


class Evidence(Model):
    source_id: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=1, max_length=2048)
    content_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    observed_at: datetime | None = None
    published_at: datetime | None = None
    available_at: datetime
    retrieved_at: datetime
    licence: str = Field(min_length=1, max_length=300)
    limitations: tuple[str, ...] = ()

    @field_validator('url')
    @classmethod
    def https_url(cls, value):
        u = urlsplit(value)
        if u.scheme != 'https' or not u.hostname or u.username or u.password:
            raise ValueError('evidence URL must be absolute HTTPS without credentials')
        return value

    @field_validator('observed_at', 'published_at', 'available_at', 'retrieved_at')
    @classmethod
    def aware(cls, value):
        return utc(value) if value else value

    @model_validator(mode='after')
    def chronology(self):
        if self.published_at and self.available_at < self.published_at:
            raise ValueError('availability cannot precede the documented publication')
        if self.available_at > self.retrieved_at:
            raise ValueError('availability cannot follow retrieval of this capture')
        return self

    def visible(self, as_of: date, *, historical: bool) -> bool:
        cutoff = datetime.combine(as_of, time.max, timezone.utc)
        # Retrieval is a conservative availability boundary for historical investigations.
        return self.available_at <= cutoff and (not historical or self.retrieved_at <= cutoff)


class Instrument(Model):
    ticker: str = Field(pattern=r'^[A-Z0-9][A-Z0-9.=_-]{0,39}$')
    exchange_mic: str = Field(pattern=r'^[A-Z0-9]{4}$')
    valid_from: date
    valid_to: date | None = None
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    isin: str | None = None
    name: str = Field(min_length=1, max_length=200)
    evidence: Evidence

    @field_validator('isin')
    @classmethod
    def check_isin(cls, value):
        if value is not None and not valid_isin(value):
            raise ValueError('invalid ISIN checksum')
        return value

    @model_validator(mode='after')
    def dates(self):
        if self.valid_to and self.valid_to < self.valid_from:
            raise ValueError('listing end precedes start')
        return self

    @property
    def listing_id(self) -> str:
        """Deterministic exchange/symbol/lifecycle ID; not a claim about the issuer."""
        token = f'{self.exchange_mic}|{self.ticker}|{self.valid_from.isoformat()}'
        return 'listing_' + hashlib.sha256(token.encode('utf-8')).hexdigest()[:24]


RelationshipType = Literal[
    'SECURITY_ISSUED_BY', 'ENTITY_PARENT_OF', 'FACILITY_OPERATED_BY',
    'ENTITY_HEADQUARTERED_IN', 'COMPANY_REPORTS_REVENUE_IN', 'FACILITY_LOCATED_IN',
    'COMPANY_SUPPLIES_TO', 'SECURITY_HELD_BY_PORTFOLIO', 'EVENT_OCCURRED_AT',
    'EVENT_REFERENCES_ENTITY', 'CLAIM_SUPPORTED_BY_SOURCE',
]
EvidenceClass = Literal['direct', 'derived', 'model_inferred', 'candidate']


class Relationship(Model):
    subject_id: str = Field(min_length=1, max_length=200)
    relation: RelationshipType
    object_id: str = Field(min_length=1, max_length=200)
    evidence_class: EvidenceClass
    valid_from: date
    valid_to: date | None = None
    evidence: Evidence
    derivation: str | None = Field(default=None, max_length=500)

    @model_validator(mode='after')
    def validate_relation(self):
        if self.valid_to and self.valid_to < self.valid_from:
            raise ValueError('relationship end precedes start')
        if self.evidence_class == 'derived' and not self.derivation:
            raise ValueError('derived relationships require an explicit rule')
        return self

    @property
    def relationship_id(self) -> str:
        token = '|'.join((self.subject_id, self.relation, self.object_id, str(self.valid_from),
                          self.evidence.source_id, self.evidence.content_sha256))
        return 'rel_' + hashlib.sha256(token.encode()).hexdigest()[:24]


class RelationshipStore:
    """Immutable, source-backed relations; caller stores serialized records in S3/DynamoDB.

    Status defaults to directly documented and explicitly derived relationships; candidate and
    model-inferred relationships are only exposed on request and never become proven edges.
    """
    def __init__(self, relationships: list[Relationship]):
        self._relations = tuple(relationships)
        ids = [r.relationship_id for r in self._relations]
        if len(ids) != len(set(ids)):
            raise ValueError('duplicate relationship provenance')

    def find(self, subject_id: str, as_of: date, *, historical: bool = False,
             include_unverified: bool = False) -> list[Relationship]:
        return [r for r in self._relations if r.subject_id == subject_id and r.valid_from <= as_of
                and (r.valid_to is None or as_of <= r.valid_to)
                and r.evidence.visible(as_of, historical=historical)
                and (include_unverified or r.evidence_class in ('direct', 'derived'))]
