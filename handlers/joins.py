# handlers/joins.py
import asyncio
from telethon import events
from core.config import TARGET_GROUP, AUTO_CAPTURE_GROUP, DM_DELAY_SECONDS, WELCOME_DM, DEBUG_LOG_JOINS
from core.storage import has_already_dm, load_group_config, save_group_config
from services.dm_worker import enqueue_dm
from services.state import upsert_user_profile, touch_conversation, is_muted

TARGET_GROUP_ID_INT = int(TARGET_GROUP) if TARGET_GROUP.lstrip("-").isdigit() else None

def register_join_handler(client):
    # Auto-capture si demandé
    if TARGET_GROUP_ID_INT is None and AUTO_CAPTURE_GROUP:
        @client.on(events.ChatAction)
        async def _auto_capture_group(event):
            if event.user_joined or event.user_added or event.user_left:
                gid = int(event.chat_id)
                save_group_config(gid, None)
                print(f"[AUTO] Groupe capturé: {gid} (persisté dans config.json).")
                global TARGET_GROUP_ID_INT
                TARGET_GROUP_ID_INT = gid

    @client.on(events.ChatAction)
    async def on_user_join(event):
        if DEBUG_LOG_JOINS:
            print(f"[JOIN DEBUG] chat_id={event.chat_id}, joined={event.user_joined}, added={event.user_added}, left={event.user_left}")

        # Résout le groupe via config si besoin
        if TARGET_GROUP_ID_INT is None:
            gid, _ = load_group_config()
            if gid:
                globals()['TARGET_GROUP_ID_INT'] = gid
            else:
                return

        if int(event.chat_id) != int(TARGET_GROUP_ID_INT):
            return
        if not (event.user_joined or event.user_added):
            return

        user = await event.get_user()
        uid = user.id

        # Enregistre/MAJ le profil pour le front
        upsert_user_profile(uid, {
            "first_name": getattr(user, "first_name", None),
            "last_name": getattr(user, "last_name", None),
            "username": getattr(user, "username", None),
            "phone": getattr(user, "phone", None),
        })
        touch_conversation(uid, last_text=None)

        if has_already_dm(uid):
            if DEBUG_LOG_JOINS:
                print(f"[JOIN DEBUG] {uid} déjà DM, skip.")
            return

        # Si MUTED → on n'envoie pas le DM d'accueil auto
        if is_muted(uid):
            if DEBUG_LOG_JOINS:
                print(f"[JOIN DEBUG] {uid} est MUTED, pas de DM d'accueil.")
            return

        async def delayed():
            await asyncio.sleep(DM_DELAY_SECONDS)
            if is_muted(uid):
                return
            if not has_already_dm(uid):
                await enqueue_dm(uid, user, WELCOME_DM)
                print(f"[QUEUE ✅] DM d’accueil en file -> {uid}")

        asyncio.create_task(delayed())
