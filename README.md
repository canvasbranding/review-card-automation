# Pure Turf — 5-Star Review Card Automation

Automatically sends a handwritten thank-you card (via Handwrytten) to every customer who leaves a 5-star Google review, if they can be matched to a HubSpot contact with a valid mailing address.

## Setup

### 1. Create the Supabase table

Run `schema.sql` in the Supabase SQL Editor.

### 2. Get Google OAuth refresh token

```bash
pip install -r requirements.txt
export GOOGLE_CLIENT_ID="494434425724-..."
export GOOGLE_CLIENT_SECRET="GOCSPX-..."
python auth_setup.py
```

Copy the refresh token and set it as `GOOGLE_REFRESH_TOKEN` in Railway.

### 3. Railway environment variables

| Variable | Description |
|---|---|
| `GOOGLE_CLIENT_ID` | GBP OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | GBP OAuth client secret |
| `GOOGLE_REFRESH_TOKEN` | From auth_setup.py |
| `HUBSPOT_ACCESS_TOKEN` | Pure Turf HubSpot token |
| `HANDWRYTTEN_API_KEY` | Handwrytten API key |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase service key |
| `SLACK_WEBHOOK_URL` | Slack webhook URL |
| `DRY_RUN` | `true` (default) or `false` |

### 4. Deploy

Push to Railway. The service runs every 30 minutes automatically.

### 5. Go live

Set `DRY_RUN=false` in Railway env vars once testing is confirmed.

## How it works

Every 30 minutes:
1. Polls all Pure Turf GBP locations for 5-star reviews
2. Matches reviewers to HubSpot contacts by name
3. Sends handwritten cards via Handwrytten for matched contacts with addresses
4. Retries failed sends (up to 3 attempts)
5. Sends Slack notifications for each outcome

Weekly summary sent to Slack on Mondays at 9:00 AM Central.
