# Easy SQL Helper

> 基於 LLM 的 KPI SQL 輔助工具，協助工程師快速比對跨廠區 SQL 邏輯、產生通用樣板並進行互動式問答。

---

## 功能概覽

| 模式 | 說明 |
|------|------|
| **模式一：KPI 跨廠分析** | 選擇一個 KPI 與多個廠區，AI 自動比對各廠 SQL 差異、歸納共通邏輯並產生通用樣板 |
| **模式二：SQL 直接輸入** | 貼上任意 SQL，AI 梳理邏輯結構、識別潛在風險並產生通用樣板 |
| **互動問答** | 首次分析完成後可持續追問，AI 保持上下文進行多輪對話 |

---

## 快速開始

### 1. 安裝套件

```bash
pip install -r requirements.txt
```

### 2. 準備資料

將 KPI SQL 資料放至 `data/` 目錄，支援 `.csv` 與 `.xlsx`，格式如下：

| 欄位 | 說明 | 範例 |
|------|------|------|
| `ITEM` | 廠區代號 | `SQL_FAB01` |
| `SEQ` | KPI 名稱 | `YIELD_RATE` |
| `VALUE` | 對應的 SQL 語句 | `SELECT lot_id, ...` |

專案內附 `data/kpi_data.csv` 範例資料可直接測試。

### 3. 設定 LLM 連線

**本地測試（Ollama）**

確認已安裝 [Ollama](https://ollama.com) 並拉取模型：

```bash
ollama pull qwen3.5:4b
```

預設即連接 `http://localhost:11434/v1`，無需額外設定。

**公司 LLM（LiteLLM Proxy）**

透過環境變數覆蓋設定：

```bash
# Windows
set LLM_BASE_URL=http://your-litellm-proxy/v1
set LLM_API_KEY=your_api_key
set LLM_MODEL=your_model_name

# macOS / Linux
export LLM_BASE_URL=http://your-litellm-proxy/v1
export LLM_API_KEY=your_api_key
export LLM_MODEL=your_model_name
```

### 4. 啟動

```bash
streamlit run app.py
```

瀏覽器開啟 `http://localhost:8501`

---

## 使用流程

### 模式一：KPI 跨廠分析

1. 點選 **「模式一：KPI 跨廠分析」** 頁籤
2. 在 **KPI 名稱** 下拉選單中搜尋並選取目標 KPI
3. 在 **參考廠區** 選單中選取一個或多個廠區
4. 確認顯示找到的 SQL 筆數後，點擊 **「🚀 開始分析」**
5. AI 會依序輸出：邏輯摘要 → 廠區差異對照表 → 通用 SQL 樣板 → 樣板說明 → 後續問答建議
6. 可在底部輸入框持續追問

![模式一流程](docs/mode1_flow.png)

### 模式二：SQL 直接輸入

1. 點選 **「模式二：SQL 直接輸入」** 頁籤
2. 將 SQL 貼入文字框
3. 點擊 **「🚀 開始分析」**
4. AI 會輸出：邏輯梳理 → 潛在風險分析 → 通用 SQL 樣板 → 樣板說明 → 後續問答建議
5. 可繼續追問調整樣板或詢問優化方式

### 重新開始

對話頁右上角點擊 **「🔄 重新開始」** 即可清空對話，回到模式選擇頁。

---

## 專案結構

```
easy_sql_helper/
├── app.py            # Streamlit 主程式（UI 與對話狀態管理）
├── llm_client.py     # LLM API 封裝（chat_complete / chat_stream）
├── prompts.py        # 所有 Prompt 統一管理（角色定義、格式規則、模式 Prompt）
├── config.py         # 設定（讀取環境變數，含 Ollama 預設值）
├── requirements.txt
└── data/
    └── kpi_data.csv  # KPI SQL 參考資料（ITEM / SEQ / VALUE）
```

---

## Prompt 樣板輸出格式

每次首次分析，AI 固定輸出以下五個段落：

```
## 一、邏輯摘要
## 二、結構分析（含廠區差異對照表 或 潛在風險）
## 三、通用 SQL 樣板
## 四、樣板使用說明
## 五、後續問答建議
```

Placeholder 格式統一為 `{{UPPER_SNAKE_CASE}}`，例如 `{{FAB_SCHEMA}}`、`{{START_DATE}}`。

---

## 環境變數

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `LLM_BASE_URL` | `http://localhost:11434/v1` | LLM API 端點 |
| `LLM_API_KEY` | `ollama` | API 金鑰 |
| `LLM_MODEL` | `qwen3.5:4b` | 模型名稱 |
| `KPI_DATA_FILE` | `data/kpi_data.csv` | KPI 資料檔路徑 |

---

## 修改 Prompt

所有 Prompt 集中在 `prompts.py`，調整時無需動其他程式碼：

- **角色調整**：修改 `ROLE_DEFINITION`
- **輸出格式**：修改 `FORMAT_RULES`
- **模式一邏輯**：修改 `mode1_system()`
- **模式二邏輯**：修改 `MODE2_SYSTEM`
- **追問行為**：修改 `FOLLOWUP_REMINDER`
