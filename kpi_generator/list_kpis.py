#!/usr/bin/env python3
"""
list_kpis.py — 列出資料檔中的所有 KPI 與廠區，幫助填寫 kpi_selection.yaml
用法：uv run python kpi_generator/list_kpis.py [--data-file data/kpi_data.csv]
"""
import _bootstrap  # noqa: F401
import argparse
import config
import data_loader as dl


def main():
    p = argparse.ArgumentParser(description="列出資料檔中所有 KPI 與廠區")
    p.add_argument("--data-file", default=config.DATA_FILE,
                   help=f"資料檔路徑（預設：{config.DATA_FILE}）")
    args = p.parse_args()

    df = dl.load(args.data_file)
    kpis = dl.list_kpis(df)
    factories = dl.list_factories(df)

    print(f"\n資料檔：{args.data_file}")
    print(f"總筆數：{len(df)}\n")

    print("── 廠區清單（ITEM 欄位） ─────────────────────")
    for f in factories:
        count = len(df[df["ITEM"] == f])
        print(f"  {f}  ({count} 個 KPI)")

    print(f"\n── KPI 清單（SEQ 欄位）共 {len(kpis)} 個 ────────────────")
    for i, kpi in enumerate(kpis, 1):
        fabs = sorted(df[df["SEQ"] == kpi]["ITEM"].unique().tolist())
        print(f"  {i:>3}. {kpi:<30} 有資料的廠區：{', '.join(fabs)}")

    print("\n── 複製以下內容到 kpi_selection.yaml 的 kpis 區塊 ─")
    for kpi in kpis:
        print(f"  - name: {kpi}")
        print(f"    enabled: false")
        print(f"    note: ")


if __name__ == "__main__":
    main()
