"""The web Markets page types capability states as available | aside | removed."""

from aplomb.api.settings import Settings
from aplomb.intelligence.capabilities import capabilities


def test_capability_states_match_the_web_union_and_sec_stays_removed():
    families = {item['id']: item for item in capabilities(Settings(data_version="snap-20261113-starter"))['families']}
    assert {item['state'] for item in families.values()} <= {'available', 'aside', 'removed'}
    assert families['sec']['state'] == 'removed'
    assert families['nport_example']['state'] == 'removed'
