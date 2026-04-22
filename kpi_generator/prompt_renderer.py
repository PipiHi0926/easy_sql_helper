"""
Prompt 載入與渲染。
設計原則：prompts/ 目錄下只有純 Markdown，不含 YAML frontmatter。
渲染規則：只替換 kwargs 中明確傳入的 {{KEY}}，其他 {{...}} 保持原樣。
"""
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def load(filename: str) -> str:
    """讀取 prompts/<filename>，回傳原始文字。"""
    path = _PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"找不到 prompt 檔案：{path}")
    return path.read_text(encoding="utf-8")


def render(template: str, **kwargs) -> str:
    """
    將 template 中的 {{KEY}} 替換為對應的值。
    key 比對不分大小寫（統一轉大寫）。
    kwargs 中沒有的 {{...}} 原樣保留，不會誤替換 LLM 輸出示範用的 placeholder。
    """
    for key, val in kwargs.items():
        template = template.replace(f"{{{{{key.upper()}}}}}", str(val))
    return template
