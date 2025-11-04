from telethon import events
from services.chatbase import ask_chatbase
from models.history import append_message

def register_private_handler(client):
    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        sender = await event.get_sender()
        text = event.raw_text.strip()
        uid = sender.id

        print(f"[PRIVATE] Message reçu de {sender.first_name}: {text}")

        # Historique utilisateur (pour continuité du contexte)
        append_message(uid, "user", text)

        # Envoi à Chatbase
        try:
            reply = await ask_chatbase(uid, text)
        except Exception as e:
            print(f"[Chatbase Exception] {type(e).__name__}: {e}")
            reply = None

        if not reply:
            reply = "Je n’ai pas bien compris, peux-tu reformuler ?"

        # Envoie la réponse à l’utilisateur
        try:
            await event.respond(reply)
            print(f"[BOT -> {sender.first_name}] {reply}")
            append_message(uid, "assistant", reply)
        except Exception as e:
            print(f"[SEND ERROR] {type(e).__name__}: {e}")
