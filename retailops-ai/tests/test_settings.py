"""Multiple Groq API keys: settings.py::_load_groq_api_keys (the pure
scanning function) and Settings.groq_api_keys (the field it populates).
conftest.py points SERVICE_ROOT at an empty temp directory for the whole
test session, so these tests control every key purely via monkeypatched
env vars -- see conftest.py's own comment for why that redirection
exists.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from settings import Settings, _load_groq_api_keys, get_settings


def test_load_groq_api_keys_returns_empty_list_when_nothing_configured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert _load_groq_api_keys(tmp_path / "does-not-exist.env") == []


def test_load_groq_api_keys_treats_bare_groq_api_key_as_position_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "bare-key")
    assert _load_groq_api_keys(tmp_path / "does-not-exist.env") == ["bare-key"]


def test_load_groq_api_keys_orders_numbered_keys_ascending(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY_2", "second")
    monkeypatch.setenv("GROQ_API_KEY_1", "first")
    monkeypatch.setenv("GROQ_API_KEY_10", "tenth")
    assert _load_groq_api_keys(tmp_path / "does-not-exist.env") == ["first", "second", "tenth"]


def test_load_groq_api_keys_prefers_groq_api_key_1_over_the_bare_alias(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The bare GROQ_API_KEY is only a fallback for position 1 -- an
    explicit GROQ_API_KEY_1 wins if both happen to be set.
    """
    monkeypatch.setenv("GROQ_API_KEY", "bare-key")
    monkeypatch.setenv("GROQ_API_KEY_1", "numbered-key")
    assert _load_groq_api_keys(tmp_path / "does-not-exist.env") == ["numbered-key"]


def test_load_groq_api_keys_skips_empty_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEY_2", "real-key")
    assert _load_groq_api_keys(tmp_path / "does-not-exist.env") == ["real-key"]


def test_load_groq_api_keys_reads_the_env_file_when_present(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GROQ_API_KEY_1=from-file-1\nGROQ_API_KEY_2=from-file-2\n# GROQ_API_KEY_3=commented-out\n",
        encoding="utf-8",
    )
    assert _load_groq_api_keys(env_file) == ["from-file-1", "from-file-2"]


def test_load_groq_api_keys_env_var_overrides_the_env_file_for_the_same_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("GROQ_API_KEY_1=from-file\n", encoding="utf-8")
    monkeypatch.setenv("GROQ_API_KEY_1", "from-real-env")
    assert _load_groq_api_keys(env_file) == ["from-real-env"]


def test_settings_groq_api_keys_field_reflects_configured_env_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY_1", "first")
    monkeypatch.setenv("GROQ_API_KEY_2", "second")
    get_settings.cache_clear()

    try:
        assert get_settings().groq_api_keys == ["first", "second"]
    finally:
        monkeypatch.delenv("GROQ_API_KEY_1", raising=False)
        monkeypatch.delenv("GROQ_API_KEY_2", raising=False)
        monkeypatch.setenv("GROQ_API_KEY", "test-key-not-for-production")
        get_settings.cache_clear()


def test_settings_groq_api_keys_defaults_to_the_single_bare_key_in_test_env() -> None:
    """conftest.py's own os.environ.setdefault("GROQ_API_KEY", ...) is
    the baseline every other test in this suite implicitly relies on --
    asserted explicitly here so a regression in the loader is caught
    directly, not just indirectly through unrelated Groq-provider tests.
    """
    assert get_settings().groq_api_keys == ["test-key-not-for-production"]


def test_settings_construction_does_not_require_groq_api_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """groq_api_keys defaults to an empty list, not a required field --
    Settings() itself must not fail to construct when no Groq key is
    configured at all; llm/providers/groq.py is what fails fast, at
    first real use (see test_groq_provider.py).
    """
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert (
        Settings(
            retailops_database_url="sqlite:///:memory:",
            stockpilot_base_url="http://localhost:8000",
            stockpilot_username="u",
            stockpilot_password="p",
            gemini_api_key="g",
            jwt_secret="s",
        ).groq_api_keys
        == []
    )
