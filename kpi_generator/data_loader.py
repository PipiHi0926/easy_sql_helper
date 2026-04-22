"""
資料載入與查詢。
資料格式：CSV / Excel，三欄 ITEM（廠區代號）、SEQ（KPI 名稱）、VALUE（SQL 字串）。
"""
from pathlib import Path

import pandas as pd


def load(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到資料檔：{p}")
    if p.suffix in (".xlsx", ".xls"):
        return pd.read_excel(p)
    return pd.read_csv(p)


def list_kpis(df: pd.DataFrame) -> list[str]:
    return sorted(df["SEQ"].dropna().unique().tolist())


def list_factories(df: pd.DataFrame) -> list[str]:
    return sorted(df["ITEM"].dropna().unique().tolist())


def get_reference_rows(df: pd.DataFrame, kpi: str, factories: list[str]) -> list[dict]:
    """回傳指定 KPI 在指定廠區列表中的所有 SQL rows。"""
    mask = (df["SEQ"] == kpi) & (df["ITEM"].isin(factories))
    return df[mask][["ITEM", "VALUE"]].to_dict("records")


def get_actual_sql(df: pd.DataFrame, kpi: str, factory: str) -> str | None:
    """回傳指定 KPI 在指定廠區的實際 SQL（backtest ground truth）；找不到回傳 None。"""
    rows = df[(df["SEQ"] == kpi) & (df["ITEM"] == factory)]
    if rows.empty:
        return None
    return str(rows.iloc[0]["VALUE"])


def build_reference_block(rows: list[dict]) -> str:
    """將廠區 SQL rows 格式化成 Markdown 區塊，供注入 prompt。"""
    if not rows:
        return "_（無參考資料）_"
    parts = [f"### 廠區：{r['ITEM']}\n```sql\n{r['VALUE']}\n```" for r in rows]
    return "\n\n".join(parts)
