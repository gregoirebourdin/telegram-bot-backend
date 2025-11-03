# services/api.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any

from services.state import list_conversations, mute_user, unmute_user, toggle_mute, is_muted
from services.state import touch_conversation
from core.telegram_client import client

app = FastAPI(title="Operator API", version="1.0.0")

# CORS ouvert par défaut (mets ton domaine de front en prod)
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
        # envoi manuel côté opérateur : toujours permis
        peer = await client.get_entity(user_id)
        await client.send_message(peer, body.message)
        touch_conversation(user_id, body.message)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
