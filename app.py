# app.py — robuste, safe Telegram, auto-reconnect, Chatbase historique

import os
os.environ["TG_FORCE_IPV4"] = "1"  # Stabilise certaines connexions (évite Errno 104)

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
from telethon.errors import FloodWaitError, ChatWriteForbiddenError, PeerFloodError, TypeNotFoundError

from telethon.network.mtprotosender import MTProtoSender

_old_handle = MTProtoSender._handle_rpc_result

async def _safe_handle(self, *args, **kwargs):
    try:
        return await _old_handle(self, *args, **kwargs)
    except TypeNotFoundError as e:
        print(f"[WARN] Objet MTProto inconnu ignoré: {e}")
        return None

MTProtoSender._handle_rpc_result = _safe_handle

# ---------- Compat Python >= 3.12 ----------
if sys.version_info >= (3, 12):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
# -------------------------------------------

load_dotenv()

# --- Identifiants Telegram ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME", "userbot_session")

# --- Chatbase ---
CHATBASE_API_KEY = os.getenv("CHATBASE_API_KEY")
CHATBASE_BOT_ID = os.getenv("CHATBASE_BOT_ID")

# --- Groupe cible ---
TARGET_GROUP = (os.getenv("TARGET_GROUP") or "").strip()  # ID -100..., @username, ou lien t.me/xxx
AUTO_CAPTURE_GROUP = os.getenv("AUTO_CAPTURE_GROUP", "0").strip() == "1"
CONFIG_PATH = "config.json"                               # persiste l'ID de groupe auto-capturé
DEBUG_LOG_JOINS = os.getenv("DEBUG_LOG_JOINS", "0").strip() == "1"

# --- Message d'accueil ---
WELCOME_DM = (
    "Coucou c’est Billie du Become Club ! 🥰 Trop contente de t’accueillir dans la team !\n\n"
    "Dis-moi, je suis curieuse… tu aimerais avoir quel type de résultats avec les réseaux sociaux ?\n\n"
    "Juste un complément ou remplacer ton salaire ? 😊"
)

# --- Delays / Limits ---
DM_DELAY_SECONDS   = float(os.getenv("DM_DELAY_SECONDS", "10"))
REPLY_DELAY_MIN    = float(os.getenv("REPLY_DELAY_MIN", "20"))
REPLY_DELAY_MAX    = float(os.getenv("REPLY_DELAY_MAX", "50"))
DM_SPACING_MIN     = float(os.getenv("DM_SPACING_MIN", "40"))
DM_SPACING_MAX     = float(os.getenv("DM_SPACING_MAX", "70"))
DM_MAX_PER_HOUR    = int(os.getenv("DM_MAX_PER_HOUR", "30"))
DM_SENT_DB_PATH    = os.getenv("DM_SENT_DB", "dm_sent.json")
HISTORY_MAX_TURNS  = int(os.getenv("HISTORY_MAX_TURNS", "40"))
CHATBASE_CONCURRENCY = int(os.getenv("CHATBASE_CONCURRENCY", "8"))

# --- Client Telegram avec retries et flood management ---
client = TelegramClient(
    SESSION_NAME, API_ID, API_HASH,
    connection_retries=999,   # réessaie indéfiniment
    retry_delay=2,            # délai entre tentatives
    request_retries=5,        # retries des requêtes
    flood_sleep_threshold=30, # laisse Telethon dormir automatiquement si FloodWait long
)
_chatbase_sem = asyncio.Semaphore(CHATBASE_CONCURRENCY)

# =========================================================
# Config persistante (auto-capture du groupe si souhaitée)
# =========================================================
TARGET_GROUP_ID_INT: Optional[int] = None
TARGET_GROUP_TITLE: Optional[str] = None

def _load_config_group():
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                gid = data.get("target_group_id_int")
                title = data.get("target_group_title")
                return gid, title
        except Exception:
            return None, None
    return None, None

def _save_config_group(gid: int, title: Optional[str]):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"target_group_id_int": gid, "target_group_title": title}, f, indent=2)
    except Exception as e:
        print("[WARN] Impossible d'écrire config.json:", e)

async def resolve_target_group():
    """Résout l'ID du groupe à partir de TARGET_GROUP ou config.json (auto-capture sinon)."""
    global TARGET_GROUP_ID_INT, TARGET_GROUP_TITLE

    # 1) Si TARGET_GROUP non fourni, essaie config.json
    if not TARGET_GROUP:
        gid, title = _load_config_group()
        if gid:
            TARGET_GROUP_ID_INT = int(gid)
            TARGET_GROUP_TITLE = title
            return

    if not TARGET_GROUP:
        return  # pas de cible fournie

    val = TARGET_GROUP.strip()

    # 2) ID direct (-100... ou entier)
    if val.startswith("-100") or val.lstrip("-").isdigit():
        try:
            ent = await client.get_entity(int(val))
            TARGET_GROUP_ID_INT = int(ent.id)
            TARGET_GROUP_TITLE = getattr(ent, "title", None) or getattr(ent, "username", None)
            return
        except Exception as e:
            print(f"[ERROR] Résolution ID directe '{val}' échouée: {e}")
            return

    # 3) Username / lien
    m = re.search(r'(?:https?://t\.me/)?@?([A-Za-z0-9_]{5,})', val)
    if not m:
        print(f"[WARN] TARGET_GROUP non valide: {val}")
        return
    username = m.group(1)
    try:
        ent = await client.get_entity(username)
        TARGET_GROUP_ID_INT = int(ent.id)
        TARGET_GROUP_TITLE = getattr(ent, "title", None) or getattr(ent, "username", None) or username
    except Exception as e:
        print(f"[ERROR] Résolution du groupe '{val}' échouée: {e}")

# =========================================================
# Historique de conversation (pour Chatbase)
# =========================================================
_history_by_user: dict[int, list[dict]] = {}

def _get_history(uid: int) -> list[dict]:
    hist = _history_by_user.get(uid, [])
    limit = HISTORY_MAX_TURNS * 2
    return hist[-limit:].copy()

def _append_turn(uid: int, user_text: str, bot_text: Optional[str]):
    lst = _history_by_user.setdefault(uid, [])
    lst.append({"role": "user", "content": user_text})
    if bot_text:
        lst.append({"role": "assistant", "content": bot_text})
    limit = HISTORY_MAX_TURNS * 2
    if len(lst) > limit:
        _history_by_user[uid] = lst[-limit:]

# =========================================================
# Persistance: utilisateurs déjà DM (évite doublons)
# =========================================================
_dm_sent: dict[str, float] = {}

def load_dm_sent():
    global _dm_sent
    try:
        if os.path.isfile(DM_SENT_DB_PATH):
            with open(DM_SENT_DB_PATH, "r", encoding="utf-8") as f:
                _dm_sent = json.load(f)
        else:
            _dm_sent = {}
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

# =========================================================
# Worker file DM (rate-limit + backoff + pas de rafale)
# =========================================================
_dm_queue: asyncio.Queue = asyncio.Queue()
_last_dm_ts = 0.0
_dm_sent_timestamps: list[float] = []
_backoff_seconds = 0

async def dm_worker():
    global _last_dm_ts, _dm_sent_timestamps, _backoff_seconds
    print("[DM-WORKER] démarré")
    while True:
        user_id, text = await _dm_queue.get()
        try:
            if has_already_dm(user_id):
                _dm_queue.task_done()
                continue

            now = time.time()
            _dm_sent_timestamps = [t for t in _dm_sent_timestamps if now - t < 3600]
            if len(_dm_sent_timestamps) >= DM_MAX_PER_HOUR:
                sleep_left = 3600 - (now - _dm_sent_timestamps[0]) + 5
                print(f"[DM] cap/h atteint, pause {int(sleep_left)}s")
                await asyncio.sleep(sleep_left)

            if _backoff_seconds > 0:
                print(f"[DM] backoff {int(_backoff_seconds)}s")
                await asyncio.sleep(_backoff_seconds)

            since = time.time() - _last_dm_ts
            need = random.uniform(DM_SPACING_MIN, DM_SPACING_MAX)
            if since < need:
                await asyncio.sleep(need - since)

            await client.send_message(user_id, text)
            _last_dm_ts = time.time()
            _dm_sent_timestamps.append(_last_dm_ts)
            mark_dm_sent(user_id)
            _backoff_seconds = max(0, int(_backoff_seconds * 0.5))
            print(f"[DM OK] -> {user_id}")

        except ChatWriteForbiddenError:
            print(f"[DM BLOQUÉ] privacy de {user_id}")
        except FloodWaitError as e:
            print(f"[FLOOD_WAIT] {e.seconds}s (DM); retry unique après attente")
            await asyncio.sleep(e.seconds + 2)
            try:
                await client.send_message(user_id, text)
                _last_dm_ts = time.time()
                _dm_sent_timestamps.append(_last_dm_ts)
                mark_dm_sent(user_id)
                _backoff_seconds = max(0, int(_backoff_seconds * 0.5))
                print(f"[DM OK après FLOOD_WAIT] -> {user_id}")
            except Exception as e2:
                print(f"[DM ÉCHEC après FLOOD_WAIT] {user_id} -> {e2}")
        except PeerFloodError:
            # Anti-spam Telegram → cool down fort puis requeue
            _backoff_seconds = max(_backoff_seconds * 2, 300)  # min 5 min
            print(f"[PEER_FLOOD] backoff={_backoff_seconds}s ; requeue")
            await asyncio.sleep(_backoff_seconds)
            if not has_already_dm(user_id):
                await _dm_queue.put((user_id, text))
        except Exception as e:
            print(f"[DM ERROR] {e}")
        finally:
            _dm_queue.task_done()

# =========================================================
# Chatbase client
# =========================================================
async def ask_chatbase(uid: int, latest_user_text: str) -> Optional[str]:
    if not CHATBASE_API_KEY or not CHATBASE_BOT_ID:
        return None
    messages = _get_history(uid)
    messages.append({"role": "user", "content": latest_user_text})
    payload = {
        "chatbotId": CHATBASE_BOT_ID,
        "messages": messages,          # historique complet tronqué + message courant
        "conversationId": str(uid),    # conversation = id utilisateur
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {CHATBASE_API_KEY}", "Content-Type": "application/json"}
    async with _chatbase_sem:
        async with httpx.AsyncClient(timeout=45) as http:
            r = await http.post("https://www.chatbase.co/api/v1/chat", json=payload, headers=headers)
            if r.status_code != 200:
                print("[Chatbase Error]", r.status_code, r.text)
                return None
            data = r.json()
            return data.get("text") or data.get("message") or data.get("reply")

# =========================================================
# Handlers
# =========================================================
# Logger global pour comprendre ce qui arrive réellement
@client.on(events.ChatAction)
async def _debug_log_actions(event: events.ChatAction.Event):
    if not DEBUG_LOG_JOINS:
        return
    try:
        who = await event.get_user() if (event.user_joined or event.user_added or event.user_left) else None
        print(f"[DEBUG ChatAction] chat_id={event.chat_id}, user={getattr(who, 'id', None)}, "
              f"joined={event.user_joined}, added={event.user_added}, left={event.user_left}")
    except Exception as e:
        print("[DEBUG ChatAction ERROR]", e)

# Auto-capture du groupe si activée et pas encore résolu
@client.on(events.ChatAction)
async def _auto_capture_group(event: events.ChatAction.Event):
    global TARGET_GROUP_ID_INT, TARGET_GROUP_TITLE
    if TARGET_GROUP_ID_INT is not None or not AUTO_CAPTURE_GROUP:
        return
    try:
        if event.user_joined or event.user_added or event.user_left:
            TARGET_GROUP_ID_INT = int(event.chat_id)
            TARGET_GROUP_TITLE = None
            _save_config_group(TARGET_GROUP_ID_INT, TARGET_GROUP_TITLE)
            print(f"[AUTO] Groupe capturé: {TARGET_GROUP_ID_INT}. Persisté dans config.json.")
    except Exception as e:
        print("[AUTO ERROR]", e)

# DM au join (uniquement pour le groupe ciblé)
@client.on(events.ChatAction)
async def on_user_join(event: events.ChatAction.Event):
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
            try:
                await asyncio.sleep(DM_DELAY_SECONDS)
                if not has_already_dm(uid):
                    await _dm_queue.put((uid, WELCOME_DM))
                    print(f"[QUEUE] DM d'accueil -> {uid}")
            except asyncio.CancelledError:
                pass

        asyncio.create_task(enqueue_dm())
    except Exception as e:
        print("[ERROR on_user_join]", e)

# Réponses Chatbase uniquement en DM (jamais dans un groupe)
@client.on(events.NewMessage)
async def on_private_message(event: events.NewMessage.Event):
    try:
        if event.out or not event.is_private:
            return
        text = (event.raw_text or "").strip()
        if not text:
            return
        sender = await event.get_sender()
        uid = sender.id
        delay = random.uniform(REPLY_DELAY_MIN, REPLY_DELAY_MAX)
        await asyncio.sleep(delay)
        answer = await ask_chatbase(uid, text)
        if answer:
            await client.send_message(uid, answer, reply_to=event.id)
            _append_turn(uid, text, answer)
            print(f"[DM OUT -> {uid}] (delay ~{int(delay)}s)")
        else:
            _append_turn(uid, text, None)
    except Exception as e:
        print("[ERROR on_private_message]", e)

# =========================================================
# Serveur long-cours (auto-reconnect sur coupure réseau)
# =========================================================
async def serve_forever():
    backoff = 1
    while True:
        try:
            await client.run_until_disconnected()
        except (ConnectionResetError, OSError) as e:
            print(f"[NET] Connexion perdue: {e}. Reconnexion dans {backoff}s…")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)  # max 60s
        else:
            backoff = 1  # reset si sortie propre

# =========================================================
# Main
# =========================================================
async def main():
    print("Connexion à Telegram…")
    await client.start()
    me = await client.get_me()
    print(f"✅ Connecté en tant que {getattr(me, 'first_name', '')} (@{getattr(me, 'username', None)})")

    await resolve_target_group()
    if TARGET_GROUP_ID_INT:
        print(f"[INFO] Groupe surveillé: {TARGET_GROUP_TITLE or '(sans titre)'} ({TARGET_GROUP_ID_INT})")
    else:
        if AUTO_CAPTURE_GROUP:
            print("[INFO] Pas de groupe défini, auto-capture ACTIVE. Dès qu'un ChatAction arrive, je fixe le groupe.")
        else:
            print("[INFO] Aucun groupe cible résolu (pas d'auto DM). Renseigne TARGET_GROUP ou mets AUTO_CAPTURE_GROUP=1.")

    load_dm_sent()
    print(f"[INFO] Utilisateurs déjà DM: {len(_dm_sent)}")

    asyncio.create_task(dm_worker())
    print("[READY] En écoute… (DEBUG_LOG_JOINS=%s)" % ("ON" if DEBUG_LOG_JOINS else "OFF"))

    await serve_forever()

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
