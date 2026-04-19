# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
# Install dependencies
pip install -r requirements.txt

# Start (local Ollama default)
streamlit run app.py

# Start with company LLM
set LLM_BASE_URL=http://litellm-db.nv.example.v1
set LLM_API_KEY=your_key
set LLM_MODEL=ai-infra/MiniMaxAI/MiniMax-M2.1
streamlit run app.py
```

## Architecture

```
config.py      → All settings; reads env vars first, falls back to Ollama defaults
llm_client.py  → Wraps OpenAI SDK; exposes chat_complete() and chat_stream()
prompts.py     → All LLM prompts as constants/functions; single source of truth
app.py         → Streamlit UI; delegates LLM calls to llm_client, prompts to prompts.py
data/          → CSV or Excel KPI reference data (ITEM, SEQ, VALUE columns)
```

### Data format

`data/kpi_data.csv` has three columns:
- `ITEM` — factory site code (e.g. `SQL_FAB01`)
- `SEQ` — KPI name (e.g. `YIELD_RATE`)
- `VALUE` — the SQL string for that KPI at that site

Supports `.csv` and `.xlsx`; controlled by `KPI_DATA_FILE` env var or `config.DATA_FILE`.

### Two analysis modes

**Mode 1 (KPI cross-factory):** User selects one KPI + multiple factories → rows filtered from CSV → injected into `mode1_system()` as context → LLM compares SQL across factories and produces a universal template.

**Mode 2 (SQL direct input):** User pastes raw SQL → passed to `mode2_trigger()` → LLM analyzes and produces a universal template.

Both modes then enter a persistent chat loop using `st.session_state.messages`. The system prompt is fixed at analysis start and reused for all follow-up turns (with `FOLLOWUP_REMINDER` appended after turn 1).

### Prompt structure (`prompts.py`)

`ROLE_DEFINITION` and `FORMAT_RULES` are shared constants composed into mode-specific system prompts. `FORMAT_RULES` enforces a strict five-section output (邏輯摘要 / 結構分析 / 通用SQL樣板 / 樣板說明 / 後續建議) to keep first responses consistent. Placeholder convention in generated SQL templates is `{{UPPER_SNAKE_CASE}}`.

When adding a new analysis mode, follow the same pattern: a `modeN_system()` builder function + a `modeN_trigger()` function, both composed from the shared constants.

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_BASE_URL` | `http://localhost:11434/v1` | LiteLLM proxy or Ollama endpoint |
| `LLM_API_KEY` | `ollama` | API key |
| `LLM_MODEL` | `qwen3.5:4b` | Model identifier |
| `KPI_DATA_FILE` | `data/kpi_data.csv` | Path to KPI reference data |
