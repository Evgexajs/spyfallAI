"""Security tests for API key handling (TASK-044)."""

import json
import os
import re
from pathlib import Path

import pytest


def get_project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent


class TestApiKeySecurity:
    """Test suite for API key security requirements."""

    def test_env_in_gitignore(self):
        """Verify .env is listed in .gitignore."""
        gitignore_path = get_project_root() / ".gitignore"
        assert gitignore_path.exists(), ".gitignore file must exist"

        content = gitignore_path.read_text()
        lines = [line.strip() for line in content.splitlines()]

        assert ".env" in lines, ".env must be in .gitignore"

    def test_env_example_has_no_real_values(self):
        """Verify .env.example has empty values for API keys."""
        env_example_path = get_project_root() / ".env.example"
        assert env_example_path.exists(), ".env.example file must exist"

        content = env_example_path.read_text()

        api_key_pattern = re.compile(r"^(OPENAI_API_KEY|ANTHROPIC_API_KEY)=(.*)$", re.MULTILINE)
        matches = api_key_pattern.findall(content)

        assert len(matches) >= 2, "Both API key variables should be in .env.example"

        for key_name, value in matches:
            assert value.strip() == "", \
                f"{key_name} must have empty value in .env.example, got: '{value}'"

    def test_game_model_has_no_api_key_fields(self):
        """Verify Game model doesn't store API keys."""
        from src.models.game import Game, GameConfig

        game_fields = set(Game.model_fields.keys())
        config_fields = set(GameConfig.model_fields.keys())

        forbidden_patterns = [
            "api_key", "apikey", "secret_key", "password", "credential", "auth_token"
        ]

        for field in game_fields | config_fields:
            field_lower = field.lower()
            for pattern in forbidden_patterns:
                assert pattern not in field_lower, f"Field '{field}' may contain sensitive data"

    def test_llm_config_stores_env_names_not_keys(self):
        """Verify llm_config.json stores env variable names, not actual keys."""
        config_path = get_project_root() / "llm_config.json"
        assert config_path.exists(), "llm_config.json must exist"

        with open(config_path) as f:
            config = json.load(f)

        for provider_name, provider_config in config.get("providers", {}).items():
            assert "api_key_env" in provider_config, \
                f"Provider {provider_name} must use api_key_env"
            env_name = provider_config["api_key_env"]
            assert env_name.endswith("_API_KEY") or env_name.endswith("_KEY"), \
                f"api_key_env should be an env variable name, got: {env_name}"
            assert not env_name.startswith("sk-"), \
                "api_key_env must be env var name, not actual key"

    def test_no_api_keys_in_game_logs(self):
        """Verify no API keys in saved game logs (if any exist)."""
        games_dir = get_project_root() / "games"
        if not games_dir.exists():
            pytest.skip("No games directory yet")

        game_files = list(games_dir.glob("*.json"))
        if not game_files:
            pytest.skip("No game logs to check")

        api_key_patterns = [
            r"sk-[a-zA-Z0-9]{20,}",
            r"OPENAI_API_KEY",
            r"ANTHROPIC_API_KEY",
            r"api[_-]?key",
        ]

        for game_file in game_files:
            content = game_file.read_text()
            for pattern in api_key_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                assert not matches, \
                    f"Potential API key leak in {game_file.name}: {matches}"

    def test_adapter_uses_env_vars(self):
        """Verify LLM adapter loads keys from environment variables."""
        from src.llm.adapter import LLMError, OpenAIProvider

        with pytest.raises(LLMError, match="OPENAI_API_KEY not set"):
            original = os.environ.pop("OPENAI_API_KEY", None)
            try:
                OpenAIProvider()
            finally:
                if original is not None:
                    os.environ["OPENAI_API_KEY"] = original

    def test_no_hardcoded_keys_in_source(self):
        """Verify no hardcoded API keys in source code."""
        src_dir = get_project_root() / "src"

        api_key_pattern = re.compile(r'sk-[a-zA-Z0-9]{20,}')

        for py_file in src_dir.rglob("*.py"):
            content = py_file.read_text()
            matches = api_key_pattern.findall(content)
            assert not matches, \
                f"Hardcoded API key found in {py_file.name}: {matches}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
