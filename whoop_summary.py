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

    # Recovery insight
    if recovery_score >= 67:
        rec_tip = "Green zone — push hard today"
    elif recovery_score >= 34:
        rec_tip = "Yellow zone — moderate effort"
    else:
        rec_tip = "Red zone — prioritize rest"

    # Sleep insight
    sleep_debt = sleep_needed_ms - total_sleep_ms if total_sleep_ms < sleep_needed_ms else 0
    if sleep_perf >= 85:
        sleep_tip = "Great sleep"
    elif sleep_perf >= 70:
        sleep_tip = f"Decent — {format_duration(sleep_debt)} short" if sleep_debt else "Decent"
    else:
        sleep_tip = f"Low — {format_duration(sleep_debt)} short" if sleep_debt else "Low"

    # Strain insight & recommendation
    if strain >= 18:
        strain_tip = "All out"
    elif strain >= 14:
        strain_tip = "High — good training day"
    elif strain >= 10:
        strain_tip = "Moderate"
    elif strain >= 7:
        strain_tip = "Light"
    else:
        strain_tip = "Minimal"

    # Strain recommendation based on recovery
    if recovery_score >= 67:
        if strain < 14:
            strain_rec = "\U0001F4AA You can push harder — aim for 14+ strain today"
        else:
            strain_rec = "\U0001F4AA Strong day — keep it up"
    elif recovery_score >= 34:
        if strain < 10:
            strain_rec = "\u26A0\uFE0F Moderate effort today — aim for 10-14 strain"
        else:
            strain_rec = "\u26A0\uFE0F Good effort — don't overdo it today"
    else:
        strain_rec = "\U0001F6D1 Recovery day — keep strain under 10"

    # Bedtime recommendation
    # Calculate ideal bedtime: need to get sleep_needed_ms of actual sleep
    # Account for sleep efficiency (time in bed vs actual sleep)
    if sleep_eff and sleep_eff > 0:
        # Time in bed needed = sleep needed / efficiency
        bed_time_needed_ms = sleep_needed_ms / (sleep_eff / 100)
    else:
        bed_time_needed_ms = sleep_needed_ms * 1.1  # assume 90% efficiency

    bed_time_needed_min = int(bed_time_needed_ms / 60000)
    bed_hours = bed_time_needed_min // 60
    bed_mins = bed_time_needed_min % 60

    # Assuming 9:00 AM wake time (Barcelona), work backwards
    # Wake at 7:30 AM, subtract bed time needed
    wake_hour, wake_min = 7, 30
    total_wake_min = wake_hour * 60 + wake_min
    bedtime_min = total_wake_min - bed_time_needed_min
    if bedtime_min < 0:
        bedtime_min += 24 * 60
    bt_hour = bedtime_min // 60
    bt_min = bedtime_min % 60
    bedtime_str = f"{bt_hour}:{bt_min:02d}"

    # Sleep debt recommendation
    if sleep_debt > 0:
        debt_min = int(sleep_debt / 60000)
        early_min = debt_min  # go to bed earlier by the debt amount
        early_bt_min = bedtime_min - early_min
        if early_bt_min < 0:
            early_bt_min += 24 * 60
        early_hour = early_bt_min // 60
        early_minute = early_bt_min % 60
        sleep_rec = f"\U0001F6CF Bedtime tonight: {early_hour}:{early_minute:02d} (extra {format_duration(sleep_debt)} to catch up)"
    else:
        sleep_rec = f"\U0001F6CF Bedtime tonight: {bedtime_str}"

    message = (
        f"\U0001F4CA WHOOP Daily — {day_name}\n\n"
        f"{emoji} Recovery: {int(recovery_score)}%  _{rec_tip}_\n"
        f"   HRV: {hrv:.1f} ms | RHR: {int(rhr)} bpm\n\n"
        f"\U0001F634 Sleep: {format_duration(total_sleep_ms)} of {format_duration(sleep_needed_ms)} needed\n"
        f"   {sleep_tip}\n"
        f"   Performance: {int(sleep_perf)}% | Efficiency: {int(sleep_eff)}%\n"
        f"   Light: {format_duration(light_ms)} | Deep: {format_duration(deep_ms)} | REM: {format_duration(rem_ms)}\n\n"
        f"\U0001F525 Strain: {strain:.1f}  _{strain_tip}_\n\n"
        f"*Today's Plan:*\n"
        f"{strain_rec}\n"
        f"{sleep_rec}"
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
