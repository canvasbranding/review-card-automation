"""Handwrytten API integration for sending handwritten cards."""

import logging

import requests

import config

logger = logging.getLogger(__name__)

BASE_URL = "https://api.handwrytten.com/v1"

# Dark Border Thank You card
CARD_ID = 2661


def send_card(
    recipient_name: str,
    street: str,
    city: str,
    state: str,
    zip_code: str,
    message: str | None = None,
) -> dict:
    """Send a handwritten card via Handwrytten.

    Returns dict with 'order_id' on success, or raises on failure.
    """
    if config.DRY_RUN:
        logger.info(
            "[DRY RUN] Would send card to %s at %s, %s, %s %s",
            recipient_name,
            street,
            city,
            state,
            zip_code,
        )
        return {"order_id": "DRY_RUN_ORDER"}

    # Parse recipient name
    name_parts = recipient_name.strip().split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    # Parse sender name
    sender_parts = config.SENDER_NAME.strip().split(" ", 1)
    sender_first = sender_parts[0]
    sender_last = sender_parts[1] if len(sender_parts) > 1 else ""

    payload = {
        "login": config.HANDWRYTTEN_API_KEY,
        "card_id": CARD_ID,
        "message": message or config.CARD_MESSAGE,
        "recipient_name": recipient_name,
        "recipient_first_name": first_name,
        "recipient_last_name": last_name,
        "recipient_street1": street,
        "recipient_city": city,
        "recipient_state": state,
        "recipient_zip": zip_code,
        "recipient_country": "US",
        "sender_name": config.SENDER_NAME,
        "sender_first_name": sender_first,
        "sender_last_name": sender_last,
    }

    url = f"{BASE_URL}/orders/single"
    resp = requests.post(url, json=payload, timeout=30)

    if not resp.ok:
        error_text = resp.text[:500]
        logger.error("Handwrytten send failed: %s %s", resp.status_code, error_text)
        raise RuntimeError(f"Handwrytten API error {resp.status_code}: {error_text}")

    result = resp.json()
    order_id = str(
        result.get("id")
        or result.get("order_id")
        or result.get("order", {}).get("id", "unknown")
    )
    logger.info("Handwrytten card sent, order ID: %s", order_id)
    return {"order_id": order_id}
