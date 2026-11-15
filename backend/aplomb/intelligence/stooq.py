"""Stooq historical daily price files (SRC-018): access review and the acquisition gate.

Stooq's robots.txt disallows every user agent other than Googlebot and Bingbot, and every
page checked (including the CSV download endpoint and the terms page) answered with a
JavaScript proof-of-work browser-verification page instead of content. Solving that
challenge programmatically would circumvent a provider access control, and the terms
could not be read without doing so. No acquisition adapter is built and this module never
sends a network request. Requests are validated and answered with an explicit blocked state.
"""
from __future__ import annotations

import re
from datetime import date

CHECKED_AT = '2026-11-15T17:01:39Z'
MAX_RANGE_DAYS = 3660

# Stooq-style symbols such as ``aapl.us`` or ``^spx``; shape only, never an identity proof.
_SYMBOL = re.compile(r'^\^?[a-z0-9][a-z0-9_-]{0,15}(\.[a-z]{1,4})?$')

REVIEW = {
    'source_ids': ['SRC-018'],
    'provider': 'Stooq',
    'dataset': 'Historical daily price files',
    'dataset_url': 'https://stooq.com/db/h/',
    'catalogue_url': 'https://stooq.com/dbh/',
    'terms_url': 'https://stooq.com/terms.html',
    'checked_at': CHECKED_AT,
    'status': 'blocked_by_access_control',
    'terms_verified': False,
    'decision': ('robots.txt disallows automated agents and every endpoint checked returned a JavaScript '
                 'proof-of-work verification page. The challenge is an access control and is not solved '
                 'or bypassed. Terms could not be read. No acquisition adapter is built.'),
    'evidence': [
        {'url': 'https://stooq.com/robots.txt', 'http_status': 200,
         'sha256': 'b2f1e90e59d2e03ef256ecf56f0cdd50b00d53f46d7ac8cde7c505525ef15c45',
         'observed': 'User-agent: Bingbot Allow: / ; User-agent: Googlebot Allow: / ; User-agent: * Disallow: /'},
        {'url': 'https://stooq.com/q/d/l/?s=aapl.us&i=d', 'http_status': 200,
         'content_type': 'text/html; charset=utf-8',
         'observed': ('796-byte page: "This site requires JavaScript to verify your browser" with a SHA-256 '
                      'proof-of-work script posting to /__verify; no CSV returned.')},
        {'url': 'https://stooq.com/terms.html', 'http_status': 200,
         'observed': 'Same browser-verification page; terms text not retrievable without solving it.'},
        {'url': 'https://stooq.com/dbh/', 'http_status': 404,
         'observed': 'Catalogue URL listed in SOURCES-AGENT-2.md returned 404.'},
    ],
    'unblock_requires': ('Stooq terms read by a person in a browser and confirming automated download, storage '
                         'and display are permitted, plus an access method that does not require circumventing '
                         'the verification challenge (for example a published bulk file or written permission).'),
    'unverified': ['Secondary sources report an apikey parameter and a daily hit limit on /q/d/l/; '
                   'not verified here because the endpoint returned only the verification page.'],
    'acquisition_adapter': None,
}


class StooqBlocked(RuntimeError):
    pass


def validate_request(symbol: str, start: date, end: date) -> dict:
    sym = (symbol or '').strip().lower()
    if not _SYMBOL.fullmatch(sym):
        raise ValueError('invalid Stooq symbol')
    if start > end:
        raise ValueError('start after end')
    if (end - start).days > MAX_RANGE_DAYS:
        raise ValueError('date range too long')
    if end > date.today():
        raise ValueError('end date in the future')
    return {'symbol': sym, 'start': start.isoformat(), 'end': end.isoformat(), 'interval': 'd'}


def daily_prices(symbol: str, start: date, end: date) -> dict:
    """Validate a daily OHLCV request, then refuse: acquisition is blocked (see REVIEW)."""
    validate_request(symbol, start, end)
    raise StooqBlocked(REVIEW['status'])


def blocked_response(request: dict | None) -> dict:
    return {
        'status': REVIEW['status'],
        'request': request,
        'network_request_sent': False,
        'bars': None,
        'currency': None,
        'exchange': None,
        'adjustment': None,
        'available_at': None,
        'review': REVIEW,
    }
