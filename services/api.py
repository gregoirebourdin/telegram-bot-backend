# services/api.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any

from services.state import (
    list_conversations, mute_user, unmute_user, toggle_mute, is_muted,
    touch_conversation, get_state_meta, upsert_user_profile
)
from core.telegram_client import client

app = FastAPI(title="Operator API", version="1.1.0")

# CORS large (restreins en prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

class SendBody(BaseModel):
    message: str

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/state")
def state_meta():
    """Debug: vois chemin, taille fichier, compte conv/users, timestamps."""
    return get_state_meta()

@app.get("/conversations")
def get_conversations() -> List[Dict[str, Any]]:
    return list_conversations()

@app.post("/conversations/{user_id}/mute")
def post_mute(user_id: int):
    mute_user(user_id)
    return {"user_id": user_id, "muted": True}

@app.post("/conversations/{user_id}/unmute")
def post_unmute(user_id: int):
    unmute_user(user_id)
    return {"user_id": user_id, "muted": False}

@app.post("/conversations/{user_id}/toggle")
def post_toggle(user_id: int):
    muted = toggle_mute(user_id)
    return {"user_id": user_id, "muted": muted}

@app.post("/conversations/{user_id}/send")
async def post_send(user_id: int, body: SendBody):
    try:
        peer = await client.get_entity(user_id)
        await client.send_message(peer, body.message)
        touch_conversation(user_id, body.message)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------- DEBUG: seed manual -----------
class SeedBody(BaseModel):
    user_id: int
    first_name: str | None = None
    username: str | None = None
    text: str = "seed message"

@app.post("/debug/seed")
def debug_seed(b: SeedBody):
    """Insère une conversation de test dans le state pour vérifier la persistance."""
    upsert_user_profile(b.user_id, {"first_name": b.first_name, "username": b.username})
    touch_conversation(b.user_id, b.text)
    return {"ok": True, "meta": get_state_meta()}
