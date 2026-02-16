"""
Step 1: Run this script, then open the printed URL in your browser.
It will wait for the WHOOP callback and exchange the code for a refresh token.
"""

import http.server
import os
import sys
import urllib.parse

import requests

CLIENT_ID = os.environ.get("WHOOP_CLIENT_ID")
CLIENT_SECRET = os.environ.get("WHOOP_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8080/callback"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"

auth_code_result = {}


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            auth_code_result["code"] = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Authorization successful!</h1><p>You can close this tab.</p>")
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Error</h1><p>No authorization code received.</p>")

    def log_message(self, format, *args):
        pass


print("Starting server on http://localhost:8080 ...")
server = http.server.HTTPServer(("127.0.0.1", 8080), CallbackHandler)
print("Server is ready! Waiting for WHOOP callback...")
sys.stdout.flush()

server.handle_request()

if "code" not in auth_code_result:
    print("Error: No authorization code received.")
    sys.exit(1)

print("Got authorization code. Exchanging for tokens...")

response = requests.post(TOKEN_URL, data={
    "grant_type": "authorization_code",
    "code": auth_code_result["code"],
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT_URI,
})

if response.status_code != 200:
    print(f"Error: {response.status_code} {response.text}")
    sys.exit(1)

tokens = response.json()
refresh_token = tokens.get("refresh_token")

print()
print("=" * 60)
print("YOUR REFRESH TOKEN:")
print("=" * 60)
print(refresh_token)
print("=" * 60)
