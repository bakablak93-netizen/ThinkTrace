import pytest


@pytest.fixture(autouse=True)
def no_real_llm(monkeypatch):
    """Tests never call a real LLM: empty LLM_* vars (set, so a local .env cannot fill them)."""
    for name in ("LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.setenv(name, "")
