import os

# 設定優先順序：環境變數 > 此處預設值
# 本地測試用 Ollama；正式環境設環境變數即可切換，不需改程式碼

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY  = os.getenv("LLM_API_KEY",  "ollama")
LLM_MODEL    = os.getenv("LLM_MODEL",    "qwen3.5:4b")

DATA_FILE    = os.getenv("KPI_DATA_FILE", "data/kpi_data.csv")
