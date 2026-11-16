"""Shim of GET /v1/intelligence/source-capabilities: no research source family is available.

The Markets research panels and their /v1/intelligence/*, /v1/research/* and
/v1/timemachine/vintages/status routes were removed: they had no role in the persona decision
flow. The current Markets page (web/src/features/markets/MarketsPage.tsx) still reads this route
and shows a research panel only for a family reported 'available', so an empty inventory hides
every panel. Delete this module and its route once the web no longer calls it.
"""
from __future__ import annotations


def capabilities():
    # The note is the literal the web translates (SourceAvailability.tsx, web/tests/web-deferred.test.ts).
    return {'families': [], 'catalogue': {'rows': [], 'source_count': 0},
            'note': 'Available means a demonstrated workflow within its stated scope; it does not guarantee current provider uptime. Evidence-only captures are not live adapters.'}
