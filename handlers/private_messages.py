import asyncio
import random
from telethon import events
from core.config import REPLY_DELAY_MIN, REPLY_DELAY_MAX
from services.chatbase import ask_chatbase
from models.history import append_turn

def register_private_handler(client):
    @client.on(events.NewMessage)
    async def on_private_message(event):
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
            await client.send_message(sender, answer, reply_to=event.id)
            append_turn(uid, text, answer)
            print(f"[DM OUT -> {uid}] (~{int(delay)}s)")
        else:
            append_turn(uid, text, None)
