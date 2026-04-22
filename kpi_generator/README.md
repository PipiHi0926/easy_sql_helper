# KPI Generator — 使用指南

> 利用 AI LLM 自動生成台積電 AMHS KPI SQL 腳本。
> 支援兩個階段：先 Backtest 驗證 AI 品質，再正式 Generate 新廠 SQL。

---

## 目錄

1. [資料夾結構](#資料夾結構)
2. [到公司前的準備清單](#到公司前的準備清單)
3. [環境設定](#環境設定)
4. [第零步：認識你的資料](#第零步認識你的資料)
5. [第一步：設定 kpi_selection.yaml](#第一步設定-kpi_selectionyaml)
6. [第二步：Phase 1 — Backtest 驗證](#第二步phase-1--backtest-驗證)
7. [第三步：Phase 2 — Generate 正式生成](#第三步phase-2--generate-正式生成)
8. [讀懂輸出報告](#讀懂輸出報告)
9. [所有 CLI 參數總覽](#所有-cli-參數總覽)
10. [常見問題](#常見問題)

---

## 資料夾結構

```
kpi_generator/
├── run.py               ← 主程式入口（backtest / generate 兩個模式）
├── list_kpis.py         ← 列出資料檔所有 KPI 與廠區（填 yaml 前先跑這個）
├── kpi_selection.yaml   ← 選擇要跑哪些 KPI 與設定廠區（每次執行前編輯這個）
│
├── prompts/             ← AI Prompt 設定（可調整 AI 行為）
│   ├── role.md          ← AI 的角色定義（AMHS 工程師）
│   ├── generate_system.md  ← 生成 SQL 的指示（含廠區層級判別邏輯）
│   ├── generate_trigger.md ← 送給 AI 的觸發訊息模板
│   ├── evaluate_system.md  ← 評分 SQL 的指示（100 分制）
│   └── evaluate_trigger.md ← 送給 AI 評分的觸發訊息模板
│
├── _bootstrap.py        ← 路徑設定（不需修改）
├── data_loader.py       ← 資料讀取（不需修改）
├── generator.py         ← 生成邏輯（不需修改）
├── evaluator.py         ← 評分邏輯（不需修改）
├── output_writer.py     ← 報告輸出（不需修改）
├── prompt_renderer.py   ← Prompt 渲染（不需修改）
└── result_types.py      ← 資料型態定義（不需修改）
```

**你平常只需要動的檔案：**
- `kpi_selection.yaml` — 每次執行前設定廠區與 KPI 清單
- `prompts/*.md` — 若 AI 輸出品質不佳，調整 Prompt 指示

---

## 到公司前的準備清單

到公司執行前，需要準備以下東西：

### 必要資料

- [ ] **KPI 資料檔**（CSV 或 Excel）
  - 格式：三個欄位 `ITEM`、`SEQ`、`VALUE`
  - `ITEM`：廠區代號，格式為 `SQL_<廠區>`，例如 `SQL_F20P1`、`SQL_AP7`
  - `SEQ`：KPI 名稱，例如 `OHT_UTILIZATION`、`STOCKER_CAPACITY`
  - `VALUE`：該廠區、該 KPI 的完整 SQL 字串
  - 把檔案放到 `data/` 目錄下，或任意路徑（執行時指定 `--data-file`）

### 需要確認的資訊

- [ ] **LLM 連線設定**（公司 LiteLLM Proxy）
  - `LLM_BASE_URL`：API endpoint，例如 `http://your-litellm-proxy/v1`
  - `LLM_API_KEY`：API 金鑰
  - `LLM_MODEL`：模型名稱，例如 `ai-infra/MiniMaxAI/MiniMax-M2.1`

- [ ] **確認廠區代號**
  - 資料檔的 ITEM 欄位中，廠區代號長什麼樣子（有無 `SQL_` 前綴）

- [ ] **決定 Backtest 的目標廠**
  - Phase 1 Backtest 需要一個「已存在 SQL」的廠區當 Ground Truth
  - 例如：用 `SQL_F20`、`SQL_F20P1` 生成 `SQL_F20P2`，比對真實的 `SQL_F20P2`

---

## 環境設定

### 本地 Ollama（開發測試用）

預設設定即可使用，無需任何環境變數。

```bash
# 確認 Ollama 正在執行
curl http://localhost:11434/api/tags

# qwen3.x 系列需要關閉 thinking 模式才能正常輸出
set LLM_DISABLE_THINKING=true   # Windows CMD
# 或
export LLM_DISABLE_THINKING=true  # bash
```

### 公司 LLM（正式執行）

```bash
# Windows CMD
set LLM_BASE_URL=http://your-litellm-proxy/v1
set LLM_API_KEY=your_api_key
set LLM_MODEL=ai-infra/MiniMaxAI/MiniMax-M2.1

# bash / PowerShell
export LLM_BASE_URL=http://your-litellm-proxy/v1
export LLM_API_KEY=your_api_key
export LLM_MODEL=ai-infra/MiniMaxAI/MiniMax-M2.1
```

> 公司 LLM **不需要**設定 `LLM_DISABLE_THINKING`。

---

## 第零步：認識你的資料

拿到資料檔後，先執行這個指令看看裡面有什麼：

```bash
uv run python kpi_generator/list_kpis.py --data-file data/your_kpi_data.csv
```

輸出範例：
```
資料檔：data/your_kpi_data.csv
總筆數：120

── 廠區清單（ITEM 欄位）──────────────────────
  SQL_F20     (15 個 KPI)
  SQL_F20P1   (15 個 KPI)
  SQL_F20P2   (15 個 KPI)

── KPI 清單（SEQ 欄位）共 15 個 ────────────────
    1. OHT_UTILIZATION        有資料的廠區：SQL_F20, SQL_F20P1, SQL_F20P2
    2. STOCKER_CAPACITY       有資料的廠區：SQL_F20, SQL_F20P1, SQL_F20P2
   ...

── 複製以下內容到 kpi_selection.yaml 的 kpis 區塊 ──
  - name: OHT_UTILIZATION
    enabled: false
    note:
  ...
```

把最底部的 KPI 清單複製到 `kpi_selection.yaml` 的 `kpis:` 區塊。

---

## 第一步：設定 kpi_selection.yaml

每次執行前，編輯這個檔案決定要跑哪些 KPI：

```yaml
# 執行設定
run:
  mode: backtest              # 先填 backtest（驗證階段）
  ref_factories:              # 參考廠區（用於推斷，需在資料檔中有 SQL）
    - SQL_F20
    - SQL_F20P1
  target_factory: SQL_F20P2   # 目標廠（backtest：需有 Ground Truth；generate：填新廠代號）
  data_file: data/your_kpi_data.csv
  output_dir: output/

# KPI 清單：enabled: true 的才會執行
kpis:
  - name: OHT_UTILIZATION
    enabled: true
    note: 先跑這個驗證
  - name: STOCKER_CAPACITY
    enabled: false
    note: 待下次
  - name: TRANSFER_COUNT
    enabled: false
```

**常用操作：**
- 只開幾個 KPI 測試 → 把想跑的設 `enabled: true`，其他設 `false`
- 跑全部 → 全部設 `enabled: true`（或刪掉 kpis 區塊，預設跑全部）

---

## 第二步：Phase 1 — Backtest 驗證

用已知廠區的真實 SQL 測試 AI 準確度，確認 Prompt 效果後才正式生成。

### 方式一：使用 kpi_selection.yaml（推薦）

```bash
# 編輯 kpi_selection.yaml 後執行
uv run python kpi_generator/run.py backtest \
    --kpi-config kpi_generator/kpi_selection.yaml
```

### 方式二：直接用 CLI 指定

```bash
uv run python kpi_generator/run.py backtest \
    --ref-factories SQL_F20 SQL_F20P1 \
    --target-factory SQL_F20P2 \
    --data-file data/your_kpi_data.csv \
    --kpi OHT_UTILIZATION STOCKER_CAPACITY
```

### 執行過程

```
[BACKTEST] 參考廠：SQL_F20, SQL_F20P1
[BACKTEST] 目標廠（Ground Truth）：SQL_F20P2
[BACKTEST] KPI 數量：2 | 模型：MiniMax-M2.1

[  1/2] OHT_UTILIZATION 生成中... OK (23.1s) | 評估中... OK (18.4s) → 分數：88/100
[  2/2] STOCKER_CAPACITY 生成中... OK (19.8s) | 評估中... OK (17.2s) → 分數：92/100

[DONE] 生成：SUCCESS=2  FAILED=0 | 平均分：90.0/100

[OUTPUT] 報告已輸出至：output/backtest_F20_F20P1_to_SQL_F20P2_20260422_103011
```

### 怎麼判斷結果好不好？

| 平均分 | 意義 | 建議動作 |
|--------|------|---------|
| ≥ 80 | 優良，AI 推斷準確 | 可直接進行 Phase 2 生成 |
| 60～79 | 可接受，但有瑕疵 | 審閱 EVALUATION_REPORT.md，考慮補充參考廠或調整 Prompt |
| < 60 | 需要人工介入 | 檢查差異分析，可能需要補充更多參考廠的 SQL |

---

## 第三步：Phase 2 — Generate 正式生成

Backtest 結果滿意後，正式為全新廠區生成 SQL。

### 修改 kpi_selection.yaml

```yaml
run:
  mode: generate              # 改成 generate
  ref_factories:
    - SQL_F20
    - SQL_F20P1
    - SQL_F20P2               # 加入更多參考廠可提升品質
  target_factory: F20P3       # 新廠代號（不需在資料檔中存在）
  data_file: data/your_kpi_data.csv
  output_dir: output/

kpis:
  - name: OHT_UTILIZATION
    enabled: true
  # ... 其他 KPI
```

### 執行

```bash
uv run python kpi_generator/run.py generate \
    --kpi-config kpi_generator/kpi_selection.yaml
```

---

## 讀懂輸出報告

每次執行在 `output/` 下建立一個帶時間戳的目錄：

```
output/
└── backtest_F20_F20P1_to_SQL_F20P2_20260422_103011/
    ├── SUMMARY.md              ← 先看這個：所有 KPI 的狀態與分數一覽
    ├── GENERATED_SQLS.md       ← 所有 AI 生成的 SQL（含 Placeholder）
    ├── EVALUATION_REPORT.md    ← 各 KPI 的詳細評分與改善建議（backtest 才有）
    ├── run_config.json         ← 本次執行的參數紀錄
    └── kpis/
        ├── OHT_UTILIZATION.md  ← 單一 KPI 的完整報告
        └── STOCKER_CAPACITY.md
```

### 各報告的用途

**`SUMMARY.md`** — 快速掌握整批結果，每個 KPI 的成功/失敗與分數

**`GENERATED_SQLS.md`** — 工程師最常用，把所有 SQL 集中在一起：
- 含有 `{{PLACEHOLDER}}` 的地方 → 需確認後替換
- 沒有 Placeholder 的 → 可直接使用

**`EVALUATION_REPORT.md`** — 每個 KPI 的差異分析與改善建議（backtest 模式）：
- 「生成正確之處」→ 確認 AI 理解的地方
- 「差異分析」→ 找出 AI 哪裡沒推斷正確
- 「改善建議」→ 如何補充資料或調整 Prompt

**`kpis/<KPI>.md`** — 完整的 7 段式分析：
- 第一段：KPI 層級定位（整廠 vs Phase）
- 第二段：跨廠差異規律分析
- 第三段：生成 SQL（含改動明細）
- 第四段：待確認事項（✅確定 / ⚠️待確認 / ❓縮寫含意不明）

---

## 所有 CLI 參數總覽

```bash
# 基本用法
uv run python kpi_generator/run.py <backtest|generate> [參數...]

# 最常用：配合 yaml 設定檔
uv run python kpi_generator/run.py backtest --kpi-config kpi_generator/kpi_selection.yaml
uv run python kpi_generator/run.py generate --kpi-config kpi_generator/kpi_selection.yaml
```

| 參數 | 說明 | 預設 |
|------|------|------|
| `--kpi-config` | kpi_selection.yaml 路徑 | 無 |
| `--ref-factories` | 參考廠區（可多個） | 必填（或從 yaml 讀） |
| `--target-factory` | 目標廠區 | 必填（或從 yaml 讀） |
| `--kpi` | 指定 KPI（空白分隔，可多個） | 全部（或從 yaml 讀） |
| `--data-file` | 資料檔路徑 | `data/kpi_data.csv` |
| `--output-dir` | 報告輸出目錄 | `output/` |
| `--retries` | LLM 失敗重試次數 | `2` |
| `--temperature` | LLM 溫度（越低越穩定） | `0.2` |
| `--max-tokens` | 生成最大 token 數 | `4000` |
| `--eval-max-tokens` | 評估最大 token 數（backtest） | `3000` |

---

## 常見問題

**Q：到公司後，指令怎麼跑？**
```bash
# 1. 設定 LLM 環境變數
set LLM_BASE_URL=http://your-litellm/v1
set LLM_API_KEY=your_key
set LLM_MODEL=your_model

# 2. 把 KPI 資料放進 data/
# 3. 查看有哪些 KPI
uv run python kpi_generator/list_kpis.py --data-file data/your_file.csv

# 4. 填寫 kpi_selection.yaml（廠區代號、選哪些 KPI）
# 5. 先跑 backtest 驗證 AI 品質
uv run python kpi_generator/run.py backtest --kpi-config kpi_generator/kpi_selection.yaml

# 6. 確認分數可接受後，改 yaml 裡的 mode 為 generate，正式生成
uv run python kpi_generator/run.py generate --kpi-config kpi_generator/kpi_selection.yaml
```

**Q：某個 KPI 失敗，怎麼重跑？**
```bash
uv run python kpi_generator/run.py backtest \
    --ref-factories SQL_F20 SQL_F20P1 \
    --target-factory SQL_F20P2 \
    --kpi OHT_UTILIZATION
```

**Q：Backtest 分數很低怎麼辦？**
1. 查看 `EVALUATION_REPORT.md` 的「差異分析」和「改善建議」
2. 可能的原因：
   - 參考廠太少 → 補充更多廠的 SQL 到資料檔
   - Prompt 需調整 → 修改 `prompts/generate_system.md`
   - 該 KPI 的命名規律特殊 → 在 `prompts/generate_system.md` 補充說明

**Q：輸出的 SQL 有 `{{PLACEHOLDER}}`，怎麼處理？**
- 每個 Placeholder 在 `kpis/<KPI>.md` 的第四段都有說明（⚠️ 待確認項目）
- 通常需要詢問：廠區 DBA（Schema 名稱）/ 廠區工程師（業務欄位值）/ AMHS 系統管理員（特殊表名）
- 確認後直接在 `GENERATED_SQLS.md` 找到對應位置替換

**Q：如何調整 AI 的分析行為？**
- AI 角色與不猜測規則 → `prompts/role.md`
- 廠區層級判別邏輯（整廠 vs Phase）→ `prompts/generate_system.md`
- 評分維度與比重 → `prompts/evaluate_system.md`
- 修改後**不需重新安裝**，下次執行自動生效

**Q：資料檔的 ITEM 欄位沒有 `SQL_` 前綴怎麼辦？**
- `--ref-factories` 和 `--target-factory` 直接填資料中實際的值即可
- 例如資料是 `F20P1`（無前綴），就填 `--ref-factories F20P1 F20P2`
