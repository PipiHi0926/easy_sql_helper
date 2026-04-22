"""
output_writer.py
================
將 KpiResult 清單寫出成完整報告包。

Backtest 模式：
  output/backtest_<ref>_to_<target>_<ts>/
    SUMMARY.md           執行摘要 + 評分一覽表
    EVALUATION_REPORT.md 所有 KPI 評分彙整（含改善建議）
    GENERATED_SQLS.md    所有生成 SQL 彙整
    kpis/<KPI>.md        每個 KPI 的完整報告（生成 + 評估 + Ground Truth）

Generate 模式：
  output/generate_<ref>_to_<target>_<ts>/
    SUMMARY.md
    GENERATED_SQLS.md
    kpis/<KPI>.md        每個 KPI 的生成報告
"""
import json
import re
from datetime import datetime
from pathlib import Path

from result_types import KpiResult


# ── 目錄管理 ───────────────────────────────────────────────────

def make_run_dir(
    base_output_dir: str,
    mode:            str,   # "backtest" | "generate"
    ref_factories:   list[str],
    target_factory:  str,
) -> Path:
    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    ref_str = "_".join(f.replace("SQL_", "") for f in ref_factories[:2])  # 最多取2個避免路徑太長
    if len(ref_factories) > 2:
        ref_str += f"_+{len(ref_factories)-2}more"
    name    = f"{mode}_{ref_str}_to_{target_factory}_{ts}"
    run_dir = Path(base_output_dir) / name
    (run_dir / "kpis").mkdir(parents=True, exist_ok=True)
    return run_dir


# ── 段落萃取 helpers ──────────────────────────────────────────

def _extract_section(text: str, heading: str) -> str:
    """萃取 ## <heading> 到下一個 ## 之間的內容（不含標題行本身）。"""
    pattern = rf"##\s*{re.escape(heading)}[^\n]*\n(.*?)(?=\n##\s|\Z)"
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ""


def _extract_sql_block(text: str) -> str:
    """從文字中萃取第一個 ```sql ... ``` 區塊（不含標記行）。"""
    m = re.search(r"```sql\n(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else ""


# ── 單一 KPI 報告 ─────────────────────────────────────────────

def write_kpi_file(result: KpiResult, mode: str, kpi_dir: Path) -> None:
    safe = result.kpi.replace("/", "_").replace(" ", "_")
    out  = kpi_dir / f"{safe}.md"

    gen  = result.generation
    evl  = result.evaluation
    lines: list[str] = []

    # --- YAML-like header ---
    lines += [
        "---",
        f"kpi: {result.kpi}",
        f"target_factory: {gen.target_factory}",
        f"ref_factories: [{', '.join(gen.ref_factories)}]",
        f"mode: {mode}",
        f"gen_status: {gen.status}",
    ]
    if evl:
        score_str = str(evl.similarity_score) if evl.similarity_score is not None else "N/A"
        lines.append(f"eval_status: {evl.status}")
        lines.append(f"similarity_score: {score_str}")
    lines += ["---", "", f"# {result.kpi} — {gen.target_factory}", ""]

    # --- Generation Section ---
    lines += ["## 生成結果", ""]
    if gen.status == "SUCCESS" and gen.raw_response:
        lines.append(gen.raw_response)
    else:
        lines += [f"**生成失敗**", f"", f"錯誤：{gen.error_msg}", ""]

    # --- Evaluation Section (backtest only) ---
    if evl:
        lines += ["", "---", "", "## 相似度評估", ""]
        if evl.status == "SUCCESS" and evl.raw_response:
            lines.append(evl.raw_response)
        else:
            lines += [f"**評估失敗**", f"", f"錯誤：{evl.error_msg}", ""]

    # --- Ground Truth Section (backtest only) ---
    if result.actual_sql:
        lines += [
            "", "---", "",
            "## 實際 SQL（Ground Truth）", "",
            "```sql",
            result.actual_sql,
            "```",
        ]

    out.write_text("\n".join(lines), encoding="utf-8")


# ── SUMMARY.md ────────────────────────────────────────────────

def write_summary(results: list[KpiResult], mode: str, run_dir: Path) -> None:
    success_gen = sum(1 for r in results if r.generation.status == "SUCCESS")
    failed_gen  = sum(1 for r in results if r.generation.status == "FAILED")
    total       = len(results)

    lines: list[str] = [
        "# 執行摘要",
        "",
        f"| 項目 | 值 |",
        f"|------|---|",
        f"| 模式 | {mode} |",
        f"| 目標廠 | {results[0].generation.target_factory if results else '—'} |",
        f"| 參考廠 | {', '.join(results[0].generation.ref_factories) if results else '—'} |",
        f"| 執行時間 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |",
        f"| 總 KPI 數 | {total} |",
        f"| 生成成功 | {success_gen} |",
        f"| 生成失敗 | {failed_gen} |",
        "",
    ]

    # Backtest: add score column
    if mode == "backtest":
        scores = [
            r.evaluation.similarity_score
            for r in results
            if r.evaluation and r.evaluation.similarity_score is not None
        ]
        if scores:
            avg = sum(scores) / len(scores)
            lines += [
                f"| 平均相似度 | {avg:.1f} / 100 |",
                f"| 評估筆數 | {len(scores)} |",
                "",
            ]

    lines += ["## KPI 結果一覽", ""]

    if mode == "backtest":
        lines.append("| KPI | 生成 | 評估 | 相似度 | 耗時（生成+評估） |")
        lines.append("|-----|------|------|--------|-----------------|")
        for r in results:
            g_dur = f"{r.generation.duration_sec:.1f}s" if r.generation.duration_sec else "—"
            e_dur = f"{r.evaluation.duration_sec:.1f}s" if r.evaluation and r.evaluation.duration_sec else "—"
            score = str(r.evaluation.similarity_score) if r.evaluation and r.evaluation.similarity_score is not None else "—"
            evl_s = r.evaluation.status if r.evaluation else "—"
            lines.append(f"| {r.kpi} | {r.generation.status} | {evl_s} | {score}/100 | {g_dur} + {e_dur} |")
    else:
        lines.append("| KPI | 生成 | 耗時 |")
        lines.append("|-----|------|------|")
        for r in results:
            dur = f"{r.generation.duration_sec:.1f}s" if r.generation.duration_sec else "—"
            lines.append(f"| {r.kpi} | {r.generation.status} | {dur} |")

    # Failed details
    failed = [r for r in results if r.generation.status == "FAILED"]
    if failed:
        lines += ["", "## 失敗 KPI", ""]
        for r in failed:
            lines += [
                f"### {r.kpi}",
                f"- 錯誤：{r.generation.error_msg}",
                "",
            ]

    (run_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


# ── GENERATED_SQLS.md ─────────────────────────────────────────

def write_generated_sqls(results: list[KpiResult], run_dir: Path) -> None:
    """彙整所有成功生成的 SQL，方便工程師一次瀏覽或複製。"""
    target = results[0].generation.target_factory if results else "—"
    lines: list[str] = [
        f"# 生成 SQL 彙整 — {target}",
        f"> 產生時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "> 含 {{PLACEHOLDER}} 的項目需工程師確認後替換。",
        "",
    ]

    for r in results:
        if r.generation.status != "SUCCESS" or not r.generation.raw_response:
            lines += [f"## {r.kpi}", "", "_（生成失敗）_", ""]
            continue

        # 從第三段「生成 SQL」萃取 SQL 區塊
        section3 = _extract_section(r.generation.raw_response, "三、")
        sql = _extract_sql_block(section3) if section3 else _extract_sql_block(r.generation.raw_response)

        lines += [f"## {r.kpi}", ""]
        if sql:
            lines += [f"```sql\n{sql}\n```", ""]
        else:
            lines += ["_（無法萃取 SQL，請查閱完整報告）_", ""]

    (run_dir / "GENERATED_SQLS.md").write_text("\n".join(lines), encoding="utf-8")


# ── EVALUATION_REPORT.md（backtest 專用）─────────────────────

def write_evaluation_report(results: list[KpiResult], run_dir: Path) -> None:
    """彙整所有 KPI 的評分與改善建議。"""
    lines: list[str] = [
        "# 相似度評估報告",
        f"> 產生時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    scored = [
        r for r in results
        if r.evaluation and r.evaluation.status == "SUCCESS" and r.evaluation.similarity_score is not None
    ]

    if scored:
        avg = sum(r.evaluation.similarity_score for r in scored) / len(scored)  # type: ignore[union-attr]
        excellent = sum(1 for r in scored if r.evaluation.similarity_score >= 80)   # type: ignore[union-attr]
        acceptable = sum(1 for r in scored if 60 <= r.evaluation.similarity_score < 80)  # type: ignore[union-attr]
        review     = sum(1 for r in scored if r.evaluation.similarity_score < 60)  # type: ignore[union-attr]

        lines += [
            "## 整體統計",
            "",
            f"| 指標 | 值 |",
            f"|------|---|",
            f"| 平均分 | {avg:.1f} / 100 |",
            f"| 優良（≥80） | {excellent} 個 KPI |",
            f"| 可接受（60～79） | {acceptable} 個 KPI |",
            f"| 需審查（<60） | {review} 個 KPI |",
            "",
        ]

    lines += ["## 各 KPI 評分詳情", ""]

    for r in results:
        lines.append(f"---\n\n### {r.kpi}")
        if not r.evaluation:
            lines += ["", "_（未進行評估）_", ""]
            continue
        if r.evaluation.status == "FAILED":
            lines += ["", f"_評估失敗：{r.evaluation.error_msg}_", ""]
            continue

        score_str = f"{r.evaluation.similarity_score}/100" if r.evaluation.similarity_score is not None else "N/A"
        lines += ["", f"**總分：{score_str}**", ""]

        if r.evaluation.raw_response:
            # 附上第三段（差異分析）和第四段（改善建議）
            diff = _extract_section(r.evaluation.raw_response, "三、")
            suggest = _extract_section(r.evaluation.raw_response, "四、")
            if diff:
                lines += ["#### 差異分析", "", diff, ""]
            if suggest:
                lines += ["#### 改善建議", "", suggest, ""]

    (run_dir / "EVALUATION_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


# ── run_config.json ───────────────────────────────────────────

def write_run_config(
    mode:           str,
    ref_factories:  list[str],
    target_factory: str,
    data_file:      str,
    kpi_filter:     list[str] | None,
    run_dir:        Path,
    extra:          dict | None = None,
) -> None:
    data = {
        "mode":           mode,
        "ref_factories":  ref_factories,
        "target_factory": target_factory,
        "data_file":      data_file,
        "kpi_filter":     kpi_filter,
        "run_dir":        str(run_dir),
        "executed_at":    datetime.now().isoformat(),
        **(extra or {}),
    }
    (run_dir / "run_config.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── 主入口 ────────────────────────────────────────────────────

def write_all(
    results:        list[KpiResult],
    mode:           str,
    ref_factories:  list[str],
    target_factory: str,
    data_file:      str,
    kpi_filter:     list[str] | None,
    run_dir:        Path,
) -> None:
    kpi_dir = run_dir / "kpis"

    for r in results:
        write_kpi_file(r, mode, kpi_dir)

    write_summary(results, mode, run_dir)
    write_generated_sqls(results, run_dir)

    if mode == "backtest":
        write_evaluation_report(results, run_dir)

    write_run_config(mode, ref_factories, target_factory, data_file, kpi_filter, run_dir)

    filelist = ["SUMMARY.md", "GENERATED_SQLS.md"]
    if mode == "backtest":
        filelist.append("EVALUATION_REPORT.md")
    filelist.append("run_config.json")
    filelist.append(f"kpis/ ({sum(1 for r in results if r.generation.status == 'SUCCESS')} 個 KPI)")

    print(f"\n[OUTPUT] 報告已輸出至：{run_dir}")
    for f in filelist:
        print(f"  └─ {f}")
