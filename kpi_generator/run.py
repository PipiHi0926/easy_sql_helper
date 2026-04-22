#!/usr/bin/env python3
"""
KPI Generator CLI
=================

兩個子命令：

  backtest  — 以已知廠區為 Ground Truth，驗證 AI 生成品質
  generate  — 為全新廠區生成 KPI SQL

範例：
  # Phase 1：用 F20、F20P1 生成 F20P2，並與真實 F20P2 比對
  uv run python kpi_generator/run.py backtest \\
      --ref-factories SQL_F20 SQL_F20P1 \\
      --target-factory SQL_F20P2

  # Phase 2：正式生成 F20P3（尚無 Ground Truth）
  uv run python kpi_generator/run.py generate \\
      --ref-factories SQL_F20 SQL_F20P1 SQL_F20P2 \\
      --target-factory F20P3

  # 只跑特定 KPI 進行快速測試
  uv run python kpi_generator/run.py backtest \\
      --ref-factories SQL_F20 SQL_F20P1 \\
      --target-factory SQL_F20P2 \\
      --kpi YIELD_RATE UTILIZATION
"""
import _bootstrap  # noqa: F401

import argparse
import sys
from pathlib import Path

import config as cfg
import data_loader as dl
import generator as gen
import evaluator as evl
import output_writer as ow
from result_types import KpiResult


def _load_kpi_config(path: str) -> dict:
    """
    載入 kpi_selection.yaml，回傳 dict。
    需要 PyYAML（pip install pyyaml）；若未安裝則提示並離開。
    """
    try:
        import yaml
    except ImportError:
        print("[ERROR] 使用 --kpi-config 需要安裝 PyYAML：pip install pyyaml", file=sys.stderr)
        sys.exit(1)
    p = Path(path)
    if not p.exists():
        print(f"[ERROR] 找不到 kpi_selection.yaml：{p}", file=sys.stderr)
        sys.exit(1)
    with p.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _apply_kpi_config(cfg_data: dict, args: argparse.Namespace) -> argparse.Namespace:
    """
    將 kpi_selection.yaml 的設定合併進 args。
    優先順序：CLI 明確指定 > yaml > 預設值。
    """
    run_cfg = cfg_data.get("run", {})
    kpis_cfg = cfg_data.get("kpis", [])

    # 只在 CLI 未明確設定時，才從 yaml 補值
    # （argparse 的 default 無法區分「使用者傳入」vs「預設值」，用 sentinel 判斷）
    if not getattr(args, "_ref_set", False) and run_cfg.get("ref_factories"):
        args.ref_factories = run_cfg["ref_factories"]
    if not getattr(args, "_target_set", False) and run_cfg.get("target_factory"):
        args.target_factory = run_cfg["target_factory"]
    if run_cfg.get("data_file") and args.data_file == cfg.DATA_FILE:
        args.data_file = run_cfg["data_file"]
    if run_cfg.get("output_dir") and args.output_dir == "output":
        args.output_dir = run_cfg["output_dir"]

    # KPI 清單：只取 enabled: true 的項目（若 CLI 未指定 --kpi）
    if args.kpi is None and kpis_cfg:
        enabled = [k["name"] for k in kpis_cfg if k.get("enabled", False)]
        if enabled:
            args.kpi = enabled
            print(f"[CONFIG] 從 kpi_selection.yaml 載入 {len(enabled)} 個 KPI：{enabled}")
        else:
            print("[WARN] kpi_selection.yaml 中沒有 enabled: true 的 KPI，將執行全部")

    return args


# ── 子命令實作 ────────────────────────────────────────────────

def run_backtest(args: argparse.Namespace) -> int:
    """
    Phase 1：以 --target-factory 的真實 SQL 為 Ground Truth，
    驗證 AI 從 --ref-factories 推斷出的 SQL 品質。
    --target-factory 必須在資料檔中已有 SQL。
    """
    df = dl.load(args.data_file)

    # 確定 KPI 清單
    all_kpis     = dl.list_kpis(df)
    kpis_to_run  = _resolve_kpis(all_kpis, args.kpi)
    if not kpis_to_run:
        print("[ERROR] 無符合條件的 KPI", file=sys.stderr)
        return 1

    print(f"\n[BACKTEST] 參考廠：{', '.join(args.ref_factories)}")
    print(f"[BACKTEST] 目標廠（Ground Truth）：{args.target_factory}")
    print(f"[BACKTEST] KPI 數量：{len(kpis_to_run)} | 模型：{cfg.LLM_MODEL}\n")

    run_dir = ow.make_run_dir(args.output_dir, "backtest", args.ref_factories, args.target_factory)
    results: list[KpiResult] = []
    total = len(kpis_to_run)

    for i, kpi in enumerate(kpis_to_run, 1):
        # ── 取得參考資料 ──
        ref_rows   = dl.get_reference_rows(df, kpi, args.ref_factories)
        actual_sql = dl.get_actual_sql(df, kpi, args.target_factory)

        if not ref_rows:
            print(f"[{i:>3}/{total}] {kpi} SKIP — 參考廠無此 KPI 資料")
            continue
        if actual_sql is None:
            print(f"[{i:>3}/{total}] {kpi} SKIP — 目標廠無此 KPI 的 Ground Truth")
            continue

        # ── Step 1：生成 ──
        print(f"[{i:>3}/{total}] {kpi} 生成中...", end=" ", flush=True)
        g_result = gen.generate(
            kpi, args.ref_factories, args.target_factory, ref_rows,
            temperature=args.temperature, max_tokens=args.max_tokens, max_retries=args.retries,
        )
        if g_result.status == "SUCCESS":
            print(f"OK ({g_result.duration_sec:.1f}s)", end=" | ", flush=True)
        else:
            print(f"FAILED ({g_result.error_msg})")
            results.append(KpiResult(kpi=kpi, generation=g_result, evaluation=None, actual_sql=actual_sql))
            continue

        # ── Step 2：評估 ──
        generated_sql = gen.extract_generated_sql(g_result) or ""
        print("評估中...", end=" ", flush=True)
        e_result = evl.evaluate(
            kpi, args.target_factory, generated_sql, actual_sql,
            temperature=args.temperature, max_tokens=args.eval_max_tokens, max_retries=args.retries,
        )
        score_str = f"{e_result.similarity_score}/100" if e_result.similarity_score is not None else "N/A"
        if e_result.status == "SUCCESS":
            print(f"OK ({e_result.duration_sec:.1f}s) → 分數：{score_str}")
        else:
            print(f"FAILED ({e_result.error_msg})")

        results.append(KpiResult(kpi=kpi, generation=g_result, evaluation=e_result, actual_sql=actual_sql))

    if not results:
        print("[WARN] 沒有任何結果可輸出")
        return 1

    _print_batch_summary(results, "backtest")
    ow.write_all(results, "backtest", args.ref_factories, args.target_factory,
                 args.data_file, args.kpi, run_dir)
    return 0


def run_generate(args: argparse.Namespace) -> int:
    """
    Phase 2：為全新廠區生成 KPI SQL（無 Ground Truth 驗證）。
    """
    df = dl.load(args.data_file)

    all_kpis    = dl.list_kpis(df)
    kpis_to_run = _resolve_kpis(all_kpis, args.kpi)
    if not kpis_to_run:
        print("[ERROR] 無符合條件的 KPI", file=sys.stderr)
        return 1

    print(f"\n[GENERATE] 參考廠：{', '.join(args.ref_factories)}")
    print(f"[GENERATE] 目標廠：{args.target_factory}")
    print(f"[GENERATE] KPI 數量：{len(kpis_to_run)} | 模型：{cfg.LLM_MODEL}\n")

    run_dir = ow.make_run_dir(args.output_dir, "generate", args.ref_factories, args.target_factory)
    results: list[KpiResult] = []
    total = len(kpis_to_run)

    for i, kpi in enumerate(kpis_to_run, 1):
        ref_rows = dl.get_reference_rows(df, kpi, args.ref_factories)
        if not ref_rows:
            print(f"[{i:>3}/{total}] {kpi} SKIP — 參考廠無此 KPI 資料")
            continue

        print(f"[{i:>3}/{total}] {kpi} ...", end=" ", flush=True)
        g_result = gen.generate(
            kpi, args.ref_factories, args.target_factory, ref_rows,
            temperature=args.temperature, max_tokens=args.max_tokens, max_retries=args.retries,
        )
        if g_result.status == "SUCCESS":
            print(f"OK ({g_result.duration_sec:.1f}s)")
        else:
            print(f"FAILED ({g_result.error_msg})")

        results.append(KpiResult(kpi=kpi, generation=g_result, evaluation=None, actual_sql=None))

    if not results:
        print("[WARN] 沒有任何結果可輸出")
        return 1

    _print_batch_summary(results, "generate")
    ow.write_all(results, "generate", args.ref_factories, args.target_factory,
                 args.data_file, args.kpi, run_dir)
    return 0


# ── Helpers ───────────────────────────────────────────────────

def _resolve_kpis(all_kpis: list[str], kpi_filter: list[str] | None) -> list[str]:
    if not kpi_filter:
        return all_kpis
    missing = [k for k in kpi_filter if k not in all_kpis]
    if missing:
        print(f"[WARN] 以下 KPI 在資料中找不到，已略過：{missing}")
    return [k for k in kpi_filter if k in all_kpis]


def _print_batch_summary(results: list[KpiResult], mode: str) -> None:
    success = sum(1 for r in results if r.generation.status == "SUCCESS")
    failed  = sum(1 for r in results if r.generation.status == "FAILED")
    print(f"\n[DONE] 生成：SUCCESS={success}  FAILED={failed}", end="")
    if mode == "backtest":
        scored = [r for r in results if r.evaluation and r.evaluation.similarity_score is not None]
        if scored:
            avg = sum(r.evaluation.similarity_score for r in scored) / len(scored)  # type: ignore[union-attr]
            print(f" | 平均分：{avg:.1f}/100 ({len(scored)} 個 KPI)", end="")
    print()


# ── Argparse ──────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KPI SQL 生成工具（無 UI）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    # 共用參數
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--kpi-config",     default=None, metavar="YAML",
                        help="kpi_selection.yaml 路徑，用於設定廠區與 KPI 清單（優先順序低於其他 CLI 參數）")
    shared.add_argument("--ref-factories",  nargs="+", metavar="FACTORY", default=None,
                        help="參考廠區代號（可多個），例如：SQL_F20 SQL_F20P1")
    shared.add_argument("--target-factory", metavar="FACTORY", default=None,
                        help="目標廠區代號")
    shared.add_argument("--kpi",            nargs="+", metavar="KPI", default=None,
                        help="指定 KPI（省略則全部）")
    shared.add_argument("--data-file",      default=cfg.DATA_FILE,
                        help=f"KPI 資料檔路徑（預設：{cfg.DATA_FILE}）")
    shared.add_argument("--output-dir",     default="output",
                        help="報告輸出根目錄（預設：output/）")
    shared.add_argument("--retries",        type=int,   default=2,   metavar="N",
                        help="LLM 失敗重試次數（預設：2）")
    shared.add_argument("--temperature",    type=float, default=0.2,
                        help="LLM 溫度（預設：0.2）")
    shared.add_argument("--max-tokens",     type=int,   default=4000,
                        help="生成 LLM 最大 token 數（預設：4000）")

    # backtest 子命令
    p_bt = sub.add_parser("backtest", parents=[shared],
                           help="Phase 1：生成 + 與 Ground Truth 比對評分")
    p_bt.add_argument("--eval-max-tokens", type=int, default=3000,
                      help="評估 LLM 最大 token 數（預設：3000）")

    # generate 子命令
    sub.add_parser("generate", parents=[shared],
                   help="Phase 2：為全新廠區生成 KPI SQL")

    return parser


def main() -> int:
    parser = _build_parser()
    args   = parser.parse_args()

    # 套用 kpi_selection.yaml（若有指定）
    if args.kpi_config:
        cfg_data = _load_kpi_config(args.kpi_config)
        args = _apply_kpi_config(cfg_data, args)

    # 驗證必要參數
    if not args.ref_factories:
        print("[ERROR] 必須透過 --ref-factories 或 kpi_selection.yaml 指定參考廠區", file=sys.stderr)
        return 1
    if not args.target_factory:
        print("[ERROR] 必須透過 --target-factory 或 kpi_selection.yaml 指定目標廠區", file=sys.stderr)
        return 1

    # generate 模式補上 eval_max_tokens
    if not hasattr(args, "eval_max_tokens"):
        args.eval_max_tokens = 3000

    try:
        if args.mode == "backtest":
            return run_backtest(args)
        else:
            return run_generate(args)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n[ABORT] 使用者中斷", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
