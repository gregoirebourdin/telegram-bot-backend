import os
import json

DATA_DIR = "data"
CONVERSATIONS_FILE = os.path.join(DATA_DIR, "conversations.json")
DM_SENT_FILE = os.path.join(DATA_DIR, "dm_sent.json")


def init_storage():
    """Crée les dossiers et fichiers de base au démarrage."""
    os.makedirs(DATA_DIR, exist_ok=True)

    for file_path in [CONVERSATIONS_FILE, DM_SENT_FILE]:
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump([], f)
    print(f"[STORAGE] Initialisé dans {DATA_DIR}")


# ----------- CONVERSATIONS -----------
def load_conversations():
    """Charge les conversations depuis le fichier JSON."""
    try:
        with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[STORAGE] Erreur de lecture (conversations): {e}")
        return []


def save_conversations(conversations):
    """Sauvegarde les conversations dans le fichier JSON."""
    try:
        with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(conversations, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[STORAGE] Erreur de sauvegarde (conversations): {e}")


# ----------- DM SENT TRACKING -----------
def load_dm_sent():
    """Charge la liste des utilisateurs déjà DM."""
    try:
        with open(DM_SENT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[STORAGE] Erreur de lecture (dm_sent): {e}")
        return []


def save_dm_sent(dm_sent_list):
    """Sauvegarde la liste des utilisateurs déjà DM."""
    try:
        with open(DM_SENT_FILE, "w", encoding="utf-8") as f:
            json.dump(dm_sent_list, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[STORAGE] Erreur de sauvegarde (dm_sent): {e}")
