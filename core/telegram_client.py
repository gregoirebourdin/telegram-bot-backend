import os
import sys
import asyncio
from telethon import TelegramClient
from telethon.network.mtprotosender import MTProtoSender
from telethon.errors import TypeNotFoundError
from .config import API_ID, API_HASH, SESSION_NAME

# Forcer IPv4 pour stabilité réseaux
os.environ["TG_FORCE_IPV4"] = "1"

# Patch tolérant aux nouveaux TLObjects
_old_handle = MTProtoSender._handle_rpc_result
async def _safe_handle(self, *args, **kwargs):
    try:
        return await _old_handle(self, *args, **kwargs)
    except TypeNotFoundError as e:
        print(f"[WARN] Objet MTProto inconnu ignoré: {e}")
        return None
MTProtoSender._handle_rpc_result = _safe_handle

# Compat Python 3.12+
if sys.version_info >= (3, 12):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

client = TelegramClient(
    SESSION_NAME, API_ID, API_HASH,
    connection_retries=999,
    retry_delay=2,
    request_retries=5,
    flood_sleep_threshold=30,
)
