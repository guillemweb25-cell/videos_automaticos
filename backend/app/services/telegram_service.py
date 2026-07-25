"""Tiny Telegram notifier for pipeline events.

Sends a plain-text message via the Telegram Bot API. It is intentionally
fire-and-forget: any failure (missing config, network error, bad token) is
swallowed and logged, so a notification problem can NEVER break or abort the
video pipeline.

Requires two values in .env:
    TELEGRAM_BOT_TOKEN=<token del bot, de @BotFather>
    TELEGRAM_CHAT_ID=<id del chat destino>
"""
import requests

from app.config import get_settings


def send_telegram(text: str) -> bool:
    """Send `text` to the configured Telegram chat. Never raises.
    Returns True if the message was accepted by Telegram, False otherwise
    (including when Telegram is not configured)."""
    try:
        settings = get_settings()
        token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
        chat_id = getattr(settings, "TELEGRAM_CHAT_ID", None)
        if not token or not chat_id:
            return False  # Telegram not configured — silently skip.

        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        if r.status_code != 200:
            print(f"[telegram] sendMessage {r.status_code}: {r.text[:200]}", flush=True)
            return False
        return True
    except Exception as e:  # noqa: BLE001 - notifications must never crash the pipeline
        print(f"[telegram] notify failed: {type(e).__name__}: {e}", flush=True)
        return False
