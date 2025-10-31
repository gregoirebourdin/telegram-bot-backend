# app.py — DM only, sûr Telegram, avec résolution automatique du groupe
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
from telethon import TelegramClient, events, functions
from telethon.errors import (
    FloodWaitError, ChatWriteForbiddenError, PeerFloodError
)
from telethon.tl.types import InputPeerChannel, InputPeerChat

# ---------- Compat Python >= 3.12/3.14 ----------
if sys.version_info >= (3, 12):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
# -------------------------------------------------

load_dotenv()

# --- Identifiants Telegram ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME", "userbot_session")

# --- Chatbase ---
CHATBASE_API_KEY = os.getenv("CHATBASE_API_KEY")
CHATBASE_BOT_ID = os.getenv("CHATBASE_BOT_ID")

# --- Groupe cible : ID (-100...), @username, ou URL t.me/xxx ---
TARGET_GROUP = os.getenv("TARGET_GROUP", "").strip()

# --- Message d'accueil (DM) ---
WELCOME_DM = (
    "Coucou c’est Billie du Become Club ! 🥰 Trop contente de t’accueillir dans la team !\n\n"
    "Dis-moi, je suis curieuse… tu aimerais avoir quel type de résultats avec les réseaux sociaux ?\n\n"
    "Juste un complément ou remplacer ton salaire ? 😊"
)

# --- Délais & Concurrence ---
DM_DELAY_SECONDS   = float(os.getenv("DM_DELAY_SECONDS", "10"))
REPLY_DELAY_MIN    = float(os.getenv("REPLY_DELAY_MIN", "20"))
REPLY_DELAY_MAX    = float(os.getenv("REPLY_DELAY_MAX", "50"))
CHATBASE_CONCURRENCY = int(os.getenv("CHATBASE_CONCURRENCY", "8"))
HISTORY_MAX_TURNS  = int(os.getenv("HISTORY_MAX_TURNS", "40"))

# --- Anti-spam DM d'accueil ---
DM_SPACING_MIN   = float(os.getenv("DM_SPACING_MIN", "40"))
DM_SPACING_MAX   = float(os.getenv("DM_SPACING_MAX", "70"))
DM_MAX_PER_HOUR  = int(os.getenv("DM_MAX_PER_HOUR", "30"))
DM_SENT_DB_PATH  = os.getenv("DM_SENT_DB", "dm_sent.json")

# --- Debug global des joins ---
DEBUG_LOG_JOINS = os.getenv("DEBUG_LOG_JOINS", "0").strip() == "1"

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
_chatbase_sem = asyncio.Semaphore(CHATBASE_CONCURRENCY)

# ---------- Résolution du groupe (ID réel) ----------
TARGET_GROUP_ID_INT: Optional[int] = None
TARGET_GROUP_TITLE: Optional[str] = None

async def resolve_target_group():
    """
    Accepte :
      - ID: -1001234567890
      - Username: @becomeclub
      - URL: https://t.me/becomeclub
    Renseigne TARGET_GROUP_ID_INT et TARGET_GROUP_TITLE.
    """
    global TARGET_GROUP_ID_INT, TARGET_GROUP_TITLE
    if not TARGET_GROUP:
        return
    val = TARGET_GROUP

    # 1) ID direct
    try:
        TARGET_GROUP_ID_INT = int(val)
        # Récupérer le titre si possible
        try:
            ent = await client.get_entity(TARGET_GROUP_ID_INT)
            TARGET_GROUP_TITLE = getattr(ent, "title", None) or getattr(ent, "username", None)
        except Exception:
            TARGET_GROUP_TITLE = None
        return
    except ValueError:
        pass

    # 2) Username / URL -> extraire username
    m = re.search(r'(?:https?://t\.me/)?@?([A-Za-z0-9_]{5,})', val)
    if not m:
        print(f"[WARN] TARGET_GROUP '{val}' non reconnu (ID ou @username ou t.me/username attendus)")
        return
    username = m.group(1)

    try:
        ent = await client.get_entity(username)
        # ent.id est le -100... pour supergroup/canal, ou un id positif pour "basic group"
        TARGET_GROUP_ID_INT = int(getattr(ent, "id", None))
        TARGET_GROUP_TITLE = getattr(ent, "title", None) or getattr(ent, "username", None) or username
    except Exception as e:
        print(f"[ERROR] Impossible de résoudre '{val}' -> {e}")
        TARGET_GROUP_ID_INT = None
        TARGET_GROUP_TITLE = None

# ---------- Historique DM pour Chatbase ----------
_history_by_user: dict[int, list[dict]] = {}

def _get_history(user_id: int) -> list[dict]:
    hist = _history_by_user.get(user_id, [])
    limit = HISTORY_MAX_TURNS * 2
    return hist[-limit:].copy()

def _append_turn(user_id: int, user_text: str, assistant_text: Optional[str]):
    lst = _history_by_user.setdefault(user_id, [])
    lst.append({"role": "user", "content": user_text})
    if assistant_text is not None:
        lst.append({"role": "assistant", "content": assistant_text})
    limit = HISTORY_MAX_TURNS * 2
    if len(lst) > limit:
        _history_by_user[user_id] = lst[-limit:]

# ---------- Persistance des utilisateurs déjà DM ----------
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
        print("[WARN] Impossible d'écrire DM_SENT_DB:", e)

def has_already_dm(user_id: int) -> bool:
    return str(user_id) in _dm_sent

def mark_dm_sent(user_id: int):
    _dm_sent[str(user_id)] = time.time()
    save_dm_sent()

# ---------- File & worker DM (rate-limit/backoff) ----------
_dm_queue: asyncio.Queue[tuple[int, str]] = asyncio.Queue()
_dm_worker_task: Optional[asyncio.Task] = None

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
                print(f"[DM-WORKER] cap/h atteint, pause {int(sleep_left)}s")
                await asyncio.sleep(sleep_left)

            if _backoff_seconds > 0:
                print(f"[DM-WORKER] backoff {int(_backoff_seconds)}s")
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
            print(f"[FLOOD_WAIT] {e.seconds}s (DM); re-tentative unique après attente")
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
            _backoff_seconds = max(_backoff_seconds * 2, 300)
            print(f"[PEER_FLOOD] backoff={_backoff_seconds}s ; reprogrammation unique")
            await asyncio.sleep(_backoff_seconds)
            if not has_already_dm(user_id):
                await _dm_queue.put((user_id, text))
        except Exception as e:
            print(f"[DM ERROR] {user_id} -> {e}")
        finally:
            _dm_queue.task_done()

# ---------- Client Chatbase ----------
async def ask_chatbase_with_history(user_id: int, latest_user_text: str) -> Optional[str]:
    if not CHATBASE_API_KEY or not CHATBASE_BOT_ID:
        return None

    messages = _get_history(user_id)
    messages.append({"role": "user", "content": latest_user_text})

    payload = {
        "chatbotId": CHATBASE_BOT_ID,
        "messages": messages,
        "conversationId": str(user_id),
        "contactId": str(user_id),
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

# ---------- Handlers ----------
_pending_dm_tasks: dict[tuple[int, int], asyncio.Task] = {}

# Logger de secours (voit TOUS les ChatAction si DEBUG_LOG_JOINS=1)
@client.on(events.ChatAction)
async def debug_all_actions(event: events.ChatAction.Event):
    if not DEBUG_LOG_JOINS:
        return
    try:
        who = await event.get_user() if (event.user_joined or event.user_added or event.user_left) else None
        print(f"[DEBUG ChatAction] chat_id={event.chat_id}, user={getattr(who,'id',None)}, "
              f"joined={event.user_joined}, added={event.user_added}, left={event.user_left}")
    except Exception as e:
        print("[DEBUG ChatAction ERROR]", e)

@client.on(events.ChatAction)
async def on_join_schedule_dm(event: events.ChatAction.Event):
    """Planifie 1 DM (unique) après DM_DELAY_SECONDS quand quelqu'un rejoint le groupe cible."""
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
            # déjà DM par le passé → on ignore
            return

        key = (event.chat_id, uid)
        old = _pending_dm_tasks.get(key)
        if old and not old.done():
            old.cancel()

        async def delayed_enqueue():
            try:
                await asyncio.sleep(DM_DELAY_SECONDS)
                if has_already_dm(uid):
                    return
                await _dm_queue.put((uid, WELCOME_DM))
                print(f"[QUEUE] DM d'accueil programmé -> {uid}")
            except asyncio.CancelledError:
                print(f"[DM PLAN ANNULÉ] -> {uid}")
            finally:
                _pending_dm_tasks.pop(key, None)

        _pending_dm_tasks[key] = asyncio.create_task(delayed_enqueue())

    except Exception as e:
        print("[ERROR on_join_schedule_dm]", e)

@client.on(events.NewMessage)
async def on_private_message(event: events.NewMessage.Event):
    """En DM uniquement : relaye vers Chatbase avec historique, puis répond après délai aléatoire."""
    try:
        if event.out or not event.is_private:
            return

        text = (event.raw_text or "").strip()
        if not text:
            return

        sender = await event.get_sender()
        user_id = sender.id
        chat_id = event.chat_id
        print(f"[DM IN] {user_id}: {text[:120]}")

        async def respond_later(latest_text: str, reply_to_id: int):
            try:
                delay = random.uniform(REPLY_DELAY_MIN, REPLY_DELAY_MAX)
                await asyncio.sleep(delay)
                answer = await ask_chatbase_with_history(user_id, latest_text)
                if answer:
                    try:
                        await client.send_message(chat_id, answer, reply_to=reply_to_id)
                        _append_turn(user_id, latest_text, answer)
                        print(f"[DM OUT after {delay:.1f}s] -> {user_id}")
                    except FloodWaitError as e:
                        print(f"[FLOOD_WAIT] {e.seconds}s (reply DM)")
                        await asyncio.sleep(e.seconds)
                        await client.send_message(chat_id, answer, reply_to=reply_to_id)
                        _append_turn(user_id, latest_text, answer)
                else:
                    _append_turn(user_id, latest_text, None)
            except Exception as e:
                print("[ERROR respond_later]", e)

        asyncio.create_task(respond_later(text, event.id))

    except Exception as e:
        print("[ERROR on_private_message]", e)

# ---------- Main ----------
async def main():
    print("Connexion à Telegram…")
    await client.start()
    me = await client.get_me()
    print(f"✅ Connecté en tant que {getattr(me,'first_name', '')} (@{getattr(me,'username', None)})")

    # Résoudre le groupe (ID exact) AVANT d'écouter les events
    await resolve_target_group()
    if TARGET_GROUP_ID_INT is not None:
        print(f"[INFO] Groupe surveillé (JOIN -> DM privé unique): {TARGET_GROUP_ID_INT}"
              + (f" [{TARGET_GROUP_TITLE}]" if TARGET_GROUP_TITLE else ""))
    else:
        print("[INFO] Aucun groupe cible résolu : les DMs d'accueil sont désactivés.")
        print("      -> Vérifie TARGET_GROUP dans ton .env (ID -100…, @username ou lien t.me/xxx)")

    # Charger la base des utilisateurs déjà DM
    load_dm_sent()
    print(f"[INFO] Utilisateurs déjà DM connus: {len(_dm_sent)}")

    # Démarrer le worker DM
    global _dm_worker_task
    _dm_worker_task = asyncio.create_task(dm_worker())

    print(f"[INFO] Réponses DM différées: {int(REPLY_DELAY_MIN)}–{int(REPLY_DELAY_MAX)} s | "
          f"Concurrence Chatbase={CHATBASE_CONCURRENCY} | "
          f"Historique ~{HISTORY_MAX_TURNS} tours")
    print(f"[INFO] DM rate-limit: spacing {int(DM_SPACING_MIN)}–{int(DM_SPACING_MAX)} s, cap/h={DM_MAX_PER_HOUR}")
    if DEBUG_LOG_JOINS:
        print("[DEBUG] Logger de tous les ChatAction ACTIVÉ (DEBUG_LOG_JOINS=1)")

    await client.run_until_disconnected()

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
