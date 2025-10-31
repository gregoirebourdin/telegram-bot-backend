# app.py — version stable et propre, join detection + DM safe
import os
import sys
import re
import json
import time
import asyncio
import random
from typing import Optional

import httpx
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, ChatWriteForbiddenError, PeerFloodError

# --- Compatibilité Python 3.12+ ---
if sys.version_info >= (3, 12):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

# --- Chargement .env ---
load_dotenv()

# --- Identifiants Telegram ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME", "userbot_session")

# --- Chatbase ---
CHATBASE_API_KEY = os.getenv("CHATBASE_API_KEY")
CHATBASE_BOT_ID = os.getenv("CHATBASE_BOT_ID")

# --- Groupe cible ---
TARGET_GROUP = os.getenv("TARGET_GROUP", "").strip()

# --- Message de bienvenue ---
WELCOME_DM = (
    "Coucou c’est Billie du Become Club 🥰 Trop contente de t’accueillir dans la team !\n\n"
    "Dis-moi, je suis curieuse… tu aimerais avoir quel type de résultats avec les réseaux sociaux ? "
    "Juste un complément ou remplacer ton salaire ? 😊"
)

# --- Delays / Limits ---
DM_DELAY_SECONDS = float(os.getenv("DM_DELAY_SECONDS", "10"))
REPLY_DELAY_MIN = float(os.getenv("REPLY_DELAY_MIN", "20"))
REPLY_DELAY_MAX = float(os.getenv("REPLY_DELAY_MAX", "50"))
DM_SPACING_MIN = float(os.getenv("DM_SPACING_MIN", "40"))
DM_SPACING_MAX = float(os.getenv("DM_SPACING_MAX", "70"))
DM_MAX_PER_HOUR = int(os.getenv("DM_MAX_PER_HOUR", "30"))
DM_SENT_DB_PATH = os.getenv("DM_SENT_DB", "dm_sent.json")
HISTORY_MAX_TURNS = int(os.getenv("HISTORY_MAX_TURNS", "40"))
CHATBASE_CONCURRENCY = int(os.getenv("CHATBASE_CONCURRENCY", "8"))
DEBUG_LOG_JOINS = os.getenv("DEBUG_LOG_JOINS", "0").strip() == "1"

# --- Client Telegram ---
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
_chatbase_sem = asyncio.Semaphore(CHATBASE_CONCURRENCY)

# ============================================================
# ===                 UTILITAIRES LOCAUX                  ====
# ============================================================

# Résolution du groupe
TARGET_GROUP_ID_INT: Optional[int] = None
TARGET_GROUP_TITLE: Optional[str] = None


async def resolve_target_group():
    global TARGET_GROUP_ID_INT, TARGET_GROUP_TITLE
    if not TARGET_GROUP:
        return

    val = TARGET_GROUP.strip()

    # Cas ID direct
    if val.startswith("-100"):
        try:
            ent = await client.get_entity(int(val))
            TARGET_GROUP_ID_INT = int(ent.id)
            TARGET_GROUP_TITLE = getattr(ent, "title", None) or getattr(ent, "username", None)
            return
        except Exception as e:
            print(f"[ERROR] Résolution ID directe échouée : {e}")
            return

    # Cas lien ou @username
    m = re.search(r'(?:https?://t\.me/)?@?([A-Za-z0-9_]{5,})', val)
    if not m:
        print(f"[WARN] TARGET_GROUP non valide: {val}")
        return
    username = m.group(1)
    try:
        ent = await client.get_entity(username)
        TARGET_GROUP_ID_INT = int(ent.id)
        TARGET_GROUP_TITLE = getattr(ent, "title", None) or getattr(ent, "username", None)
    except Exception as e:
        print(f"[ERROR] Résolution du groupe '{val}' échouée: {e}")


# --- Base des utilisateurs déjà DM ---
_dm_sent: dict[str, float] = {}


def load_dm_sent():
    global _dm_sent
    try:
        if os.path.isfile(DM_SENT_DB_PATH):
            with open(DM_SENT_DB_PATH, "r", encoding="utf-8") as f:
                _dm_sent = json.load(f)
    except Exception:
        _dm_sent = {}


def save_dm_sent():
    try:
        with open(DM_SENT_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(_dm_sent, f)
    except Exception as e:
        print("[WARN] Sauvegarde DM_SENT_DB échouée:", e)


def has_already_dm(uid: int) -> bool:
    return str(uid) in _dm_sent


def mark_dm_sent(uid: int):
    _dm_sent[str(uid)] = time.time()
    save_dm_sent()


# ============================================================
# ===                  WORKER D'ENVOI DM                  ====
# ============================================================

_dm_queue: asyncio.Queue = asyncio.Queue()
_last_dm_ts = 0.0
_dm_sent_timestamps: list[float] = []
_backoff_seconds = 0


async def dm_worker():
    global _last_dm_ts, _dm_sent_timestamps, _backoff_seconds
    print("[DM-WORKER] Démarré")
    while True:
        user_id, text = await _dm_queue.get()
        try:
            if has_already_dm(user_id):
                _dm_queue.task_done()
                continue

            # Limite horaire
            now = time.time()
            _dm_sent_timestamps = [t for t in _dm_sent_timestamps if now - t < 3600]
            if len(_dm_sent_timestamps) >= DM_MAX_PER_HOUR:
                sleep_left = 3600 - (now - _dm_sent_timestamps[0]) + 5
                print(f"[DM] Cap/h atteint, pause {int(sleep_left)}s")
                await asyncio.sleep(sleep_left)

            if _backoff_seconds > 0:
                print(f"[DM] Backoff {int(_backoff_seconds)}s")
                await asyncio.sleep(_backoff_seconds)

            # Espacement
            since = time.time() - _last_dm_ts
            need = random.uniform(DM_SPACING_MIN, DM_SPACING_MAX)
            if since < need:
                await asyncio.sleep(need - since)

            await client.send_message(user_id, text)
            _last_dm_ts = time.time()
            _dm_sent_timestamps.append(_last_dm_ts)
            mark_dm_sent(user_id)
            print(f"[DM OK] -> {user_id}")

        except (ChatWriteForbiddenError, PeerFloodError, FloodWaitError) as e:
            print(f"[DM Error spécifique] {e}")
            _backoff_seconds = random.randint(120, 300)
        except Exception as e:
            print(f"[DM ERROR] {e}")
        finally:
            _dm_queue.task_done()


# ============================================================
# ===                  CHATBASE REPLIES                   ====
# ============================================================

_history_by_user: dict[int, list[dict]] = {}


def _get_history(uid: int):
    return _history_by_user.get(uid, [])[-HISTORY_MAX_TURNS:]


def _append_turn(uid: int, user_text: str, bot_text: Optional[str]):
    hist = _history_by_user.setdefault(uid, [])
    hist.append({"role": "user", "content": user_text})
    if bot_text:
        hist.append({"role": "assistant", "content": bot_text})


async def ask_chatbase(uid: int, text: str) -> Optional[str]:
    if not CHATBASE_API_KEY or not CHATBASE_BOT_ID:
        return None

    payload = {
        "chatbotId": CHATBASE_BOT_ID,
        "messages": _get_history(uid) + [{"role": "user", "content": text}],
        "conversationId": str(uid),
    }
    headers = {"Authorization": f"Bearer {CHATBASE_API_KEY}", "Content-Type": "application/json"}

    async with _chatbase_sem:
        async with httpx.AsyncClient(timeout=45) as http:
            r = await http.post("https://www.chatbase.co/api/v1/chat", json=payload, headers=headers)
            if r.status_code != 200:
                print("[Chatbase Error]", r.status_code, r.text)
                return None
            data = r.json()
            return data.get("text") or data.get("message")


# ============================================================
# ===                   EVENT HANDLERS                    ====
# ============================================================

@client.on(events.ChatAction)
async def on_user_join(event: events.ChatAction.Event):
    """Détecte les nouveaux membres et planifie un DM unique"""
    try:
        if TARGET_GROUP_ID_INT is None:
            return
        if event.chat_id != TARGET_GROUP_ID_INT:
            return
        if not (event.user_joined or event.user_added):
            return

        user = await event.get_user()
        uid = user.id
        if has_already_dm(uid):
            return

        async def enqueue_dm():
            await asyncio.sleep(DM_DELAY_SECONDS)
            if not has_already_dm(uid):
                await _dm_queue.put((uid, WELCOME_DM))
                print(f"[QUEUE] DM programmé -> {uid}")

        asyncio.create_task(enqueue_dm())

    except Exception as e:
        print("[ERROR on_user_join]", e)


@client.on(events.NewMessage)
async def on_private_message(event: events.NewMessage.Event):
    """Relaye les DMs vers Chatbase avec un délai naturel"""
    try:
        if event.out or not event.is_private:
            return

        sender = await event.get_sender()
        uid = sender.id
        text = (event.raw_text or "").strip()
        print(f"[DM IN] {uid}: {text[:120]}")

        delay = random.uniform(REPLY_DELAY_MIN, REPLY_DELAY_MAX)
        await asyncio.sleep(delay)
        reply = await ask_chatbase(uid, text)
        if reply:
            await client.send_message(uid, reply, reply_to=event.id)
            _append_turn(uid, text, reply)
            print(f"[DM OUT → {uid}] après {int(delay)}s")
        else:
            _append_turn(uid, text, None)
    except Exception as e:
        print("[ERROR on_private_message]", e)


# ============================================================
# ===                       MAIN                           ====
# ============================================================

async def main():
    print("Connexion à Telegram…")
    await client.start()
    me = await client.get_me()
    print(f"✅ Connecté en tant que {me.first_name} (@{me.username})")

    await resolve_target_group()
    if TARGET_GROUP_ID_INT:
        print(f"[INFO] Groupe surveillé: {TARGET_GROUP_TITLE} ({TARGET_GROUP_ID_INT})")
    else:
        print("[INFO] Aucun groupe valide trouvé. Pas d’envoi automatique.")

    load_dm_sent()
    print(f"[INFO] Utilisateurs déjà DM: {len(_dm_sent)}")

    asyncio.create_task(dm_worker())

    print("[READY] En écoute…")
    await client.run_until_disconnected()


if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
