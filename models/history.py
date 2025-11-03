from typing import Dict, List
from core.config import HISTORY_MAX_TURNS

# mémoire en RAM (simple et rapide)
_history_by_user: Dict[int, List[dict]] = {}

def get_history(uid: int) -> List[dict]:
    hist = _history_by_user.get(uid, [])
    return hist[-HISTORY_MAX_TURNS*2:].copy()

def append_turn(uid: int, user_text: str, bot_text: str | None):
    lst = _history_by_user.setdefault(uid, [])
    lst.append({"role": "user", "content": user_text})
    if bot_text:
        lst.append({"role": "assistant", "content": bot_text})
    if len(lst) > HISTORY_MAX_TURNS*2:
        _history_by_user[uid] = lst[-HISTORY_MAX_TURNS*2:]
