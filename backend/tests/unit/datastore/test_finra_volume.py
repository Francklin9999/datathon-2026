"""Synthetic sample; FINRA source-use and redistribution terms remain to be cleared."""
import hashlib
from decimal import Decimal

import pytest
from aplomb.datastore.errors import IngestionError
from aplomb.datastore.finra_volume import read_capture


def metadata(raw):
    return {'rawSha256': hashlib.sha256(raw).hexdigest(),
            'sourceUrl': 'https://cdn.finra.org/equity/regsho/daily/CNMSshvol20261112.txt',
            'retrievedAt': '2026-11-15T16:00:00Z'}


def test_fractional_shares_and_short_exempt_subset():
    raw = (b'Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market\n'
           b'20261112|ABC|70.5|30|90|B,Q,N\n1\n')
    capture = read_capture(raw, metadata(raw))
    assert capture.find('ABC', '2026-11-12T23:59:59Z') is None
    row = capture.find('ABC', capture.retrieved_at)
    assert row.short == Decimal('70.5')
    assert row.short_exempt == Decimal('30')


def test_trailer_and_invalid_exempt_are_rejected():
    for line in (b'20261112|ABC|2|3|5|Q\n1\n', b'20261112|ABC|2|1|5|Q\n2\n'):
        raw = b'Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market\n' + line
        with pytest.raises(IngestionError):
            read_capture(raw, metadata(raw))
