"""
llm_client.py
=============
封裝 LLM API 呼叫，支援一般回應與串流（Streaming）模式。
設定優先順序：環境變數 > config.py 預設值
"""
from typing import Iterator
from openai import OpenAI
import config

_client = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)


def chat_complete(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 4000,
) -> str:
    """一次性回應（非串流）"""
    response = _client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


def chat_stream(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 4000,
) -> Iterator[str]:
    """串流回應，yield 每個 chunk 的文字內容"""
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
