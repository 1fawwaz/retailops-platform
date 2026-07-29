from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from llm.providers.gemini import list_model_ids


def test_list_model_ids_strips_the_models_prefix() -> None:
    fake_models = [
        SimpleNamespace(name="models/gemini-3.5-flash"),
        SimpleNamespace(name="models/gemini-3.1-pro-preview"),
    ]
    fake_client = MagicMock()
    fake_client.models.list.return_value = fake_models

    with patch("llm.providers.gemini.genai.Client", return_value=fake_client) as mock_client_cls:
        result = list_model_ids()

    assert result == ["gemini-3.5-flash", "gemini-3.1-pro-preview"]
    mock_client_cls.assert_called_once()


def test_list_model_ids_skips_entries_with_no_name() -> None:
    fake_models = [SimpleNamespace(name=None), SimpleNamespace(name="models/gemini-3.5-flash")]
    fake_client = MagicMock()
    fake_client.models.list.return_value = fake_models

    with patch("llm.providers.gemini.genai.Client", return_value=fake_client):
        result = list_model_ids()

    assert result == ["gemini-3.5-flash"]
