"""Qwen Cloud client -- OpenAI-compatible wrapper for Qwen Cloud models.

The MemoryAgent uses three distinct Qwen Cloud capabilities:

  1. Long-context reasoning  -- qwen-max-longcontext for multi-session context
  2. Native function calling -- structured, reliable memory extraction
  3. Text embeddings         -- text-embedding-v3 for hybrid semantic recall

Endpoint (international):
    https://dashscope-intl.aliyuncs.com/compatible-mode/v1
"""

import os
from openai import OpenAI


class QwenClient:
    """OpenAI-compatible client for Qwen Cloud."""

    BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

    def __init__(self, api_key=None, model="qwen-max-longcontext",
                 base_url=None, embed_model=None):
        self.api_key = api_key or os.environ.get("QWEN_CLOUD_API_KEY", "")
        self.model = model
        self.base_url = (base_url or os.environ.get("QWEN_CLOUD_BASE_URL")
                         or self.BASE_URL)
        self.embed_model = (embed_model
                            or os.environ.get("QWEN_EMBED_MODEL", "text-embedding-v3"))
        if not self.api_key:
            raise ValueError(
                "Qwen Cloud API key required. Set QWEN_CLOUD_API_KEY or pass "
                "api_key. Get one at https://www.qwencloud.com/"
            )
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat(self, messages, system="", temperature=0.7, max_tokens=4096):
        """Plain chat completion. Returns the response text."""
        full = ([{"role": "system", "content": system}] if system else []) + list(messages)
        resp = self.client.chat.completions.create(
            model=self.model, messages=full,
            temperature=temperature, max_tokens=max_tokens,
        )
        return resp.choices[0].message.content

    def chat_with_tools(self, messages, tools, system="", tool_choice="auto",
                        temperature=0.3, max_tokens=2048, model=None):
        """Chat completion using Qwen Cloud native function calling.

        Returns the raw assistant message (inspect .tool_calls / .content).
        `model` overrides the default -- use a tool-capable model (e.g.
        qwen-max) even when the agent reasons with a long-context variant.
        """
        full = ([{"role": "system", "content": system}] if system else []) + list(messages)
        resp = self.client.chat.completions.create(
            model=model or self.model, messages=full, tools=tools,
            tool_choice=tool_choice, temperature=temperature, max_tokens=max_tokens,
        )
        return resp.choices[0].message

    def embed(self, text):
        """Return a Qwen Cloud embedding vector for `text`, or None on failure."""
        try:
            resp = self.client.embeddings.create(model=self.embed_model, input=text)
            return resp.data[0].embedding
        except Exception:
            return None

    def list_models(self):
        try:
            return [m.id for m in self.client.models.list().data]
        except Exception:
            return ["qwen-max-longcontext", "qwen-max", "qwen-plus", "qwen-turbo"]
