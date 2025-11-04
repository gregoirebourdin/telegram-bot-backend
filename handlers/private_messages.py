from telethon import events
from services.chatbase import ask_chatbase  # ✅ fixed import
from core.storage import load_conversations, save_conversations


def register_private_handler(client):
    """Écoute les messages privés et répond via Chatbase"""
    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        user_id = event.sender_id
        text = event.raw_text.strip()
        print(f"[DM IN] {user_id}: {text}")

        # Charge les conversations existantes
        conversations = load_conversations()

        # Récupère ou crée la conversation
        conversation = next((c for c in conversations if c["user_id"] == user_id), None)
        if not conversation:
            conversation = {"user_id": user_id, "messages": []}
            conversations.append(conversation)

        # Ajoute le message utilisateur
        conversation["messages"].append({"role": "user", "content": text})

        # Appelle Chatbase
        try:
            reply = await ask_chatbase(user_id, conversation["messages"])
            if reply:
                await event.respond(reply)
                conversation["messages"].append({"role": "assistant", "content": reply})
            else:
                await event.respond("⚠️ Je n’ai pas compris ta demande.")
        except Exception as e:
            print(f"[ERROR Chatbase] {e}")
            await event.respond("⚠️ Une erreur s’est produite avec Chatbase.")

        # Sauvegarde la conversation mise à jour
        save_conversations(conversations)
