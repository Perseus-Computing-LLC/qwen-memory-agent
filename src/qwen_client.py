"""Qwen Cloud client — OpenAI-compatible wrapper for Qwen Cloud models.

Qwen Cloud exposes an OpenAI-compatible API at:
    https://dashscope-intl.aliyuncs.com/compatible-mode/v1

Supported models for the MemoryAgent track:
    - qwen-max-longcontext    (1M tokens, best for multi-session context)
    - qwen-max                (general reasoning)
    - qwen-plus               (faster, cheaper)
"""

import os
from openai import OpenAI


class QwenClient:
    """OpenAI-compatible client for Qwen Cloud."""

    BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "qwen-max",
        base_url: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("QWEN_CLOUD_API_KEY", "")
        self.model = model
        self.base_url = base_url or self.BASE_URL

        if not self.api_key:
            raise ValueError(
                "Qwen Cloud API key required. Set QWEN_CLOUD_API_KEY env var "
                "or pass api_key parameter. Get yours at https://www.qwencloud.com/"
            )

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def chat(
        self,
        messages: list[dict],
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Send a chat completion request.

        Args:
            messages: List of {"role": "user|assistant", "content": "..."}
            system: System prompt (prepended as system message)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Returns:
            Model response text
        """
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content

    def list_models(self) -> list[str]:
        """List available models from Qwen Cloud."""
        try:
            models = self.client.models.list()
            return [m.id for m in models.data]
        except Exception:
            # Fallback: return known models
            return [
                "qwen-max-longcontext",
                "qwen-max",
                "qwen-plus",
                "qwen-turbo",
            ]


# Convenience function for testing without full client setup
def test_connection(api_key: str) -> dict:
    """Test Qwen Cloud API connectivity."""
    client = QwenClient(api_key=api_key)
    try:
        response = client.chat(
            messages=[{"role": "user", "content": "Say 'connected' in one word."}],
            max_tokens=10,
        )
        return {"status": "ok", "response": response}
    except Exception as e:
        return {"status": "error", "error": str(e)}
