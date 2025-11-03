import httpx
import asyncio
from typing import Optional
from core.config import CHATBASE_API_KEY, CHATBASE_BOT_ID, CHATBASE_CONCURRENCY
from models.history import get_history

_sem = asyncio.Semaphore(CHATBASE_CONCURRENCY)

async def ask_chatbase(uid: int, latest_user_text: str) -> Optional[str]:
    if not CHATBASE_API_KEY or not CHATBASE_BOT_ID:
        return None

    messages = get_history(uid)
    messages.append({"role": "user", "content": latest_user_text})

    payload = {
        "chatbotId": CHATBASE_BOT_ID,
        "messages": messages,
        "conversationId": str(uid),
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {CHATBASE_API_KEY}",
        "Content-Type": "application/json",
    }

    async with _sem:
        async with httpx.AsyncClient(timeout=45) as http:
            r = await http.post("https://www.chatbase.co/api/v1/chat", json=payload, headers=headers)
            if r.status_code != 200:
                print("[Chatbase Error]", r.status_code, r.text)
                return None
            data = r.json()
            return data.get("text") or data.get("message") or data.get("reply")
