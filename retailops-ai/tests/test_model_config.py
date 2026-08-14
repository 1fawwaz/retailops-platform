from model_config import ModelConfig, get_model_config


def test_get_model_config_loads_real_config_file() -> None:
    config = get_model_config()

    assert isinstance(config, ModelConfig)
    assert config.roles.planner
    assert config.roles.retriever
    assert config.roles.decision
    assert config.fallback


def test_budgets_match_claude_md_spec() -> None:
    config = get_model_config()

    # 2, not 12, since the Stage 3 replan-loop cap was cut to 2 with the
    # measured latency rationale (config/models.yaml budgets) -- the data
    # surface is complete after 2 rounds for the acceptance query and the
    # graph proceeds to Report deterministically after that (Task 3.6
    # truncated-reasoning flag), instead of looping 4-90s rounds under
    # Groq 429 contention until any deadline.
    assert config.budgets.max_tool_iterations == 2
    assert config.budgets.max_tokens_per_execution == 60000


def test_no_configured_role_uses_a_gemini_2_5_model() -> None:
    """CLAUDE.md: that generation is scheduled for shutdown October 2026."""
    config = get_model_config()

    for role_config in (config.roles.planner, config.roles.retriever, config.roles.decision):
        assert not role_config.model.startswith("gemini-2.5")


def test_get_model_config_is_cached() -> None:
    assert get_model_config() is get_model_config()


def test_all_roles_are_configured_for_groq() -> None:
    """Every role's PRIMARY provider is groq per CLAUDE.md's own stack
    pin ("Groq primary, Gemini fallback", Task 6.5) -- Gemini only ever
    appears as the one configured fallback, never a role's own primary.
    Groq is primary because this account's Gemini quota has been
    observed hard-zero (docs/adr/007-multi-provider-fallback.md), not
    because of any quality difference between the two providers.
    """
    config = get_model_config()

    for role_config in (config.roles.planner, config.roles.retriever, config.roles.decision):
        assert role_config.provider == "groq"


def test_fallback_is_configured_for_gemini() -> None:
    config = get_model_config()

    assert config.fallback.provider == "gemini"
    assert config.fallback.model
