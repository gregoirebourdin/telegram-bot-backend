import os
import json

DATA_DIR = "data"
DM_SENT_FILE = os.path.join(DATA_DIR, "dm_sent.json")
CONVERSATIONS_FILE = os.path.join(DATA_DIR, "conversations.json")


def init_storage():
    """Crée les fichiers de stockage s’ils n’existent pas."""
    os.makedirs(DATA_DIR, exist_ok=True)

    if not os.path.exists(DM_SENT_FILE):
        with open(DM_SENT_FILE, "w") as f:
            json.dump([], f)

    if not os.path.exists(CONVERSATIONS_FILE):
        with open(CONVERSATIONS_FILE, "w") as f:
            json.dump([], f)


def load_dm_sent():
    """Charge la liste des DMs déjà envoyés."""
    if not os.path.exists(DM_SENT_FILE):
        return []
    with open(DM_SENT_FILE, "r") as f:
        return json.load(f)


def save_dm_sent(data):
    """Sauvegarde la liste des DMs envoyés."""
    with open(DM_SENT_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_conversations():
    """Charge les conversations sauvegardées."""
    if not os.path.exists(CONVERSATIONS_FILE):
        return []
    with open(CONVERSATIONS_FILE, "r") as f:
        return json.load(f)


def save_conversations(conversations):
    """Sauvegarde les conversations."""
    with open(CONVERSATIONS_FILE, "w") as f:
        json.dump(conversations, f, indent=2)
