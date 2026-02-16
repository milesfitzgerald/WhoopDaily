"""
WHOOP OAuth2 Auth Setup
Opens browser for authorization, captures the callback, and prints your refresh token.
"""

import http.server
import os
import sys
import urllib.parse
import webbrowser

import requests

CLIENT_ID = os.environ.get("WHOOP_CLIENT_ID")
CLIENT_SECRET = os.environ.get("WHOOP_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8080/callback"
AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
SCOPES = "offline read:recovery read:cycles read:sleep read:profile"


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Authorization successful!</h1><p>You can close this tab.</p>")
            self.server.auth_code = code
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Error</h1><p>No authorization code received.</p>")
            self.server.auth_code = None

    def log_message(self, format, *args):
        pass  # Suppress request logging


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Error: Set WHOOP_CLIENT_ID and WHOOP_CLIENT_SECRET environment variables.")
        sys.exit(1)

    # Build authorization URL
    auth_params = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
    })
    full_auth_url = f"{AUTH_URL}?{auth_params}"

    print("Opening browser for WHOOP authorization...")
    webbrowser.open(full_auth_url)

    # Start local server to capture callback
    server = http.server.HTTPServer(("localhost", 8080), CallbackHandler)
    server.auth_code = None
    server.handle_request()

    if not server.auth_code:
        print("Error: No authorization code received.")
        sys.exit(1)

    print("Got authorization code. Exchanging for tokens...")

    # Exchange code for tokens
    response = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": server.auth_code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
    })

    if response.status_code != 200:
        print(f"Error exchanging code: {response.status_code} {response.text}")
        sys.exit(1)

    tokens = response.json()
    refresh_token = tokens.get("refresh_token")

    print("\n" + "=" * 60)
    print("YOUR REFRESH TOKEN (save this!):")
    print("=" * 60)
    print(refresh_token)
    print("=" * 60)
    print("\nAdd this as WHOOP_REFRESH_TOKEN in your GitHub repository secrets.")


if __name__ == "__main__":
    main()
