"""
WHOOP Daily Summary → SMS/WhatsApp via Twilio
Fetches yesterday's recovery, sleep, and strain data from WHOOP and sends a text.
Auto-rotates the WHOOP refresh token via GitHub Actions API.
"""

import base64
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests
from nacl import encoding, public

# WHOOP API
WHOOP_CLIENT_ID = os.environ["WHOOP_CLIENT_ID"]
WHOOP_CLIENT_SECRET = os.environ["WHOOP_CLIENT_SECRET"]
WHOOP_REFRESH_TOKEN = os.environ["WHOOP_REFRESH_TOKEN"]
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
API_BASE = "https://api.prod.whoop.com/developer"

# Twilio
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM_NUMBER = os.environ["TWILIO_FROM_NUMBER"]
MY_PHONE_NUMBER = os.environ["MY_PHONE_NUMBER"]

# GitHub (for auto-rotating refresh token)
GITHUB_TOKEN = os.environ.get("GH_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "")


def encrypt_secret(public_key: str, secret_value: str) -> str:
    """Encrypt a secret using the repo's public key for GitHub Actions."""
    pk = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed = public.SealedBox(pk).encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(sealed).decode("utf-8")


def update_github_secret(secret_name: str, secret_value: str):
    """Update a GitHub Actions secret via the API."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print(f"Cannot auto-update secret (no GH_TOKEN or GITHUB_REPOSITORY).")
        return False

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    # Get the repo public key
    r = requests.get(
        f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets/public-key",
        headers=headers,
    )
    if r.status_code != 200:
        print(f"Failed to get repo public key: {r.status_code}")
        return False

    key_data = r.json()
    encrypted = encrypt_secret(key_data["key"], secret_value)

    # Update the secret
    r = requests.put(
        f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets/{secret_name}",
        headers=headers,
        json={"encrypted_value": encrypted, "key_id": key_data["key_id"]},
    )
    if r.status_code in (201, 204):
        print(f"Auto-updated {secret_name} in GitHub secrets.")
        return True
    else:
        print(f"Failed to update secret: {r.status_code} {r.text}")
        return False


def get_access_token():
    """Exchange refresh token for a fresh access token. Auto-rotates if WHOOP issues a new refresh token."""
    response = requests.post(TOKEN_URL, data={
        "grant_type": "refresh_token",
        "refresh_token": WHOOP_REFRESH_TOKEN,
        "client_id": WHOOP_CLIENT_ID,
        "client_secret": WHOOP_CLIENT_SECRET,
    })
    response.raise_for_status()
    data = response.json()

    new_refresh = data.get("refresh_token")
    if new_refresh and new_refresh != WHOOP_REFRESH_TOKEN:
        print("WHOOP issued a new refresh token. Auto-updating GitHub secret...")
        update_github_secret("WHOOP_REFRESH_TOKEN", new_refresh)

    return data["access_token"]


def whoop_get(endpoint, token, params=None):
    """Make an authenticated GET request to the WHOOP API."""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{API_BASE}{endpoint}", headers=headers, params=params)
    if response.status_code != 200:
        print(f"API error {response.status_code} for {endpoint}: {response.text}")
    response.raise_for_status()
    return response.json()


def get_recovery_emoji(score):
    if score >= 67:
        return "🟢"
    elif score >= 34:
        return "🟡"
    else:
        return "🔴"


def format_duration(ms):
    """Convert milliseconds to hours and minutes string."""
    if not ms:
        return "N/A"
    total_minutes = int(ms / 60000)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours}h {minutes:02d}m"


def get_day_name():
    """Get the day name for yesterday."""
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    return yesterday.strftime("%A, %b %d")


def build_summary(token):
    """Fetch WHOOP data and build the summary message."""
    # Date range for yesterday
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00.000Z")
    end = now.strftime("%Y-%m-%dT00:00:00.000Z")
    params = {"start": start, "end": end}

    # Fetch data using v2 API
    cycle_data = whoop_get("/v2/cycle", token, params)
    recovery_data = whoop_get("/v2/recovery", token, params)
    sleep_data = whoop_get("/v2/activity/sleep", token, params)

    # Parse cycle — get strain
    cycles = cycle_data.get("records", [])
    if cycles:
        cycle = cycles[0]
        strain = cycle.get("score", {}).get("strain", 0) or 0
    else:
        strain = 0

    # Parse recovery (separate endpoint in v2)
    recoveries = recovery_data.get("records", [])
    if recoveries:
        rec_score = recoveries[0].get("score", {})
        recovery_score = rec_score.get("recovery_score", 0) or 0
        hrv = rec_score.get("hrv_rmssd_milli", 0) or 0
        rhr = rec_score.get("resting_heart_rate", 0) or 0
    else:
        recovery_score, hrv, rhr = 0, 0, 0

    emoji = get_recovery_emoji(recovery_score)

    # Parse sleep
    sleeps = sleep_data.get("records", [])
    if sleeps:
        sl = sleeps[0].get("score", {})
        stages = sl.get("stage_summary", {})
        # Total sleep = in-bed minus awake
        in_bed_ms = stages.get("total_in_bed_time_milli", 0) or 0
        awake_ms = stages.get("total_awake_time_milli", 0) or 0
        total_sleep_ms = in_bed_ms - awake_ms
        sleep_needed = sl.get("sleep_needed", {})
        sleep_needed_ms = sleep_needed.get("baseline_milli", 0) or 0
        sleep_perf = sl.get("sleep_performance_percentage", 0) or 0
        sleep_eff = sl.get("sleep_efficiency_percentage", 0) or 0
        light_ms = stages.get("total_light_sleep_time_milli", 0) or 0
        deep_ms = stages.get("total_slow_wave_sleep_time_milli", 0) or 0
        rem_ms = stages.get("total_rem_sleep_time_milli", 0) or 0
    else:
        total_sleep_ms = sleep_needed_ms = sleep_perf = sleep_eff = 0
        light_ms = deep_ms = rem_ms = 0

    day_name = get_day_name()

    message = (
        f"\U0001F4CA WHOOP Daily — {day_name}\n\n"
        f"{emoji} Recovery: {int(recovery_score)}%\n"
        f"   HRV: {hrv:.1f} ms\n"
        f"   RHR: {int(rhr)} bpm\n\n"
        f"\U0001F634 Sleep: {format_duration(total_sleep_ms)} of {format_duration(sleep_needed_ms)} needed\n"
        f"   Performance: {int(sleep_perf)}%\n"
        f"   Efficiency: {int(sleep_eff)}%\n"
        f"   Light: {format_duration(light_ms)} | Deep: {format_duration(deep_ms)} | REM: {format_duration(rem_ms)}\n\n"
        f"\U0001F525 Strain: {strain:.1f}"
    )

    return message


def send_sms(message):
    """Send SMS or WhatsApp message via Twilio."""
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    response = requests.post(url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), data={
        "From": TWILIO_FROM_NUMBER,
        "To": MY_PHONE_NUMBER,
        "Body": message,
    })
    response.raise_for_status()
    sid = response.json().get("sid")
    print(f"Message sent! SID: {sid}")


def main():
    print("Fetching WHOOP access token...")
    token = get_access_token()

    print("Building daily summary...")
    message = build_summary(token)

    print(f"\n{message}\n")

    print("Sending message via Twilio...")
    send_sms(message)

    print("Done!")


if __name__ == "__main__":
    main()
