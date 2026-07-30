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

    assert config.budgets.max_tool_iterations == 12
    assert config.budgets.max_tokens_per_execution == 60000


def test_no_configured_role_uses_a_gemini_2_5_model() -> None:
    """CLAUDE.md: that generation is scheduled for shutdown October 2026."""
    config = get_model_config()

    for role_config in (config.roles.planner, config.roles.retriever, config.roles.decision):
        assert not role_config.model.startswith("gemini-2.5")


def test_get_model_config_is_cached() -> None:
    assert get_model_config() is get_model_config()


def test_all_roles_are_configured_for_gemini() -> None:
    """Every role's PRIMARY provider is gemini per CLAUDE.md's own stack
    pin ("Gemini primary, Groq fallback") -- Groq only ever appears as
    the one configured fallback, never a role's own primary.
    """
    config = get_model_config()

    for role_config in (config.roles.planner, config.roles.retriever, config.roles.decision):
        assert role_config.provider == "gemini"


def test_fallback_is_configured_for_groq() -> None:
    config = get_model_config()

    assert config.fallback.provider == "groq"
    assert config.fallback.model
