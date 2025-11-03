import json
import os
import time
from typing import Optional, Tuple
from .config import DM_SENT_DB_PATH, CONFIG_PATH

# ---------- DM sent persistence ----------
_dm_sent_cache = {}

def load_dm_sent():
    """Charge la base locale des utilisateurs déjà DM."""
    try:
        if os.path.isfile(DM_SENT_DB_PATH):
            with open(DM_SENT_DB_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}
    except Exception:
        data = {}
    _dm_sent_cache.clear()
    _dm_sent_cache.update(data)
    # expose pour logs dans app.py
    load_dm_sent.cache = _dm_sent_cache
    return _dm_sent_cache
load_dm_sent.cache = _dm_sent_cache

def save_dm_sent():
    try:
        with open(DM_SENT_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(_dm_sent_cache, f)
    except Exception as e:
        print("[WARN] Sauvegarde DM_SENT_DB échouée:", e)

def has_already_dm(uid: int) -> bool:
    return str(uid) in _dm_sent_cache

def mark_dm_sent(uid: int):
    _dm_sent_cache[str(uid)] = time.time()
    save_dm_sent()

# ---------- optional group config (autocapture) ----------
def load_group_config() -> Tuple[Optional[int], Optional[str]]:
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                gid = data.get("target_group_id_int")
                title = data.get("target_group_title")
                return (int(gid) if gid is not None else None, title)
        except Exception:
            return None, None
    return None, None

def save_group_config(gid: int, title: Optional[str]):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"target_group_id_int": gid, "target_group_title": title}, f, indent=2)
    except Exception as e:
        print("[WARN] Impossible d'écrire config.json:", e)
