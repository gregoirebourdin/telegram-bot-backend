from telethon import events
from core.config import TARGET_GROUP
from services.dm_worker import queue_dm

def register_join_handler(client):
    @client.on(events.ChatAction)
    async def handler(event):
        if not (event.user_joined or event.user_added):
            return
        if str(event.chat_id) != str(TARGET_GROUP):
            return
        user = await event.get_user()
        print(f"[JOIN] {user.first_name} a rejoint le groupe.")
        text = "👋 Bienvenue dans le groupe ! Je t’écris en privé pour t’expliquer comment ça marche."
        await queue_dm(user.id, user, text)
