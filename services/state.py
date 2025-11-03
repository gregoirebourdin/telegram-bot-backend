# services/state.py
import json
import os
import time
from typing import Dict, Any, Optional, List

STATE_PATH = os.getenv("STATE_PATH", "state.json")

_state = {
    "muted_users": {},        # { "123456": true }
    "users": {},              # { "123456": { profile } }
    "conversations": {},      # { "123456": { "last_text": "...", "updated_at": 1234 } }
}

def _load():
    if os.path.isfile(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    _state.update(data)
        except Exception:
            pass

def _save():
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_PATH)

# init au premier import
_load()

# ---------- Muting ----------
def is_muted(user_id: int) -> bool:
    return bool(_state["muted_users"].get(str(user_id), False))

def mute_user(user_id: int):
    _state["muted_users"][str(user_id)] = True
    _save()

def unmute_user(user_id: int):
    _state["muted_users"].pop(str(user_id), None)
    _save()

def toggle_mute(user_id: int) -> bool:
    if is_muted(user_id):
        unmute_user(user_id)
        return False
    mute_user(user_id)
    return True

# ---------- Users / Conversations ----------
def upsert_user_profile(user_id: int, profile: Dict[str, Any]):
    _state["users"][str(user_id)] = {
        "id": user_id,
        "first_name": profile.get("first_name"),
        "last_name": profile.get("last_name"),
        "username": profile.get("username"),
        "phone": profile.get("phone"),
        # place pour plus tard: "photo_small": url ou path si tu la télécharges
    }
    _save()

def touch_conversation(user_id: int, last_text: Optional[str] = None):
    conv = _state["conversations"].setdefault(str(user_id), {})
    conv["user_id"] = user_id
    if last_text is not None:
        conv["last_text"] = last_text[:500]
    conv["updated_at"] = int(time.time())
    _save()

def list_conversations() -> List[Dict[str, Any]]:
    out = []
    for uid, conv in _state["conversations"].items():
        user = _state["users"].get(uid, {"id": int(uid)})
        out.append({
            "user": user,
            "conversation": conv,
            "muted": is_muted(int(uid)),
        })
    # tri du plus récent au plus ancien
    out.sort(key=lambda x: x["conversation"].get("updated_at", 0), reverse=True)
    return out
