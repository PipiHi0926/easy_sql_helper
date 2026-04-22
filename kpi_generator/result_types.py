"""純資料型別：不依賴任何外部套件。"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class GenerationResult:
    """單一 KPI 的 SQL 生成結果。"""
    kpi:             str
    ref_factories:   list[str]
    target_factory:  str
    status:          str            # "SUCCESS" | "FAILED"
    raw_response:    str | None     # LLM 完整 Markdown 回應
    error_msg:       str | None
    duration_sec:    float | None = None


@dataclass
class EvaluationResult:
    """Backtest 模式下，AI 對生成結果的相似度評估。"""
    kpi:             str
    target_factory:  str
    status:          str
    raw_response:    str | None
    similarity_score: int | None    # 0~100，從回應中解析；解析失敗為 None
    error_msg:       str | None
    duration_sec:    float | None = None


@dataclass
class KpiResult:
    """一個 KPI 的完整執行結果（生成 + 可選的評估）。"""
    kpi:        str
    generation: GenerationResult
    evaluation: EvaluationResult | None   # backtest 才有；generate 模式為 None
    actual_sql: str | None                # backtest ground truth
