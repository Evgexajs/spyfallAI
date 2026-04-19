import asyncio
import os
from abc import ABC, abstractmethod
from typing import Optional

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI, RateLimitError


class LLMError(Exception):
    """Base exception for LLM adapter errors."""

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
