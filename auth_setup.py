"""
One-time OAuth setup for Google Business Profile API.
Run this locally to get a refresh token for the cron service.
"""
import os
import json
import requests
 
CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
 
if not CLIENT_ID or not CLIENT_SECRET:
    print("ERROR: Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET env vars first.")
    exit(1)
 
SCOPE = "https://www.googleapis.com/auth/business.manage"
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
 
# Step 1: Build the auth URL
auth_url = (
    f"https://accounts.google.com/o/oauth2/auth?"
    f"client_id={CLIENT_ID}&"
    f"redirect_uri={REDIRECT_URI}&"
    f"scope={SCOPE}&"
    f"response_type=code&"
    f"access_type=offline&"
    f"prompt=consent"
)
 
print("\n=== Google Business Profile OAuth Setup ===\n")
print("1. Open this URL in your browser:\n")
print(auth_url)
print("\n2. Sign in with the Google account that manages Pure Turf's GBP.")
print("3. After authorizing, Google will show you an authorization code.")
print("4. Copy that code and paste it below.\n")
 
auth_code = input("Enter the authorization code: ").strip()
 
# Step 2: Exchange the code for tokens
token_response = requests.post(
    "https://oauth2.googleapis.com/token",
    data={
        "code": auth_code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    },
)
 
if token_response.status_code != 200:
    print(f"\nERROR: Token exchange failed: {token_response.text}")
    exit(1)
 
tokens = token_response.json()
refresh_token = tokens.get("refresh_token")
access_token = tokens.get("access_token")
 
if not refresh_token:
    print(f"\nERROR: No refresh token returned. Full response: {json.dumps(tokens, indent=2)}")
    exit(1)
 
print("\n=== SUCCESS ===\n")
print(f"Refresh Token: {refresh_token}")
print(f"\nAccess Token (temporary): {access_token[:50]}...")
print("\n--> Copy the Refresh Token above and set it as GOOGLE_REFRESH_TOKEN in Railway.")
 
# Quick test: list GBP accounts
print("\n=== Testing API Access ===\n")
headers = {"Authorization": f"Bearer {access_token}"}
resp = requests.get("https://mybusinessbusinessinformation.googleapis.com/v1/accounts", headers=headers)
if resp.status_code == 200:
    accounts = resp.json()
    print(f"Found accounts: {json.dumps(accounts, indent=2)}")
else:
    print(f"Account listing returned {resp.status_code}: {resp.text}")
    print("(This might be fine — the token works, but the API endpoint may differ.)")
