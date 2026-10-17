import pytest

from agent_engine.config import load_settings
from agent_engine.errors import ConfigError

LLM_VARS = ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY")


def load(monkeypatch, **env):
    for name, value in env.items():
        monkeypatch.setenv(name, str(value))
    return load_settings(_env_file=None)


def test_defaults(monkeypatch):
    settings = load(monkeypatch)
    assert settings.workers == 8
    assert settings.soft_cap_requests == 1700
    assert settings.brake_requests == 1950
    assert settings.per_company_cap == 14
    assert settings.store_mode == "jsonl"


def test_pass1_runs_without_llm_settings(monkeypatch):
    for name in LLM_VARS:
        monkeypatch.delenv(name, raising=False)
    settings = load_settings(_env_file=None)
    with pytest.raises(ConfigError, match="LLM_BASE_URL, LLM_MODEL, LLM_API_KEY"):
        settings.require_llm()


def test_llm_settings_when_present(monkeypatch):
    settings = load(monkeypatch, LLM_BASE_URL="https://llm.example.com/v1", LLM_MODEL="m", LLM_API_KEY="k")
    assert settings.require_llm() == ("https://llm.example.com/v1", "m", "k")


@pytest.mark.parametrize("workers", ["0", "9"])
def test_workers_out_of_range(monkeypatch, workers):
    with pytest.raises(ConfigError, match="WORKERS"):
        load(monkeypatch, WORKERS=workers)


def test_brake_above_2000_is_rejected(monkeypatch):
    with pytest.raises(ConfigError, match="BRAKE_REQUESTS"):
        load(monkeypatch, BRAKE_REQUESTS=2001)


def test_soft_cap_must_be_below_brake(monkeypatch):
    with pytest.raises(ConfigError, match="SOFT_CAP_REQUESTS"):
        load(monkeypatch, SOFT_CAP_REQUESTS=1950)


def test_unbuilt_features_fail_closed(monkeypatch):
    with pytest.raises(ConfigError, match="PLAYWRIGHT_ENABLED"):
        load(monkeypatch, PLAYWRIGHT_ENABLED="true")
    monkeypatch.delenv("PLAYWRIGHT_ENABLED")
    with pytest.raises(ConfigError, match="MODE"):
        load(monkeypatch, MODE="full")
