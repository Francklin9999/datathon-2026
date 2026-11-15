"""Global context survives session-owned profile creation, editing, and quantitative use."""
import pytest
from aplomb.api.errors import NotFound
from aplomb.contracts import api as a
from aplomb.contracts.models import InvestorContext
from pydantic import ValidationError

from tests.unit.profiles.test_profiles import A, B, create_request, service


def test_multiple_goals_and_fractional_horizon_are_preserved_and_isolated():
    svc = service()
    request = a.CreateProfileRequest.model_validate(create_request(
        horizonYears={'min': .25, 'max': 30},
        investorContext={'country': 'GB', 'investorType': 'endowment', 'language': 'fr',
                         'objectives': [{'name': 'Liquidity', 'horizonYears': .25, 'priority': 1},
                                        {'name': 'Long term capital', 'horizonYears': 30, 'priority': 2}]}))
    p = svc.create(A, request)
    assert p.investor_context.country == 'GB'
    assert p.investor_context.objectives[0].horizon_years == .25
    assert svc.get(A, p.profile_id).investor_context == p.investor_context
    with pytest.raises(NotFound):
        svc.get(B, p.profile_id)
    assert svc.get(B, 'robert').investor_context is None
    update = a.UpdateProfileRequest.model_validate({**request.to_wire(), 'version': 1})
    assert svc.replace(A, p.profile_id, update, 1).investor_context == p.investor_context
    # Uses exactly the same deterministic overview service as the seeded profiles.
    overview = svc.overview(A, p.profile_id, {'window': '1y'})
    assert overview.facts


@pytest.mark.parametrize('context', [
    {'country': 'United Kingdom'},
    {'objectives': [{'name': 'Bad', 'horizonYears': -1, 'priority': 1}]},
    {'objectives': [{'name': 'Bad', 'horizonYears': 2, 'priority': 0}]},
    {'objectives': [{'name': 'Goal', 'horizonYears': 1, 'priority': 1}] * 21},
])
def test_invalid_investor_context(context):
    with pytest.raises(ValidationError):
        InvestorContext.model_validate(context)
