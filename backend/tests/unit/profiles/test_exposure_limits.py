import pytest
from aplomb.api.errors import Conflict
from aplomb.contracts.api import AddExposureLimitRequest, CreateProfileRequest, UpdateProfileRequest
from aplomb.optimizer.services import deriver

from tests.unit.profiles.test_profiles import A, create_request, service


def test_currency_and_country_limits_use_the_same_policy_engine_and_survive_editing():
    svc = service(deriver=deriver)
    p = svc.create(A, CreateProfileRequest.model_validate(create_request()))
    p = svc.add_exposure_limit(A, p.profile_id, AddExposureLimitRequest(dimension='currency', key='USD', threshold=30, version=p.version))
    overview = svc.overview(A, p.profile_id, {'window': '1y'})
    check = next(c for c in overview.rule_checks if c.rule_id == 'cap.currency.USD')
    assert check.status == 'conflict' and check.value == 60
    assert check.value_fact_id in overview.facts
    update = UpdateProfileRequest.model_validate({**create_request(name='Changed'), 'version': p.version, 'rules': None})
    p = svc.replace(A, p.profile_id, update, p.version)
    assert next(r for r in p.rules if r.rule_id == 'cap.currency.USD').threshold == 30
    p = svc.add_exposure_limit(A, p.profile_id, AddExposureLimitRequest(dimension='country', key='CAN', threshold=30, version=p.version))
    check = next(c for c in svc.overview(A, p.profile_id, {}).rule_checks if c.rule_id == 'cap.country.CAN')
    assert check.status == 'conflict' and check.value == 40


def test_exact_duplicate_preserves_custom_policies_and_assigns_independent_identity():
    svc = service(deriver=deriver)
    p = svc.create(A, CreateProfileRequest.model_validate(create_request()))
    p = svc.add_exposure_limit(A, p.profile_id, AddExposureLimitRequest(dimension='currency', key='USD', threshold=30, version=p.version))
    clone = svc.duplicate(A, p.profile_id)
    assert clone.profile_id != p.profile_id
    assert clone.portfolio.positions == p.portfolio.positions
    assert [r.origin for r in clone.rules] == [r.origin for r in p.rules]
    assert clone.rules[-1].threshold == 30
    with pytest.raises(Conflict):
        svc.add_exposure_limit(A, 'robert', AddExposureLimitRequest(dimension='currency', key='USD', threshold=30, version=1))


@pytest.mark.parametrize('field,value', [('comparator', '>='), ('metric', 'weight.country'),
    ('unit', 'ratio'), ('countsInVerdict', False), ('target', {'dimension': 'country', 'key': 'CAN'})])
def test_rule_metadata_cannot_change_the_meaning_of_a_registered_policy(field, value):
    from aplomb.api.errors import ServiceError
    from aplomb.contracts.api import CreateProfileRequest

    from tests.unit.profiles.test_profiles import create_request
    svc = service()
    body = create_request()
    body['rules'][0][field] = value
    with pytest.raises(ServiceError, match='deterministic definition'):
        svc.create(A, CreateProfileRequest.model_validate(body))
