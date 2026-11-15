"""Issuer-published ETF holdings sources: rights review and the acquisition gate.

Issuer holdings files (iShares, Vanguard, State Street SPDR) are acquired only when the
issuer's own terms permit automated download, storage and display in this application.
Each source below records the official terms URL, when it was read, short quoted clauses
and the resulting decision. No acquisition adapter exists for a blocked issuer: there is
deliberately no download code in this module, so the gate cannot be bypassed by
configuration. A source moves to ``permitted`` only by a code change that cites written
permission or changed terms, followed by a separately reviewed adapter.

Rights-permitted fund holdings in this application come from SEC N-PORT public filings
(see ``fund_pipeline``), which are a different, delayed, regulatory source and are never
presented as issuer daily holdings.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

CHECKED_AT = '2026-11-15T17:01:39Z'

_TICKER = re.compile(r'^[A-Z][A-Z0-9.]{0,9}$')


@dataclass(frozen=True)
class Clause:
    label: str
    quote: str


@dataclass(frozen=True)
class RightsReview:
    issuer: str
    source_ids: tuple[str, ...]
    dataset: str
    dataset_url: str
    terms_url: str
    checked_at: str | None
    checked_in_this_review: bool
    terms_page_sha256: str | None
    status: str
    decision: str
    clauses: tuple[Clause, ...]
    unblock_requires: str
    limitations: tuple[str, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data['source_ids'] = list(self.source_ids)
        data['clauses'] = [asdict(c) for c in self.clauses]
        data['limitations'] = list(self.limitations)
        data['acquisition_adapter'] = None
        return data


REVIEWS: dict[str, RightsReview] = {
    'vanguard': RightsReview(
        issuer='Vanguard',
        source_ids=('SRC-055',),
        dataset='Vanguard ETF fund holdings / composition',
        dataset_url='https://investor.vanguard.com/investment-products/etfs',
        terms_url='https://investor.vanguard.com/terms-conditions',
        checked_at=CHECKED_AT,
        checked_in_this_review=True,
        terms_page_sha256='95fcdb332512cffcabb5f5f60793c3d7f97970c3b908eb7792b26ff632e7c8f2',
        status='blocked_by_terms',
        decision=('Terms limit use to personal, informational and noncommercial purposes, prohibit '
                  'repeated automated access and prohibit copying, distributing or displaying data. '
                  'No acquisition adapter is built.'),
        clauses=(
            Clause('Limited license',
                   'license to view, store, bookmark, download, and print the pages within this Site '
                   'solely for your personal, informational, and noncommercial use or as expressly '
                   'authorized by Vanguard in writing'),
            Clause('Restrictions on use',
                   'Modify, copy, screen capture, distribute, forward, transmit, post, display, perform, '
                   'reproduce, publish, broadcast, license, create derivative works from, transfer, sell, '
                   'or exploit any reports, data, information, content'),
            Clause('Automated access',
                   'using devices or software that provide repeated automated access to this Site, other '
                   'than those made generally available by Vanguard'),
        ),
        unblock_requires='Written authorization from Vanguard covering automated retrieval, storage and display.',
        limitations=('Specific holdings file URLs were not requested; only the terms page was read.',
                     'terms_page_sha256 is of the HTML as served at checked_at; the page can change.'),
    ),
    'spdr': RightsReview(
        issuer='State Street Investment Management (SPDR)',
        source_ids=('SRC-056', 'MASTER-026'),
        dataset='SPDR ETF daily holdings files',
        dataset_url='https://www.ssga.com/',
        terms_url='https://www.ssga.com/us/en/footer/terms-and-conditions',
        checked_at=CHECKED_AT,
        checked_in_this_review=True,
        terms_page_sha256='3e1ac3e060b9b6f53fb61c328ecda7914eb655a1bfc16ab3d213cc5a9ea6247f',
        status='blocked_by_terms',
        decision=('Terms permit only print-outs for personal use or a reasonable number of internal '
                  'copies, prohibit disseminating the information and prohibit redistributing data '
                  'transmitted from their databases. Storing and displaying captures to application '
                  'users is not covered. No acquisition adapter is built.'),
        clauses=(
            Clause('Copyright and copying',
                   'You may not copy, reproduce, duplicate, modify, adopt or lend, sell, disseminate or '
                   'otherwise transfer, in whole or in part, any of the information contained in this '
                   'Site, except for the purpose of accessing the Site and producing print-outs for your '
                   'own personal use, or making a reasonable number of copies of such pages for internal '
                   'use within your organization'),
            Clause('Redistribution of database information',
                   "allow or cause any information transmitted from State Street Investment Management's "
                   'databases, including data from third party sources, available through use of the Site '
                   'or the remote access services, to be published, redistributed or retransmitted'),
            Clause('Supplier licences',
                   'In no event may you use the data and information on the Site in lieu of obtaining '
                   'appropriate licenses from the applicable Supplier'),
        ),
        unblock_requires=('Written permission from State Street Investment Management (and any index '
                          'supplier licence it requires) covering automated retrieval, storage and display.'),
        limitations=('The U.S. intermediary, individual and institutional terms URLs all redirected to the '
                     'same /us/en/footer/terms-and-conditions page when checked.',
                     'Other regional SSGA sites publish different terms; only the U.S. page was read.',
                     'Specific daily holdings XLSX URLs were not requested; only the terms page was read.'),
    ),
    'ishares': RightsReview(
        issuer='BlackRock iShares',
        source_ids=('SRC-054', 'MASTER-025'),
        dataset='iShares ETF holdings files',
        dataset_url='https://www.ishares.com/',
        terms_url='https://www.blackrock.com/corporate/compliance/terms-and-conditions',
        checked_at=None,
        checked_in_this_review=False,
        terms_page_sha256=None,
        status='blocked_by_terms',
        decision=('Recorded earlier in docs/parallel/reports/agent-2/SOURCES.csv: BlackRock terms restrict '
                  'automated copying and redistribution without written permission. Not re-read here.'),
        clauses=(),
        unblock_requires='Written permission from BlackRock covering automated retrieval, storage and display.',
        limitations=('No clause text is reproduced because the terms were not re-read in this review.',),
    ),
}


class IssuerHoldingsBlocked(RuntimeError):
    def __init__(self, review: RightsReview):
        super().__init__(review.status)
        self.review = review


def rights_status() -> dict:
    return {
        'checked_at': CHECKED_AT,
        'issuers': [r.to_dict() for r in REVIEWS.values()],
        'permitted_alternative': {
            'source': 'SEC Form N-PORT public filings',
            'note': ('Regulatory portfolio reports with a reporting delay; a different source from issuer '
                     'daily holdings. Served by the N-PORT fund pipeline, not by this module.'),
        },
    }


def acquire(issuer: str, fund_ticker: str) -> dict:
    """Validate the request, then refuse unless the issuer's terms are recorded as permitted.

    No network request is ever sent from here. Fund tickers are validated for shape only;
    a ticker is not an identity and is never resolved to an ISIN in this module.
    """
    review = REVIEWS.get(issuer)
    if review is None:
        raise ValueError('unknown issuer')
    ticker = (fund_ticker or '').strip().upper()
    if not _TICKER.fullmatch(ticker):
        raise ValueError('invalid fund ticker')
    # Every issuer is currently blocked; even a status change alone would not acquire
    # anything, because no reviewed adapter exists in this module.
    raise IssuerHoldingsBlocked(review)


def blocked_response(exc: IssuerHoldingsBlocked, fund_ticker: str) -> dict:
    return {
        'status': exc.review.status,
        'requested_fund_ticker': (fund_ticker or '').strip().upper(),
        'network_request_sent': False,
        'holdings': None,
        'as_of': None,
        'review': exc.review.to_dict(),
    }
