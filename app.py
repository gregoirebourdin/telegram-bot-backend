import asyncio
from core.telegram_client import client
from core.config import DEBUG_LOG_JOINS
from core.storage import load_dm_sent
from services.dm_worker import dm_worker
from handlers.joins import register_join_handler
from handlers.private_messages import register_private_handler

async def serve_forever():
    backoff = 1
    while True:
        try:
            await client.run_until_disconnected()
        except Exception as e:
            print(f"[NET ERROR] {type(e).__name__}: {e} — reconnexion dans {backoff}s…")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
        else:
            backoff = 1

async def main():
    print("Connexion à Telegram…")
    await client.start()
    me = await client.get_me()
    print(f"✅ Connecté en tant que {getattr(me, 'first_name','')} (@{getattr(me,'username',None)})")

    load_dm_sent()
    print("[INFO] Utilisateurs déjà DM:", len(load_dm_sent.cache))

    # Enregistre les handlers
    register_join_handler(client)
    register_private_handler(client)

    # Lance le worker DM
    asyncio.create_task(dm_worker(client))
    print(f"[READY] En écoute… (DEBUG_LOG_JOINS={'ON' if DEBUG_LOG_JOINS else 'OFF'})")

    await serve_forever()

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
