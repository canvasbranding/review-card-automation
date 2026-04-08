"""Supabase database operations for review_cards table."""

import logging
from datetime import datetime, timezone

from supabase import create_client

import config

logger = logging.getLogger(__name__)

_client = None


def get_client():
    global _client
    if _client is None:
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    return _client


def review_exists(review_id: str) -> bool:
    """Check if a review has already been processed."""
    result = (
        get_client()
        .table("review_cards")
        .select("id")
        .eq("review_id", review_id)
        .execute()
    )
    return len(result.data) > 0


def insert_review(review: dict) -> dict:
    """Insert a new 5-star review with status 'pending'."""
    row = {
        "review_id": review["review_id"],
        "reviewer_name": review["reviewer_name"],
        "star_rating": review["star_rating"],
        "review_text": review.get("review_text"),
        "gbp_location": review.get("gbp_location"),
        "status": "pending",
    }
    result = get_client().table("review_cards").insert(row).execute()
    return result.data[0] if result.data else row


def get_reviews_by_status(status: str) -> list[dict]:
    """Get all reviews with a given status."""
    result = (
        get_client()
        .table("review_cards")
        .select("*")
        .eq("status", status)
        .execute()
    )
    return result.data


def update_review(review_id: str, updates: dict):
    """Update a review record by review_id."""
    get_client().table("review_cards").update(updates).eq(
        "review_id", review_id
    ).execute()


def mark_matched(review_id: str, contact_id: str, address: dict):
    update_review(
        review_id,
        {
            "status": "matched",
            "hubspot_contact_id": contact_id,
            "contact_address": address,
        },
    )


def mark_no_match(review_id: str):
    update_review(review_id, {"status": "no_match"})


def mark_no_address(review_id: str, contact_id: str):
    update_review(
        review_id, {"status": "no_address", "hubspot_contact_id": contact_id}
    )


def mark_sent(review_id: str, order_id: str):
    update_review(
        review_id,
        {
            "status": "sent",
            "handwrytten_order_id": order_id,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def mark_failed(review_id: str, error: str):
    update_review(review_id, {"status": "failed", "error_message": error})


def get_retry_candidates() -> list[dict]:
    """Get failed reviews that have been retried fewer than 3 times.

    We count retries by checking if error_message contains a retry count prefix.
    """
    result = (
        get_client()
        .table("review_cards")
        .select("*")
        .eq("status", "failed")
        .execute()
    )
    candidates = []
    for row in result.data:
        error = row.get("error_message", "") or ""
        retry_count = 0
        if error.startswith("[retry:"):
            try:
                retry_count = int(error.split("]")[0].split(":")[1])
            except (IndexError, ValueError):
                pass
        if retry_count < 3:
            row["_retry_count"] = retry_count
            candidates.append(row)
    return candidates


def increment_retry(review_id: str, error: str, current_count: int):
    """Mark as failed with incremented retry count."""
    mark_failed(review_id, f"[retry:{current_count + 1}] {error}")


def get_weekly_summary() -> dict:
    """Get counts by status for the weekly summary."""
    result = get_client().table("review_cards").select("status").execute()
    counts = {"sent": 0, "no_match": 0, "no_address": 0, "failed": 0, "total": 0}
    for row in result.data:
        counts["total"] += 1
        status = row["status"]
        if status in counts:
            counts[status] += 1
    return counts
