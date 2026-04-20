# app/retriever.py

import json
from pathlib import Path
from app.config import STATIC_DATA_DIR

def load_agents_constitution() -> str:
    path = STATIC_DATA_DIR / "transport_rules" / "AGENTS.md"
    return path.read_text(encoding="utf-8")

def load_social_knowledge() -> dict:
    path = STATIC_DATA_DIR / "social_media_knowledge" / "AGENTS_Knowledge_FromSocialMedia.json"
    return json.loads(path.read_text(encoding="utf-8"))