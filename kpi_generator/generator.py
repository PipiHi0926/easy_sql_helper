"""
generator.py
============
呼叫 LLM 為目標廠區生成 KPI SQL。
每個 KPI 獨立一次 LLM 呼叫，回傳 GenerationResult。
"""
import _bootstrap  # noqa: F401

import re
import time
from datetime import datetime

import llm_client
import prompt_renderer as pr
import data_loader as dl
from result_types import GenerationResult


def _extract_sql(response: str) -> str:
    """
    從 LLM 回應中萃取第一個 ```sql ... ``` 區塊的內容。
    若找不到，回傳完整 response（降級處理）。
    """
    blocks = re.findall(r"```sql\n(.*?)```", response, re.DOTALL)
    return blocks[0].strip() if blocks else response.strip()


def generate(
    kpi:            str,
    ref_factories:  list[str],
    target_factory: str,
    ref_rows:       list[dict],
    temperature:    float = 0.2,
    max_tokens:     int   = 4000,
    max_retries:    int   = 2,
) -> GenerationResult:
    """
    為單一 KPI 生成目標廠 SQL。
    回傳 GenerationResult，失敗時 status="FAILED"，不拋例外。
    """
    started = datetime.now()

    role       = pr.load("role.md")
    system     = pr.render(pr.load("generate_system.md"), ROLE=role)
    ref_block  = dl.build_reference_block(ref_rows)
    trigger    = pr.render(
        pr.load("generate_trigger.md"),
        KPI=kpi,
        TARGET_FACTORY=target_factory,
        REFERENCE_BLOCK=ref_block,
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": trigger},
    ]

    last_err: str | None = None
    for attempt in range(max_retries + 1):
        try:
            response = llm_client.chat_complete(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            dur = (datetime.now() - started).total_seconds()
            return GenerationResult(
                kpi=kpi,
                ref_factories=ref_factories,
                target_factory=target_factory,
                status="SUCCESS",
                raw_response=response,
                error_msg=None,
                duration_sec=dur,
            )
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            if attempt < max_retries:
                time.sleep(2 ** attempt)

    dur = (datetime.now() - started).total_seconds()
    return GenerationResult(
        kpi=kpi,
        ref_factories=ref_factories,
        target_factory=target_factory,
        status="FAILED",
        raw_response=None,
        error_msg=last_err,
        duration_sec=dur,
    )


def extract_generated_sql(gen: GenerationResult) -> str | None:
    """從 GenerationResult 萃取 SQL 字串（供 evaluator 使用）。"""
    if gen.status != "SUCCESS" or not gen.raw_response:
        return None
    return _extract_sql(gen.raw_response)
