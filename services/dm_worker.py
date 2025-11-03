import asyncio
import time
import random
from telethon.errors import FloodWaitError, PeerFloodError, ChatWriteForbiddenError
from core.config import DM_SPACING_MIN, DM_SPACING_MAX, DM_MAX_PER_HOUR
from core.storage import has_already_dm, mark_dm_sent

_dm_queue: asyncio.Queue = asyncio.Queue()
_last_dm_ts = 0.0
_dm_sent_timestamps: list[float] = []
_backoff_seconds = 0

async def enqueue_dm(user_id, user_entity, text):
    await _dm_queue.put((user_id, user_entity, text))

async def dm_worker(client):
    global _last_dm_ts, _dm_sent_timestamps, _backoff_seconds
    print("[DM-WORKER] démarré")
    while True:
        user_id, user_entity, text = await _dm_queue.get()
        print(f"[DM-WORKER] reçu tâche -> {user_id}, has_entity={bool(user_entity)}")
        try:
            if has_already_dm(user_id):
                print(f"[DM-WORKER] déjà DM -> {user_id}")
                _dm_queue.task_done()
                continue

            # Cap / heure
            now = time.time()
            _dm_sent_timestamps = [t for t in _dm_sent_timestamps if now - t < 3600]
            if len(_dm_sent_timestamps) >= DM_MAX_PER_HOUR:
                sleep_left = 3600 - (now - _dm_sent_timestamps[0]) + 5
                print(f"[DM] cap/h atteint, pause {int(sleep_left)}s")
                await asyncio.sleep(sleep_left)

            # Backoff si nécessaire
            if _backoff_seconds > 0:
                print(f"[DM] backoff {int(_backoff_seconds)}s")
                await asyncio.sleep(_backoff_seconds)

            # Espacement naturel
            since = time.time() - _last_dm_ts
            need = random.uniform(DM_SPACING_MIN, DM_SPACING_MAX)
            if since < need:
                print(f"[DM-WORKER] attente {int(need - since)}s avant DM {user_id}")
                await asyncio.sleep(need - since)

            # Envoi (avec access_hash si possible)
            peer = user_entity or await client.get_entity(user_id)
            await client.send_message(peer, text)

            _last_dm_ts = time.time()
            _dm_sent_timestamps.append(_last_dm_ts)
            mark_dm_sent(user_id)
            _backoff_seconds = max(0, int(_backoff_seconds * 0.5))
            print(f"[DM OK ✅] -> {user_id}")

        except ChatWriteForbiddenError:
            print(f"[DM BLOQUÉ] privacy de {user_id}")
        except FloodWaitError as e:
            print(f"[FLOOD_WAIT] {e.seconds}s (DM); retry unique après attente")
            await asyncio.sleep(e.seconds + 2)
            try:
                peer = user_entity or await client.get_entity(user_id)
                await client.send_message(peer, text)
                _last_dm_ts = time.time()
                _dm_sent_timestamps.append(_last_dm_ts)
                mark_dm_sent(user_id)
                _backoff_seconds = max(0, int(_backoff_seconds * 0.5))
                print(f"[DM OK après FLOOD_WAIT] -> {user_id}")
            except Exception as e2:
                print(f"[DM ÉCHEC après FLOOD_WAIT] {user_id} -> {e2}")
        except PeerFloodError:
            _backoff_seconds = max(_backoff_seconds * 2, 300)  # min 5 min
            print(f"[PEER_FLOOD] backoff={_backoff_seconds}s ; requeue")
            await asyncio.sleep(_backoff_seconds)
            if not has_already_dm(user_id):
                await _dm_queue.put((user_id, user_entity, text))
        except Exception as e:
            print(f"[DM ERROR ⚠️] {user_id}: {type(e).__name__}: {e}")
        finally:
            _dm_queue.task_done()
