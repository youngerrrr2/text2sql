"""智谱 GLM(anthropic 兼容端点)客户端。"""
from __future__ import annotations

from anthropic import Anthropic

from db import ENV


def complete(system: str, user: str, max_tokens: int = 2000) -> str:
    client = Anthropic(
        api_key=ENV["LLM_API_KEY"],
        base_url=ENV["LLM_BASE_URL"],
    )
    resp = client.messages.create(
        model=ENV["LLM_MODEL"],
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")
