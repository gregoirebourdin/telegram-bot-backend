import json, os
from core.config import STATE_PATH, DM_SENT_DB

def ensure_file(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump({}, f)

def load_dm_sent():
    ensure_file(DM_SENT_DB)
    with open(DM_SENT_DB, "r") as f:
        return json.load(f)

def save_dm_sent(data):
    ensure_file(DM_SENT_DB)
    with open(DM_SENT_DB, "w") as f:
        json.dump(data, f, indent=2)

def get_state():
    ensure_file(STATE_PATH)
    with open(STATE_PATH, "r") as f:
        return json.load(f)
