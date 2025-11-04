import asyncio
from telethon.errors import FloodWaitError, ConnectionError as TgConnectionError
from core.storage import load_dm_sent, save_dm_sent

_dm_queue = asyncio.Queue()
_dm_sent = load_dm_sent()

async def queue_dm(user_id, user_entity, text):
    await _dm_queue.put((user_id, user_entity, text))
    print(f"[QUEUE ✅] DM en attente pour {user_id}")

async def dm_worker(client):
    print("[DM-WORKER] démarré")
    while True:
        user_id, user_entity, text = await _dm_queue.get()
        try:
            if str(user_id) in _dm_sent:
                _dm_queue.task_done()
                continue
            peer = user_entity or await client.get_entity(user_id)
            await client.send_message(peer, text)
            print(f"[DM ✅] Message envoyé à {user_id}")
            _dm_sent[str(user_id)] = True
            save_dm_sent(_dm_sent)
            await asyncio.sleep(2)
        except FloodWaitError as e:
            print(f"[DM 💤] FloodWait {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except TgConnectionError:
            print("[DM ❌] Bot déconnecté — requeue")
            await asyncio.sleep(5)
            await _dm_queue.put((user_id, user_entity, text))
        except Exception as e:
            print(f"[DM ERROR] {e}")
        finally:
            _dm_queue.task_done()
