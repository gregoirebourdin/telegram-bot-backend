# app.py
import asyncio
import uvicorn
from core.telegram_client import client
from core.storage import load_dm_sent
from services.dm_worker import dm_worker
from handlers.joins import register_join_handler
from handlers.private_messages import register_private_handler
from services.api import app as fastapi_app  # importe l'instance FastAPI

async def start_api():
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=8080, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

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
    register_join_handler(client)
    register_private_handler(client)

    # Lancer le worker DM + l'API + la boucle Telethon
    asyncio.create_task(dm_worker(client))
    asyncio.create_task(start_api())
    print("[READY] Telegram + API http://localhost:8080")

    await serve_forever()

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
