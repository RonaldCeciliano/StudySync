import os
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlencode, urlparse, parse_qs

from dotenv import load_dotenv

load_dotenv()

BLACKBOARD_APP_KEY = os.getenv("BLACKBOARD_APP_KEY")

REDIRECT_URI = "http://localhost:8000"

AUTH_URL = (
    "https://learn.uark.edu/learn/api/public/v1/oauth2/authorizationcode"
)

params = {
    "client_id": BLACKBOARD_APP_KEY,
    "response_type": "code",
    "redirect_uri": REDIRECT_URI,
}

authorization_url = f"{AUTH_URL}?{urlencode(params)}"


class CallbackHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)

        code = query.get("code")

        if code:
            print("\nAuthorization code received!")
            print(code[0])

            self.send_response(200)
            self.end_headers()

            self.wfile.write(
                b"StudySync authorization successful! You can close this window."
            )

        else:
            print("No authorization code received.")
            print(query)

            self.send_response(400)
            self.end_headers()

            self.wfile.write(b"Authorization failed.")


print("Opening Blackboard authorization...")

webbrowser.open(authorization_url)

server = HTTPServer(("localhost", 8000), CallbackHandler)

print("Waiting for Blackboard...")

server.handle_request()