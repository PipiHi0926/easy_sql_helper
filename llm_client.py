"""
llm_client.py
=============
封裝 LLM API 呼叫，支援一般回應與串流（Streaming）模式。
設定優先順序：環境變數 > config.py 預設值

相容性說明：
  - 預設使用 OpenAI-compatible endpoint（公司 LiteLLM Proxy、Ollama v1/chat/completions 均適用）
  - 設定 LLM_DISABLE_THINKING=true 時，改走 Ollama 原生 /api/chat endpoint，
    並傳入 think=false 關閉 qwen3.x 的 thinking 模式（僅限本地 Ollama）
"""
import json
import urllib.request
from typing import Iterator

from openai import OpenAI

import config

_client = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)

# Ollama 原生 API endpoint（從 LLM_BASE_URL 推算）
# e.g. http://localhost:11434/v1 → http://localhost:11434/api/chat
_OLLAMA_CHAT_URL = config.LLM_BASE_URL.rstrip("/").removesuffix("/v1") + "/api/chat"


def _ollama_complete(messages: list[dict], temperature: float, max_tokens: int) -> str:
    """呼叫 Ollama 原生 /api/chat，並傳入 think=false 關閉 thinking 模式。"""
    payload = json.dumps({
        "model":    config.LLM_MODEL,
        "messages": messages,
        "think":    False,
        "stream":   False,
        "options":  {"temperature": temperature, "num_predict": max_tokens},
    }).encode("utf-8")
    req = urllib.request.Request(
        _OLLAMA_CHAT_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    return data.get("message", {}).get("content", "")


def chat_complete(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 4000,
) -> str:
    """一次性回應（非串流）。
    LLM_DISABLE_THINKING=true → 走 Ollama 原生 API 關閉 thinking（本地 qwen3.x 用）
    其餘情況 → OpenAI-compatible endpoint（公司 LLM、一般 Ollama 皆適用）
    """
    if config.LLM_DISABLE_THINKING:
        return _ollama_complete(messages, temperature, max_tokens)

    response = _client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


def chat_stream(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 4000,
) -> Iterator[str]:
    """串流回應，yield 每個 chunk 的文字內容。（Streamlit UI 用）"""
    stream = _client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content
