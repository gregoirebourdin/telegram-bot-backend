import os
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession

from handlers.joins import register_join_handler
from handlers.private_messages import register_private_handler
from core.storage import init_storage

# --- CONFIG ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")  # <== ta variable Railway
TARGET_GROUP_ID = int(os.getenv("TARGET_GROUP_ID"))

# --- INIT TELEGRAM CLIENT ---
if SESSION_STRING:
    print("✅ Utilisation de la session string")
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    print("⚠️  Aucune SESSION_STRING trouvée, utilisation du fichier local.")
    client = TelegramClient("data/userbot_session", API_ID, API_HASH)

# --- LANCEMENT ---
async def main():

    print("Connexion à Telegram…")
    await client.connect()
    if not await client.is_user_authorized():
        print("[AUTH] Session absente ou invalide. Fournis SESSION_STRING valide.")
        return
    me = await client.get_me()
    print(f"✅ Connecté en tant que {me.first_name} (@{me.username})")

    # Initialiser le stockage
    init_storage()

    # Enregistrement des handlers
    register_join_handler(client, TARGET_GROUP_ID)
    register_private_handler(client)

    print(f"[READY] En écoute sur {TARGET_GROUP_ID}…")

    # Garde le client actif
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
