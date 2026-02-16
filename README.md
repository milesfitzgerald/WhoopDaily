<p align="center">
  <pre align="center">
 __        ___                       ____        _ _
 \ \      / / |__   ___   ___  _ __ |  _ \  __ _(_) |_   _
  \ \ /\ / /| '_ \ / _ \ / _ \| '_ \| | | |/ _` | | | | | |
   \ V  V / | | | | (_) | (_) | |_) | |_| | (_| | | | |_| |
    \_/\_/  |_| |_|\___/ \___/| .__/|____/ \__,_|_|_|\__, |
                               |_|                    |___/
  </pre>
</p>

<p align="center">
  <b>Your WHOOP data, delivered to your phone every morning.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/WHOOP-API%20v2-000000?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJ3aGl0ZSI+PGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iMTAiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgZmlsbD0ibm9uZSIvPjwvc3ZnPg==" alt="WHOOP API">
  <img src="https://img.shields.io/badge/GitHub_Actions-Automated-2088FF?style=for-the-badge&logo=github-actions&logoColor=white" alt="GitHub Actions">
  <img src="https://img.shields.io/badge/Twilio-WhatsApp%20%2F%20SMS-F22F46?style=for-the-badge&logo=twilio&logoColor=white" alt="Twilio">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
</p>

---

## What You Get

Every morning, a WhatsApp message like this lands on your phone:

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

### Recovery Zones

| Zone | Score | Meaning |
|:----:|:-----:|---------|
| :green_circle: | 67-100% | **Green** — Push hard, your body is ready |
| :yellow_circle: | 34-66% | **Yellow** — Moderate effort, don't overdo it |
| :red_circle: | 0-33% | **Red** — Rest and recover |

---

## How It Works

```
                    Every morning at 9:00 AM
                            |
                            v
               +------------------------+
               |    GitHub Actions       |
               |    (cron scheduler)     |
               +------------------------+
                            |
                            v
               +------------------------+
               |    WHOOP API v2        |
               |                        |
               |  Recovery  Sleep       |
               |  Strain    HRV/RHR    |
               +------------------------+
                            |
                            v
               +------------------------+
               |    Python Script       |
               |                        |
               |  Parse + Insights +    |
               |  Recommendations       |
               +------------------------+
                            |
                            v
               +------------------------+
               |    Twilio API          |
               |                        |
               |  WhatsApp or SMS  -->  📱
               +------------------------+
```

> Refresh tokens auto-rotate on every run. Set it and forget it.

---

## Setup

### Step 1: WHOOP Developer App

1. Go to [developer-dashboard.whoop.com](https://developer-dashboard.whoop.com)
2. Log in and click **Create App**
3. Set redirect URI to `http://localhost:8080/callback`
4. Note your **Client ID** and **Client Secret**
5. Request scopes: `read:recovery`, `read:cycles`, `read:sleep`, `read:profile`

### Step 2: Get Your Refresh Token

```bash
export WHOOP_CLIENT_ID="your_client_id"
export WHOOP_CLIENT_SECRET="your_client_secret"

pip install requests
python auth_setup.py
```

Authorize in the browser. The script prints your refresh token — save it.

### Step 3: Twilio Setup

1. Sign up at [twilio.com](https://www.twilio.com) (free trial or paid)
2. For **WhatsApp**: Go to Messaging → Try it out → Send a WhatsApp message. Join the sandbox from your phone.
3. For **SMS**: Get a phone number from Twilio (paid account required for multi-segment messages to international numbers)
4. Note your **Account SID**, **Auth Token**, and **Twilio number**

### Step 4: GitHub Personal Access Token

1. Go to [github.com/settings/tokens?type=beta](https://github.com/settings/tokens?type=beta)
2. Generate a new fine-grained token
3. Scope it to this repository only
4. Grant **Secrets: Read and write** permission

> This allows the script to auto-rotate the WHOOP refresh token on each run.

### Step 5: Add Repository Secrets

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

### Step 6: Test

Go to **Actions → WHOOP Daily Summary → Run workflow**

---

## Schedule

The workflow runs daily at **9:00 AM CET (Barcelona)**. To change the time, edit the cron in `.github/workflows/daily-summary.yml`:

| Timezone | 9:00 AM local | Cron |
|:--------:|:-------------:|:----:|
| CET (UTC+1) | 08:00 UTC | `0 8 * * *` |
| EST (UTC-5) | 14:00 UTC | `0 14 * * *` |
| CST (UTC-6) | 15:00 UTC | `0 15 * * *` |
| PST (UTC-8) | 17:00 UTC | `0 17 * * *` |

---

## Token Auto-Rotation

```
Run 1:  refresh_token_A  -->  access_token + refresh_token_B  -->  saves B to GitHub
Run 2:  refresh_token_B  -->  access_token + refresh_token_C  -->  saves C to GitHub
Run 3:  refresh_token_C  -->  access_token + refresh_token_D  -->  saves D to GitHub
  ...forever
```

WHOOP refresh tokens are single-use. The script automatically saves the new token back to GitHub Secrets via the GitHub API, so you never need to touch it.

---

## WhatsApp Sandbox Note

If using the Twilio WhatsApp sandbox, the session expires after **72 hours of inactivity**. Since this runs daily, it stays active. If you miss messages, re-send the `join` code to the Twilio WhatsApp number.

---

## Cost

| Service | Cost | |
|---------|------|-|
| WHOOP API | Free | :white_check_mark: |
| GitHub Actions | Free | ~1 min/day of 2,000 min/month |
| Twilio WhatsApp | ~$0.15/month | ~$0.005/message |
| Twilio SMS | ~$0.30-3.00/month | depends on destination |

---

## Files

```
WhoopDaily/
├── .github/
│   └── workflows/
│       └── daily-summary.yml    # GitHub Actions cron + workflow
├── whoop_summary.py             # Main script: fetch, parse, send
├── auth_setup.py                # One-time OAuth token setup
├── auth_server.py               # OAuth callback helper
├── requirements.txt             # Python deps: requests, PyNaCl
└── README.md                    # You are here
```

---

<p align="center">
  Built with :coffee: and WHOOP data
</p>
