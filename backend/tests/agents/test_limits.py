import pytest
from aplomb.agents.limits import BudgetExceeded, Limits


def test_lower_configured_budgets_are_enforced_before_an_attempt():
    limits = Limits(max_llm_calls=1, max_research_calls=0, max_revisions=0)
    limits.take("llm_calls")
    for counter in ["llm_calls", "research_calls", "revisions"]:
        with pytest.raises(BudgetExceeded):
            limits.take(counter)
    assert limits.llm_calls == 1 and limits.research_calls == 0 and limits.revisions == 0


def test_global_safety_ceilings_cannot_be_increased_by_configuration():
    for settings in [{"max_llm_calls": 13}, {"max_research_calls": -1}, {"max_revisions": True}]:
        with pytest.raises(ValueError):
            Limits(**settings)


def test_cached_prompt_tokens_are_preserved_without_double_counting():
    from aplomb.agents.models import prompt_token_count
    # Providers may include cache tokens in the input count, or report them separately.
    assert prompt_token_count({"inputTokens": 100, "outputTokens": 10, "totalTokens": 110,
                               "cacheReadInputTokens": 80}) == 100
    assert prompt_token_count({"inputTokens": 2, "outputTokens": 10, "totalTokens": 112,
                               "cacheReadInputTokens": 80, "cacheWriteInputTokens": 20}) == 102
