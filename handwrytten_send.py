"""Handwrytten API integration for sending handwritten cards."""

import logging

import requests

import config
import slack_notify

logger = logging.getLogger(__name__)

BASE_URL = "https://api.handwrytten.com/v1"

_card_id = None


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {config.HANDWRYTTEN_API_KEY}",
        "Content-Type": "application/json",
    }


def _auth_params() -> dict:
    """Some Handwrytten endpoints use query param auth."""
    return {"login": config.HANDWRYTTEN_API_KEY}


def discover_template_id() -> int | None:
    """Find the card/template ID matching HANDWRYTTEN_TEMPLATE_NAME.

    Must be called at startup. Returns the card ID or None.
    """
    global _card_id

    url = f"{BASE_URL}/cards/list"
    try:
        resp = requests.get(url, params=_auth_params(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logger.exception("Failed to list Handwrytten cards")
        slack_notify.notify_error(
            "Failed to list Handwrytten card templates \u2014 check API key"
        )
        return None

    # The response structure may vary; handle both list and nested formats
    cards = data if isinstance(data, list) else data.get("cards", data.get("results", []))

    target = config.HANDWRYTTEN_TEMPLATE_NAME.lower()
    for card in cards:
        name = (card.get("name") or card.get("title") or "").lower()
        if target in name:
            _card_id = card.get("id") or card.get("card_id")
            logger.info(
                "Found Handwrytten template '%s' with ID %s",
                card.get("name") or card.get("title"),
                _card_id,
            )
            return _card_id

    logger.error(
        "Handwrytten template '%s' not found. Available: %s",
        config.HANDWRYTTEN_TEMPLATE_NAME,
        [c.get("name") or c.get("title") for c in cards[:20]],
    )
    slack_notify.notify_error(
        f"Handwrytten template '{config.HANDWRYTTEN_TEMPLATE_NAME}' not found.\n"
        f"Available templates: {[c.get('name') or c.get('title') for c in cards[:10]]}"
    )
    return None


def get_card_id() -> int | None:
    return _card_id


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
    if _card_id is None:
        raise RuntimeError("Card template not discovered yet. Call discover_template_id() first.")

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
        "card_id": _card_id,
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
