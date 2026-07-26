"""Resolve a channel's assigned LoRAs into the payload the ComfyUI injection
expects, plus the concatenated trigger words for the positive prompt."""
from typing import List, Dict, Tuple

from sqlalchemy.orm import Session

from app.models.lora import Lora


def resolve_channel_loras(db: Session, channel) -> Tuple[List[Dict], str]:
    """Return (loras_payload, trigger_words) for a channel.

    loras_payload preserves the order stored in `channel.loras` (order matters:
    it's the LoraLoader chain order). trigger_words is the LoRAs' trigger words
    joined with commas, ready to prepend to the positive prompt.
    Returns ([], "") when the channel has no LoRAs.
    """
    ids = getattr(channel, "loras", None) or []
    if not ids:
        return [], ""

    rows = db.query(Lora).filter(Lora.id.in_(ids)).all()
    by_id = {r.id: r for r in rows}

    payload: List[Dict] = []
    triggers: List[str] = []
    for lid in ids:  # preserve the channel's ordering
        r = by_id.get(lid)
        if not r:
            continue
        payload.append({
            "filename": r.filename,
            "model_strength": r.model_strength,
            "clip_strength": r.clip_strength,
            "label": r.label,
        })
        if r.trigger_words and r.trigger_words.strip():
            triggers.append(r.trigger_words.strip())

    return payload, ", ".join(triggers)
