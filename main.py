"""Entry point — scheduler and main cron logic for review card automation."""

import logging
import sys
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

import config
import google_reviews
import hubspot_lookup
import handwrytten_send
import supabase_db
import slack_notify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def process_new_reviews():
    """Step 3a: Poll GBP for 5-star reviews and insert new ones into Supabase."""
    logger.info("Polling Google Business Profile for new 5-star reviews...")
    try:
        reviews = google_reviews.poll_five_star_reviews()
    except Exception:
        logger.exception("Failed to poll GBP reviews")
        slack_notify.notify_error("Failed to poll GBP reviews \u2014 check logs")
        return 0

    new_count = 0
    for review in reviews:
        if supabase_db.review_exists(review["review_id"]):
            continue
        supabase_db.insert_review(review)
        new_count += 1
        logger.info("New 5-star review from %s", review["reviewer_name"])

    logger.info("Inserted %d new 5-star reviews", new_count)
    return new_count


def match_pending_reviews():
    """Step 3b: Match pending reviews to HubSpot contacts."""
    pending = supabase_db.get_reviews_by_status("pending")
    logger.info("Matching %d pending reviews to HubSpot contacts...", len(pending))

    for review in pending:
        review_id = review["review_id"]
        reviewer_name = review["reviewer_name"]

        try:
            match = hubspot_lookup.match_contact(reviewer_name)
        except Exception:
            logger.exception("HubSpot lookup failed for %s", reviewer_name)
            continue  # Leave as pending, retry next cycle

        if match is None:
            supabase_db.mark_no_match(review_id)
            slack_notify.notify_no_match(
                reviewer_name,
                review.get("gbp_location", "Unknown"),
                review.get("review_text", ""),
            )
        elif match["address"] is None:
            supabase_db.mark_no_address(review_id, match["contact_id"])
            slack_notify.notify_no_address(
                reviewer_name,
                match["contact_id"],
                review.get("gbp_location", "Unknown"),
            )
        else:
            supabase_db.mark_matched(review_id, match["contact_id"], match["address"])
            logger.info("Matched %s to HubSpot contact %s", reviewer_name, match["contact_id"])


def send_matched_cards():
    """Step 3c: Send Handwrytten cards for matched reviews."""
    matched = supabase_db.get_reviews_by_status("matched")
    logger.info("Sending cards for %d matched reviews...", len(matched))

    for review in matched:
        review_id = review["review_id"]
        reviewer_name = review["reviewer_name"]
        address = review.get("contact_address", {})
        if not address:
            logger.warning("No address for matched review %s", review_id)
            continue

        try:
            result = handwrytten_send.send_card(
                recipient_name=reviewer_name,
                street=address["street"],
                city=address["city"],
                state=address["state"],
                zip_code=address.get("zip", ""),
            )
            supabase_db.mark_sent(review_id, result["order_id"])
            slack_notify.notify_card_sent(
                reviewer_name,
                review.get("gbp_location", "Unknown"),
                address["city"],
                address["state"],
            )
        except Exception as e:
            logger.exception("Failed to send card for %s", reviewer_name)
            supabase_db.mark_failed(review_id, str(e))


def retry_failed_cards():
    """Retry failed card sends (up to 3 attempts across cycles)."""
    candidates = supabase_db.get_retry_candidates()
    if not candidates:
        return

    logger.info("Retrying %d failed card sends...", len(candidates))
    for review in candidates:
        review_id = review["review_id"]
        reviewer_name = review["reviewer_name"]
        address = review.get("contact_address", {})
        retry_count = review.get("_retry_count", 0)

        if not address:
            continue

        try:
            result = handwrytten_send.send_card(
                recipient_name=reviewer_name,
                street=address["street"],
                city=address["city"],
                state=address["state"],
                zip_code=address.get("zip", ""),
            )
            supabase_db.mark_sent(review_id, result["order_id"])
            slack_notify.notify_card_sent(
                reviewer_name,
                review.get("gbp_location", "Unknown"),
                address["city"],
                address["state"],
            )
        except Exception as e:
            logger.exception("Retry failed for %s (attempt %d)", reviewer_name, retry_count + 1)
            supabase_db.increment_retry(review_id, str(e), retry_count)


def run_cycle():
    """Run one full cycle: poll -> match -> send -> retry."""
    logger.info("=== Starting review card cycle at %s ===", datetime.utcnow().isoformat())
    try:
        process_new_reviews()
        match_pending_reviews()
        send_matched_cards()
        retry_failed_cards()
    except Exception:
        logger.exception("Unhandled error in review card cycle")
        slack_notify.notify_error("Unhandled error in review card cycle \u2014 check logs")
    logger.info("=== Cycle complete ===")


def weekly_summary():
    """Send the weekly summary to Slack."""
    logger.info("Sending weekly summary...")
    try:
        counts = supabase_db.get_weekly_summary()
        slack_notify.notify_weekly_summary(counts)
    except Exception:
        logger.exception("Failed to send weekly summary")


def main():
    # Validate required config
    missing = []
    for var in [
        "GOOGLE_REFRESH_TOKEN",
        "HUBSPOT_ACCESS_TOKEN",
        "HANDWRYTTEN_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "SLACK_WEBHOOK_URL",
    ]:
        if not getattr(config, var):
            missing.append(var)
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(1)

    # Discover Handwrytten template at startup
    card_id = handwrytten_send.discover_template_id()
    if card_id is None:
        logger.error("Could not find Handwrytten template. Exiting.")
        sys.exit(1)
    logger.info("Using Handwrytten card ID: %s", card_id)

    if config.DRY_RUN:
        logger.info("*** DRY RUN MODE — cards will NOT be sent ***")

    # Run once immediately
    run_cycle()

    # Schedule recurring runs
    scheduler = BlockingScheduler()

    # Every 30 minutes
    scheduler.add_job(run_cycle, "interval", minutes=30, id="review_cycle")

    # Weekly summary: Monday 9:00 AM Central (UTC-5 / UTC-6 depending on DST)
    # Using America/Chicago timezone
    scheduler.add_job(
        weekly_summary,
        CronTrigger(day_of_week="mon", hour=9, minute=0, timezone="America/Chicago"),
        id="weekly_summary",
    )

    logger.info("Scheduler started. Running every 30 minutes.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
