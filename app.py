import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

from handlers.joins import register_join_handler
from handlers.private_messages import register_private_handler
from core.storage import init_storage


# ==============================
# CONFIGURATION
# ==============================
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")  # Railway variable
TARGET_GROUP_ID = os.getenv("TARGET_GROUP_ID")

if not API_ID or not API_HASH:
    raise ValueError("❌ API_ID et API_HASH sont requis dans les variables d’environnement.")
API_ID = int(API_ID)

if TARGET_GROUP_ID:
    try:
        TARGET_GROUP_ID = int(TARGET_GROUP_ID)
    except ValueError:
        print("⚠️ TARGET_GROUP_ID invalide, il doit être un nombre.")
        TARGET_GROUP_ID = None


# ==============================
# INITIALISATION DU CLIENT
# ==============================
if SESSION_STRING:
    print("✅ Utilisation de la session string (mode headless)")
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    print("⚠️ Aucune SESSION_STRING trouvée — utilisation du fichier local de session")
    client = TelegramClient("data/userbot_session", API_ID, API_HASH)


# ==============================
# MAIN
# ==============================
async def main():
    print("Connexion à Telegram…")
    await client.connect()

    # Vérifie que la session est valide
    if not await client.is_user_authorized():
        print("❌ Session absente ou invalide — fournis une SESSION_STRING valide dans Railway.")
        return

    me = await client.get_me()
    print(f"✅ Connecté en tant que {me.first_name} (@{me.username})")

    # Initialisation du stockage (historique, état, etc.)
    init_storage()

    # Enregistrement des handlers
    if TARGET_GROUP_ID:
        register_join_handler(client, TARGET_GROUP_ID)
        print(f"[INFO] Surveillance du groupe ID: {TARGET_GROUP_ID}")
    else:
        print("[INFO] Aucun groupe configuré (TARGET_GROUP_ID manquant).")

    register_private_handler(client)
    print("[READY] En écoute Telegram + API")

    # Garde le client actif
    await client.run_until_disconnected()


# ==============================
# ENTRYPOINT
# ==============================
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Arrêt manuel du bot.")
    except Exception as e:
        print(f"❌ Erreur critique: {type(e).__name__} - {e}")
