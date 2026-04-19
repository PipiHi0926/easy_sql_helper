import streamlit as st
import pandas as pd
from pathlib import Path
import config
import prompts
import llm_client

# ── 資料載入 ──────────────────────────────────────────────────
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    p = Path(path)
    if p.suffix in (".xlsx", ".xls"):
        return pd.read_excel(p)
    return pd.read_csv(p)


# ── LLM streaming（委託給 llm_client.py）─────────────────────
def stream_chat(messages: list):
    yield from llm_client.chat_stream(messages)


# ── Prompt 建立（委託給 prompts.py）──────────────────────────
def build_mode1(df: pd.DataFrame, kpi: str, factories: list) -> tuple[str, str, str]:
    filtered = df[(df["SEQ"] == kpi) & (df["ITEM"].isin(factories))]
    rows = filtered[["ITEM", "VALUE"]].to_dict("records")
    system = prompts.mode1_system(kpi, rows)
    label  = f"📊 KPI：**{kpi}** ｜ 廠區：{', '.join(factories)}"
    return system, prompts.MODE1_TRIGGER, label


def build_mode2(sql_text: str) -> tuple[str, str, str]:
    preview = sql_text[:60].replace("\n", " ") + ("..." if len(sql_text) > 60 else "")
    label   = f"📝 SQL 輸入：`{preview}`"
    return prompts.MODE2_SYSTEM, prompts.mode2_trigger(sql_text), label


# ── Session state 初始化 ───────────────────────────────────────
def init_state():
    defaults = {
        "messages": [],
        "system_prompt": "",
        "context_label": "",
        "chat_active": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def start_analysis(system: str, trigger: str, label: str):
    st.session_state.system_prompt = system
    st.session_state.context_label = label
    st.session_state.messages = [{"role": "user", "content": trigger}]
    st.session_state.chat_active = True
    st.rerun()


def reset():
    for k in ["messages", "system_prompt", "context_label", "chat_active"]:
        del st.session_state[k]
    st.rerun()


# ── 頁面設定 ───────────────────────────────────────────────────
st.set_page_config(page_title="KPI SQL 輔助工具", page_icon="🔍", layout="wide")
init_state()

try:
    df = load_data(config.DATA_FILE)
except FileNotFoundError:
    st.error(f"找不到資料檔案：{config.DATA_FILE}")
    st.stop()

all_kpis      = sorted(df["SEQ"].dropna().unique().tolist())
all_factories = sorted(df["ITEM"].dropna().unique().tolist())


# ════════════════════════════════════════════════════════════════
# 模式選擇頁（尚未開始分析）
# ════════════════════════════════════════════════════════════════
if not st.session_state.chat_active:

    st.title("🔍 KPI SQL 輔助工具")
    st.caption(f"模型：`{config.LLM_MODEL}` ｜ 資料：`{config.DATA_FILE}`")
    st.divider()

    tab1, tab2 = st.tabs(["📊 模式一：KPI 跨廠分析", "📝 模式二：SQL 直接輸入"])

    # ── 模式一 ──────────────────────────────────────────────────
    with tab1:
        st.markdown("選擇一個 **KPI** 與多個 **廠區**，AI 將自動比對 SQL 邏輯、歸納差異並產生通用樣板。")
        st.write("")

        col1, col2 = st.columns([1, 2])
        with col1:
            kpi_choice = st.selectbox(
                "KPI 名稱",
                options=all_kpis,
                index=None,
                placeholder="輸入關鍵字搜尋...",
            )
        with col2:
            factory_choices = st.multiselect(
                "參考廠區（可多選）",
                options=all_factories,
                placeholder="輸入關鍵字搜尋廠區...",
            )

        # 即時預覽筆數
        if kpi_choice and factory_choices:
            match_count = len(df[(df["SEQ"] == kpi_choice) & (df["ITEM"].isin(factory_choices))])
            st.info(f"找到 **{match_count}** 筆 SQL 參考資料", icon="ℹ️")

        if st.button("🚀 開始分析", type="primary", key="btn1",
                     disabled=not kpi_choice or not factory_choices):
            system, trigger, label = build_mode1(df, kpi_choice, factory_choices)
            start_analysis(system, trigger, label)

    # ── 模式二 ──────────────────────────────────────────────────
    with tab2:
        st.markdown("直接貼上 **SQL 內容**，AI 將自動梳理邏輯結構並產生通用樣板。")
        st.write("")

        sql_input = st.text_area(
            "SQL 內容",
            placeholder="將 SQL 貼在此處...",
            height=220,
        )

        if st.button("🚀 開始分析", type="primary", key="btn2",
                     disabled=not (sql_input or "").strip()):
            system, trigger, label = build_mode2(sql_input.strip())
            start_analysis(system, trigger, label)


# ════════════════════════════════════════════════════════════════
# 對話頁（分析進行中）
# ════════════════════════════════════════════════════════════════
else:

    # 頁首：背景資訊 + 重置按鈕
    col_info, col_btn = st.columns([5, 1])
    with col_info:
        st.markdown(st.session_state.context_label)
    with col_btn:
        if st.button("🔄 重新開始"):
            reset()

    st.divider()

    # 渲染歷史對話
    for msg in st.session_state.messages:
        # 第一則 user 觸發訊息簡化顯示
        if msg["role"] == "user" and msg == st.session_state.messages[0]:
            with st.chat_message("user"):
                st.markdown("_（已送出分析請求）_")
        else:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # 若最後一則為 user，自動觸發 AI 回覆
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        with st.chat_message("assistant"):
            # 第一次回答用原始 system prompt；追問階段附加 FOLLOWUP_REMINDER
            is_followup = len(st.session_state.messages) > 1
            sys_content = (
                prompts.build_followup_system(st.session_state.system_prompt)
                if is_followup
                else st.session_state.system_prompt
            )
            llm_messages = (
                [{"role": "system", "content": sys_content}]
                + st.session_state.messages
            )
            response = st.write_stream(stream_chat(llm_messages))
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

    # 追問輸入
    if follow_up := st.chat_input("繼續追問，例如：如何加入時間範圍參數？"):
        st.session_state.messages.append({"role": "user", "content": follow_up})
        st.rerun()
