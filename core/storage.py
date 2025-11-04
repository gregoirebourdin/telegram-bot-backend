import os
import json

DATA_DIR = "data"
CONVERSATIONS_FILE = os.path.join(DATA_DIR, "conversations.json")


def init_storage():
    """Crée les dossiers et fichiers de base au démarrage."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CONVERSATIONS_FILE):
        with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
    print(f"[STORAGE] Initialisé dans {DATA_DIR}")


def load_conversations():
    """Charge les conversations depuis le fichier JSON."""
    try:
        with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[STORAGE] Erreur de lecture : {e}")
        return []


def save_conversations(conversations):
    """Sauvegarde les conversations dans le fichier JSON."""
    try:
        with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(conversations, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[STORAGE] Erreur de sauvegarde : {e}")
