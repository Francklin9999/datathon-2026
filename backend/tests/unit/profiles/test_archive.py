import pytest
from aplomb.api.errors import Conflict, NotFound
from aplomb.contracts.api import CreateProfileRequest

from tests.unit.profiles.test_profiles import A, B, create_request, service


def test_archive_restore_and_session_isolation():
    svc = service()
    p = svc.create(A, CreateProfileRequest.model_validate(create_request()))
    archived = svc.archive(A, p.profile_id, True, p.version)
    assert archived.archived
    assert p.profile_id not in {x.profile_id for x in svc.list(A)}
    assert [x.profile_id for x in svc.archived(A)] == [p.profile_id]
    assert svc.archived(B) == []
    with pytest.raises(NotFound):
        svc.archive(B, p.profile_id, False, archived.version)
    with pytest.raises(Conflict):
        svc.archive(A, p.profile_id, False, p.version)
    restored = svc.archive(A, p.profile_id, False, archived.version)
    assert not restored.archived and svc.archived(A) == []
    assert p.profile_id in {x.profile_id for x in svc.list(A)}
    with pytest.raises(Conflict):
        svc.archive(A, 'robert', True, 1)
