import asyncio
import uvicorn
from core.telegram_client import client
from core.storage import load_dm_sent
from handlers.joins import register_join_handler
from handlers.private_messages import register_private_handler
from services.dm_worker import dm_worker
from services.api import app as api_app
from core.config import PORT

async def start_api():
    config = uvicorn.Config(api_app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    print("Connexion à Telegram…")
    await client.connect()
    me = await client.get_me()
    print(f"✅ Connecté en tant que {me.first_name} (@{me.username})")

    load_dm_sent()

    register_join_handler(client)
    register_private_handler(client)

    asyncio.create_task(dm_worker(client))
    asyncio.create_task(start_api())

    print("[READY] En écoute Telegram + API")
    await client.run_until_disconnected()

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
