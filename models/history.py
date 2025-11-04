import os
import json

DATA_PATH = os.getenv("STATE_PATH", "/data/state.json")

# Mémoire temporaire (utilisée entre sauvegardes)
_histories = {}

def get_history(uid: int):
    return _histories.get(uid, [])

def append_message(uid: int, role: str, content: str):
    if uid not in _histories:
        _histories[uid] = []
    _histories[uid].append({"role": role, "content": content})
    _persist()

def _persist():
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w") as f:
        json.dump(_histories, f, ensure_ascii=False, indent=2)
