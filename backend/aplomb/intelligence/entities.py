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


RelationshipType = Literal[
    'SECURITY_ISSUED_BY', 'ENTITY_PARENT_OF', 'FACILITY_OPERATED_BY',
    'ENTITY_HEADQUARTERED_IN', 'COMPANY_REPORTS_REVENUE_IN', 'FACILITY_LOCATED_IN',
    'COMPANY_SUPPLIES_TO', 'SECURITY_HELD_BY_PORTFOLIO', 'EVENT_OCCURRED_AT',
    'EVENT_REFERENCES_ENTITY', 'CLAIM_SUPPORTED_BY_SOURCE',
    # Dated relationship graph (relationship_graph.py): GLEIF Level 2 and explicit derivations.
    'ENTITY_ULTIMATE_PARENT_OF', 'SECURITY_ISSUER_ULTIMATE_PARENT', 'PORTFOLIO_HOLDS_ISSUER_SECURITY',
    'FACT_SOURCED_FROM_DATASET',
]
# 'unverified' marks a documented link whose source check failed or was not run.
EvidenceClass = Literal['direct', 'derived', 'model_inferred', 'candidate', 'unverified']


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
