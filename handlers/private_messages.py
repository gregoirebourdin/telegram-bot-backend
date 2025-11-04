from telethon import events

def register_private_handler(client):
    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        sender = await event.get_sender()
        print(f"[PRIVATE] Message reçu de {sender.first_name}: {event.text}")
