"""將父目錄（sql_helper/）加入 sys.path，使本模組可 import config、llm_client。"""
import sys
from pathlib import Path

_parent = str(Path(__file__).parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)
