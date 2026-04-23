"""Google Business Profile API — discover locations and poll reviews."""

import logging

import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

import config
import slack_notify

logger = logging.getLogger(__name__)

TOKEN_URI = "https://oauth2.googleapis.com/token"
GBP_ACCOUNTS_BASE = "https://mybusinessaccountmanagement.googleapis.com/v1"
GBP_LOCATIONS_BASE = "https://mybusinessbusinessinformation.googleapis.com/v1"
GBP_REVIEWS_BASE = "https://mybusiness.googleapis.com/v4"

_credentials = None


def _get_credentials() -> Credentials:
    """Get valid OAuth credentials, refreshing if needed."""
    global _credentials
    if _credentials is None or not _credentials.valid:
        _credentials = Credentials(
            token=None,
            refresh_token=config.GOOGLE_REFRESH_TOKEN,
            token_uri=TOKEN_URI,
            client_id=config.GOOGLE_CLIENT_ID,
            client_secret=config.GOOGLE_CLIENT_SECRET,
        )
        _credentials.refresh(Request())
    return _credentials


def _auth_headers() -> dict:
    creds = _get_credentials()
    return {"Authorization": f"Bearer {creds.token}"}


def _handle_auth_error(resp: requests.Response) -> bool:
    """Handle 401/403 errors. Returns True if caller should retry."""
    if resp.status_code == 401:
        global _credentials
        _credentials = None  # Force re-auth on next call
        return True
    if resp.status_code == 403:
        slack_notify.notify_error(
            "GBP API access lost \u2014 check OAuth.\n"
            f"Response: {resp.text[:200]}"
        )
        return False
    return False


def discover_accounts() -> list[str]:
    """Discover all GBP account names the user has access to."""
    url = f"{GBP_ACCOUNTS_BASE}/accounts"
    resp = requests.get(url, headers=_auth_headers(), timeout=30)

    if resp.status_code == 401:
        if _handle_auth_error(resp):
            resp = requests.get(url, headers=_auth_headers(), timeout=30)

    if not resp.ok:
        _handle_auth_error(resp)
        logger.error("Failed to list accounts: %s %s", resp.status_code, resp.text)
        return []

    accounts = resp.json().get("accounts", [])
    if not accounts:
        logger.error("No GBP accounts found")
        return []

    logger.info("Discovered %d GBP account(s)", len(accounts))
    for acc in accounts:
        logger.info(
            "  - %s (%s)", acc.get("accountName", "?"), acc["name"]
        )
    return [acc["name"] for acc in accounts]


def discover_locations(account_name: str) -> list[dict]:
    """Discover all locations for the account."""
    url = f"{GBP_LOCATIONS_BASE}/{account_name}/locations"
    params = {"readMask": "name,title,storefrontAddress"}
    resp = requests.get(url, headers=_auth_headers(), params=params, timeout=30)

    if resp.status_code == 401:
        if _handle_auth_error(resp):
            resp = requests.get(
                url, headers=_auth_headers(), params=params, timeout=30
            )

    if not resp.ok:
        _handle_auth_error(resp)
        logger.error("Failed to list locations: %s %s", resp.status_code, resp.text)
        return []

    locations = resp.json().get("locations", [])
    logger.info("Discovered %d location(s) under %s", len(locations), account_name)
    for loc in locations:
        logger.info("  - %s (%s)", loc.get("title", "?"), loc["name"])
    return locations


def fetch_reviews(account_name: str, location_name: str) -> list[dict]:
    """Fetch recent reviews for a location, ordered by update time."""
    # location_name is like "locations/12345", we need "accounts/X/locations/Y"
    full_name = f"{account_name}/{location_name}"
    url = f"{GBP_REVIEWS_BASE}/{full_name}/reviews"
    params = {"orderBy": "updateTime desc", "pageSize": 50}

    resp = requests.get(url, headers=_auth_headers(), params=params, timeout=30)

    if resp.status_code == 401:
        if _handle_auth_error(resp):
            resp = requests.get(
                url, headers=_auth_headers(), params=params, timeout=30
            )

    if not resp.ok:
        _handle_auth_error(resp)
        logger.error(
            "Failed to fetch reviews for %s: %s %s",
            location_name,
            resp.status_code,
            resp.text,
        )
        return []

    return resp.json().get("reviews", [])


def parse_review(review: dict, location_title: str) -> dict | None:
    """Parse a GBP review into our internal format. Returns None if not 5-star."""
    star_map = {
        "FIVE": 5,
        "FOUR": 4,
        "THREE": 3,
        "TWO": 2,
        "ONE": 1,
    }
    rating = star_map.get(review.get("starRating"), 0)
    if rating != 5:
        return None

    reviewer = review.get("reviewer", {})
    return {
        "review_id": review["reviewId"],
        "reviewer_name": reviewer.get("displayName", "Unknown"),
        "star_rating": 5,
        "review_text": review.get("comment", ""),
        "gbp_location": location_title,
    }


def poll_five_star_reviews() -> list[dict]:
    """Main entry point: discover locations and return new 5-star reviews."""
    accounts = discover_accounts()
    if not accounts:
        return []

    five_star = []
    for account_name in accounts:
        locations = discover_locations(account_name)
        if not locations:
            continue

        for loc in locations:
            location_name = loc["name"]
            location_title = loc.get("title", location_name)
            reviews = fetch_reviews(account_name, location_name)
            logger.info(
                "Fetched %d reviews from %s", len(reviews), location_title
            )

            for review in reviews:
                parsed = parse_review(review, location_title)
                if parsed:
                    five_star.append(parsed)

    logger.info(
        "Found %d total 5-star reviews across %d account(s)",
        len(five_star),
        len(accounts),
    )
    return five_star
