from fastapi import FastAPI
from core.storage import get_state

app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/state")
def state():
    state = get_state()
    return {"path": "data/state.json", "file_exists": True, "counts": len(state)}
