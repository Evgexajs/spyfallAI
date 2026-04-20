import asyncio
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI, RateLimitError


MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    "gpt-4-turbo": {"input": 10.00 / 1_000_000, "output": 30.00 / 1_000_000},
    "gpt-3.5-turbo": {"input": 0.50 / 1_000_000, "output": 1.50 / 1_000_000},
}


@dataclass
class LLMResponse:
    """Response from LLM with content and usage info."""

    content: str
    input_tokens: int
    output_tokens: int
    model: str

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def calculate_cost(self) -> float:
        """Calculate cost in USD based on model pricing."""
        pricing = MODEL_PRICING.get(self.model, MODEL_PRICING.get("gpt-4o"))
        input_cost = self.input_tokens * pricing["input"]
        output_cost = self.output_tokens * pricing["output"]
        return input_cost + output_cost


class LLMError(Exception):
    """Base exception for LLM adapter errors."""

    pass


class LLMConfigError(LLMError):
    """Raised when LLM config is invalid or missing."""

    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM request times out."""

    pass


class CostExceededError(LLMError):
    """Raised when game cost exceeds MAX_PARTY_COST_USD."""

    def __init__(self, current_cost: float, max_cost: float):
        self.current_cost = current_cost
        self.max_cost = max_cost
        super().__init__(
            f"Cost limit exceeded: ${current_cost:.4f} >= ${max_cost:.2f}"
        )


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Generate a completion from the given messages.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            model: Model identifier. If None, uses provider default.
            temperature: Sampling temperature (0.0-2.0).
            max_tokens: Maximum tokens in response.
            json_mode: If True, force JSON output format.

        Returns:
            LLMResponse with content and token usage.

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
        json_mode: bool = False,
    ) -> LLMResponse:
        """Generate a completion using OpenAI API."""
        model = model or self._default_model

        try:
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = await asyncio.wait_for(
                self._client.chat.completions.create(**kwargs),
                timeout=self._timeout,
            )
            content = response.choices[0].message.content
            if content is None:
                raise LLMError("Empty response from OpenAI")

            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0

            return LLMResponse(
                content=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=model,
            )

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
