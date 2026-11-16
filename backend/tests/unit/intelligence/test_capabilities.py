"""The source-capabilities shim reports no research family, in the shape the Markets page reads."""

from aplomb.intelligence.capabilities import capabilities


def test_shim_reports_no_family_and_an_empty_catalogue():
    body = capabilities()
    # SourceAvailability.tsx reads families, catalogue.rows, catalogue.source_count and note.
    assert body['families'] == []
    assert body['catalogue'] == {'rows': [], 'source_count': 0}
    assert body['note']
