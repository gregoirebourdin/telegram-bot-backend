

import asyncio
import sys
from telethon import TelegramClient
from telethon.sessions import StringSession
from core.config import API_ID, API_HASH, SESSION_STRING

if sys.version_info >= (3, 12):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH,
    connection_retries=999,
    request_retries=5,
    retry_delay=2,
    flood_sleep_threshold=60,
)

