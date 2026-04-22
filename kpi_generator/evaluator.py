"""
evaluator.py
============
Backtest 模式專用：呼叫 LLM 對「AI 生成 SQL」與「實際 SQL（Ground Truth）」
進行相似度評估，回傳 EvaluationResult。
"""
import _bootstrap  # noqa: F401

import re
import time
from datetime import datetime

import llm_client
import prompt_renderer as pr
from result_types import EvaluationResult


def _extract_score(response: str) -> int | None:
    """
    從評估回應中嘗試解析總分（0~100）。
    找「總分」那行的數字，例如：| **總分** | **100** | 82 | ... → 82
    解析失敗回傳 None。
    """
    # 匹配 | **總分** | ... | <數字> | 這樣的表格行
    pattern = r"\*\*總分\*\*[^\n]*?\|\s*(\d{1,3})\s*\|"
    m = re.search(pattern, response)
    if m:
        score = int(m.group(1))
        return score if 0 <= score <= 100 else None
    # 備用：找任何「總分：XX」或「總分 XX 分」
    m2 = re.search(r"總分[：:]\s*(\d{1,3})", response)
    if m2:
        score = int(m2.group(1))
        return score if 0 <= score <= 100 else None
    return None


def evaluate(
    kpi:            str,
    target_factory: str,
    generated_sql:  str,
    actual_sql:     str,
    temperature:    float = 0.2,
    max_tokens:     int   = 3000,
    max_retries:    int   = 2,
) -> EvaluationResult:
    """
    對單一 KPI 的生成結果進行相似度評估。
    回傳 EvaluationResult，失敗時 status="FAILED"，不拋例外。
    """
    started = datetime.now()

    role    = pr.load("role.md")
    system  = pr.render(pr.load("evaluate_system.md"), ROLE=role)
    trigger = pr.render(
        pr.load("evaluate_trigger.md"),
        KPI=kpi,
        TARGET_FACTORY=target_factory,
        GENERATED_SQL=generated_sql,
        ACTUAL_SQL=actual_sql,
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
            dur   = (datetime.now() - started).total_seconds()
            score = _extract_score(response)
            return EvaluationResult(
                kpi=kpi,
                target_factory=target_factory,
                status="SUCCESS",
                raw_response=response,
                similarity_score=score,
                error_msg=None,
                duration_sec=dur,
            )
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            if attempt < max_retries:
                time.sleep(2 ** attempt)

    dur = (datetime.now() - started).total_seconds()
    return EvaluationResult(
        kpi=kpi,
        target_factory=target_factory,
        status="FAILED",
        raw_response=None,
        similarity_score=None,
        error_msg=last_err,
        duration_sec=dur,
    )
