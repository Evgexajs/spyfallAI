import asyncio
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI, RateLimitError


class LLMError(Exception):
    """Base exception for LLM adapter errors."""

    pass


class LLMConfigError(LLMError):
    """Raised when LLM config is invalid or missing."""

    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM request times out."""

    pass


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> str:
        """Generate a completion from the given messages.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            model: Model identifier. If None, uses provider default.
            temperature: Sampling temperature (0.0-2.0).
            max_tokens: Maximum tokens in response.

        Returns:
            Generated text response.

        Raises:
            LLMError: On API errors.
            LLMTimeoutError: On timeout.
        """
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI API provider implementation."""

    DEFAULT_MODEL = "gpt-4o"
    DEFAULT_TIMEOUT = 30.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env var.
            default_model: Default model to use. Defaults to gpt-4o.
            timeout: Request timeout in seconds.
        """
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self._api_key:
            raise LLMError("OPENAI_API_KEY not set")

        self._default_model = default_model or self.DEFAULT_MODEL
        self._timeout = timeout
        self._client = AsyncOpenAI(api_key=self._api_key, timeout=timeout)

    async def complete(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> str:
        """Generate a completion using OpenAI API."""
        model = model or self._default_model

        try:
            response = await asyncio.wait_for(
                self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                timeout=self._timeout,
            )
            content = response.choices[0].message.content
            if content is None:
                raise LLMError("Empty response from OpenAI")
            return content

        except asyncio.TimeoutError:
            raise LLMTimeoutError(f"Request timed out after {self._timeout}s")
        except APITimeoutError as e:
            raise LLMTimeoutError(f"OpenAI API timeout: {e}")
        except RateLimitError as e:
            raise LLMError(f"Rate limit exceeded: {e}")
        except APIConnectionError as e:
            raise LLMError(f"Connection error: {e}")
        except APIError as e:
            raise LLMError(f"OpenAI API error: {e}")


class LLMConfig:
    """Loads and provides access to LLM configuration."""

    def __init__(self, config_path: Optional[str] = None):
        """Load config from file.

        Args:
            config_path: Path to llm_config.json. Defaults to project root.
        """
        if config_path is None:
            config_path = str(Path(__file__).parent.parent.parent / "llm_config.json")

        try:
            with open(config_path) as f:
                self._config: dict[str, Any] = json.load(f)
        except FileNotFoundError:
            raise LLMConfigError(f"Config file not found: {config_path}")
        except json.JSONDecodeError as e:
            raise LLMConfigError(f"Invalid JSON in config: {e}")

        self._validate()

    def _validate(self) -> None:
        """Validate config structure."""
        if "providers" not in self._config:
            raise LLMConfigError("Config missing 'providers' section")
        if "roles" not in self._config:
            raise LLMConfigError("Config missing 'roles' section")

    @property
    def providers(self) -> dict[str, Any]:
        return self._config["providers"]

    @property
    def roles(self) -> dict[str, Any]:
        return self._config["roles"]

    @property
    def per_character_overrides(self) -> dict[str, Any]:
        return self._config.get("per_character_overrides", {})

    def get_model_for_role(
        self, role: str, character_id: Optional[str] = None
    ) -> tuple[str, str]:
        """Get provider and model for a role, with optional character override.

        Args:
            role: Role name ('main' or 'utility').
            character_id: Optional character ID for per-character override.

        Returns:
            Tuple of (provider_name, model_name).
        """
        if character_id and character_id in self.per_character_overrides:
            override = self.per_character_overrides[character_id]
            return override["provider"], override["model"]

        if role not in self.roles:
            raise LLMConfigError(f"Unknown role: {role}")

        role_config = self.roles[role]
        return role_config["provider"], role_config["model"]

    def get_api_key_env(self, provider: str) -> str:
        """Get the env var name for a provider's API key."""
        if provider not in self.providers:
            raise LLMConfigError(f"Unknown provider: {provider}")
        return self.providers[provider]["api_key_env"]


def create_provider(
    config: LLMConfig,
    role: str = "main",
    character_id: Optional[str] = None,
) -> tuple[LLMProvider, str]:
    """Create an LLM provider based on config.

    Args:
        config: LLM configuration.
        role: Role name ('main' or 'utility').
        character_id: Optional character ID for per-character override.

    Returns:
        Tuple of (provider_instance, model_name).
    """
    provider_name, model = config.get_model_for_role(role, character_id)
    api_key_env = config.get_api_key_env(provider_name)
    api_key = os.getenv(api_key_env)

    if provider_name == "openai":
        return OpenAIProvider(api_key=api_key, default_model=model), model
    elif provider_name == "anthropic":
        raise LLMError("Anthropic provider not yet implemented")
    else:
        raise LLMConfigError(f"Unknown provider: {provider_name}")
