"""Slack webhook notifications."""

import logging

import requests

import config

logger = logging.getLogger(__name__)


def _send(text: str):
    if not config.SLACK_WEBHOOK_URL:
        logger.warning("SLACK_WEBHOOK_URL not set, skipping notification")
        return
    try:
        resp = requests.post(
            config.SLACK_WEBHOOK_URL, json={"text": text}, timeout=10
        )
        resp.raise_for_status()
    except Exception:
        logger.exception("Failed to send Slack notification")


def notify_card_sent(name: str, location: str, city: str, state: str):
    _send(
        f":white_check_mark: *Handwritten card sent!*\n"
        f"Reviewer: {name}\n"
        f"Location: {location}\n"
        f"Address: {city}, {state}"
    )


def notify_no_match(name: str, location: str, review_text: str):
    snippet = (review_text or "")[:100]
    if len(review_text or "") > 100:
        snippet += "..."
    _send(
        f":warning: *5-star review \u2014 no HubSpot match*\n"
        f"Reviewer: {name}\n"
        f"Location: {location}\n"
        f'Review: "{snippet}"\n'
        f"\u2192 Manual lookup needed"
    )


def notify_no_address(name: str, contact_id: str, location: str):
    contact_link = (
        f"https://app.hubspot.com/contacts/{config.HUBSPOT_PORTAL_ID}"
        f"/contact/{contact_id}"
    )
    _send(
        f":warning: *5-star review \u2014 matched but no address*\n"
        f"Reviewer: {name}\n"
        f"HubSpot: {contact_link}\n"
        f"Location: {location}\n"
        f"\u2192 Address needed to send card"
    )


def notify_weekly_summary(counts: dict):
    _send(
        f":bar_chart: *Review Card Weekly Summary*\n"
        f"Cards sent: {counts.get('sent', 0)}\n"
        f"No HubSpot match: {counts.get('no_match', 0)}\n"
        f"Matched but no address: {counts.get('no_address', 0)}\n"
        f"Failed: {counts.get('failed', 0)}\n"
        f"Total 5-star reviews: {counts.get('total', 0)}"
    )


def notify_error(message: str):
    _send(f":rotating_light: *Review Card Automation Error*\n{message}")
