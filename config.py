"""Configuration loaded from environment variables."""

import os


# Google Business Profile OAuth
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_PROJECT_ID = os.environ.get("GOOGLE_PROJECT_ID", "ads-automation-492017")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")

# HubSpot
HUBSPOT_ACCESS_TOKEN = os.environ.get("HUBSPOT_ACCESS_TOKEN", "")
HUBSPOT_PORTAL_ID = "50278916"

# Handwrytten
HANDWRYTTEN_API_KEY = os.environ.get("HANDWRYTTEN_API_KEY", "")
HANDWRYTTEN_TEMPLATE_NAME = "5 star review / refer"

# Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# Slack
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

# Dry run mode — does everything except actually sending via Handwrytten
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"

# Sender info for Handwrytten cards
SENDER_NAME = "David Patton & the Pure Turf Team"

# Default card message (used only if the API requires a message body)
CARD_MESSAGE = (
    "Thank you for the kind review \u2014 we love taking care of your lawn. "
    "If you have any friends or neighbors who'd like the same results, "
    "they can get a free estimate at the link below. We'll credit your "
    "account $50 when they sign up.\n\n"
    "pureturfllc.com/refer"
)
