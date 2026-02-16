# WhoopDaily

Get a daily WhatsApp (or SMS) message with your WHOOP recovery, sleep, and strain data — plus actionable recommendations.

```
📊 WHOOP Daily — Monday, Feb 16

🟡 Recovery: 55%  Yellow zone — moderate effort
   HRV: 18.8 ms | RHR: 72 bpm

😴 Sleep: 7h 04m of 7h 31m needed
   Decent — 0h 27m short
   Performance: 84% | Efficiency: 91%
   Light: 3h 52m | Deep: 1h 30m | REM: 1h 40m

🔥 Strain: 7.4  Light

Today's Plan:
⚠️ Moderate effort today — aim for 10-14 strain
🛏 Bedtime tonight: 23:15 (extra 0h 27m to catch up)
```

## How It Works

WHOOP API v2 → Python → Twilio → WhatsApp/SMS to your phone

Runs daily via GitHub Actions (free). Refresh tokens auto-rotate so it never breaks.

## Setup

### 1. WHOOP Developer App

1. Go to [developer-dashboard.whoop.com](https://developer-dashboard.whoop.com)
2. Log in and click **Create App**
3. Set redirect URI to `http://localhost:8080/callback`
4. Note your **Client ID** and **Client Secret**
5. Request scopes: `read:recovery`, `read:cycles`, `read:sleep`, `read:profile`

### 2. Get Your Refresh Token

```bash
export WHOOP_CLIENT_ID="your_client_id"
export WHOOP_CLIENT_SECRET="your_client_secret"

pip install requests
python auth_setup.py
```

Authorize in the browser. The script prints your refresh token — save it.

### 3. Twilio Setup

1. Sign up at [twilio.com](https://www.twilio.com) (free trial or paid)
2. For **WhatsApp**: Go to Messaging → Try it out → Send a WhatsApp message. Join the sandbox from your phone.
3. For **SMS**: Get a phone number from Twilio (paid account required for multi-segment messages to international numbers)
4. Note your **Account SID**, **Auth Token**, and **Twilio number**

### 4. GitHub Personal Access Token

1. Go to [github.com/settings/tokens?type=beta](https://github.com/settings/tokens?type=beta)
2. Generate a new fine-grained token
3. Scope it to this repository only
4. Grant **Secrets: Read and write** permission

This allows the script to auto-rotate the WHOOP refresh token on each run.

### 5. Add Repository Secrets

Go to your repo → **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|--------|-------|
| `WHOOP_CLIENT_ID` | From step 1 |
| `WHOOP_CLIENT_SECRET` | From step 1 |
| `WHOOP_REFRESH_TOKEN` | From step 2 |
| `TWILIO_ACCOUNT_SID` | From Twilio console |
| `TWILIO_AUTH_TOKEN` | From Twilio console |
| `TWILIO_FROM_NUMBER` | `whatsapp:+14155238886` (sandbox) or your Twilio number |
| `MY_PHONE_NUMBER` | `whatsapp:+1234567890` or `+1234567890` for SMS |
| `GH_PAT` | From step 4 |

### 6. Test

Go to **Actions → WHOOP Daily Summary → Run workflow**

## Schedule

The workflow runs daily at **9:00 AM CET (Barcelona)**. To change the time, edit the cron in `.github/workflows/daily-summary.yml`:

| Timezone | 9:00 AM local | Cron |
|----------|--------------|------|
| CET (UTC+1) | 08:00 UTC | `0 8 * * *` |
| EST (UTC-5) | 14:00 UTC | `0 14 * * *` |
| CST (UTC-6) | 15:00 UTC | `0 15 * * *` |
| PST (UTC-8) | 17:00 UTC | `0 17 * * *` |

## Token Auto-Rotation

WHOOP refresh tokens are single-use — each time one is exchanged for an access token, WHOOP issues a new refresh token. The script automatically updates the `WHOOP_REFRESH_TOKEN` GitHub secret on every run via the GitHub API, so you never need to manually refresh it.

## WhatsApp Sandbox Note

If using the Twilio WhatsApp sandbox, the session expires after **72 hours of inactivity**. Since this runs daily, it stays active. If you miss messages, re-send the `join` code to the Twilio WhatsApp number.

## Cost

| Service | Cost |
|---------|------|
| WHOOP API | Free |
| GitHub Actions | Free (uses ~1 min/day of 2,000 min/month) |
| Twilio WhatsApp | ~$0.005/message (~$0.15/month) |
| Twilio SMS | ~$0.01-0.10/message depending on destination |

## Files

| File | Description |
|------|-------------|
| `whoop_summary.py` | Main script — fetches WHOOP data, builds summary, sends via Twilio |
| `auth_setup.py` | One-time OAuth setup to get your initial refresh token |
| `requirements.txt` | Python dependencies |
| `.github/workflows/daily-summary.yml` | GitHub Actions workflow for daily scheduling |
