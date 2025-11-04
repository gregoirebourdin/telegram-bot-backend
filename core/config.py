import os
from dotenv import load_dotenv
load_dotenv()

# Telegram
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME", "userbot_session")


SESSION_STRING = os.getenv("SESSION_STRING")
STATE_PATH = os.getenv("STATE_PATH", "./data/state.json")
DM_SENT_DB = os.getenv("DM_SENT_DB", "./data/dm_sent.json")
PORT = int(os.getenv("PORT", 8080))
TARGET_GROUP = os.getenv("TARGET_GROUP")


# Chatbase
CHATBASE_API_KEY = os.getenv("CHATBASE_API_KEY")
CHATBASE_BOT_ID = os.getenv("CHATBASE_BOT_ID")

# Groupe cible (ID négatif -100… recommandé)
TARGET_GROUP = (os.getenv("TARGET_GROUP") or "").strip()
AUTO_CAPTURE_GROUP = os.getenv("AUTO_CAPTURE_GROUP", "0").strip() == "1"
DEBUG_LOG_JOINS = os.getenv("DEBUG_LOG_JOINS", "0").strip() == "1"
CONFIG_PATH = "config.json"

# Delays & Limits
DM_DELAY_SECONDS   = float(os.getenv("DM_DELAY_SECONDS", "10"))
REPLY_DELAY_MIN    = float(os.getenv("REPLY_DELAY_MIN", "20"))
REPLY_DELAY_MAX    = float(os.getenv("REPLY_DELAY_MAX", "50"))
DM_SPACING_MIN     = float(os.getenv("DM_SPACING_MIN", "40"))
DM_SPACING_MAX     = float(os.getenv("DM_SPACING_MAX", "70"))
DM_MAX_PER_HOUR    = int(os.getenv("DM_MAX_PER_HOUR", "30"))
DM_SENT_DB_PATH    = os.getenv("DM_SENT_DB", "dm_sent.json")
HISTORY_MAX_TURNS  = int(os.getenv("HISTORY_MAX_TURNS", "40"))
CHATBASE_CONCURRENCY = int(os.getenv("CHATBASE_CONCURRENCY", "8"))

# Message d’accueil
WELCOME_DM = (
    "Coucou c’est Billie du Become Club ! 🥰 Trop contente de t’accueillir dans la team !\n\n"
    "Dis-moi, je suis curieuse… tu aimerais avoir quel type de résultats avec les réseaux sociaux ?\n\n"
    "Juste un complément ou remplacer ton salaire ? 😊"
)


