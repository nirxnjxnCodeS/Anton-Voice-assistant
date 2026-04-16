"""
Google OAuth2 — shared authentication module for Calendar and Gmail.

First run: opens a browser window for consent, saves token.json.
Subsequent runs: loads token.json silently, refreshes if expired.

Place credentials.json (downloaded from Google Cloud Console) in the project root.
"""

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Both Calendar (read/write) and Gmail (read, compose, send)
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
]

# Paths relative to project root (one directory above this file)
_PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = _PROJECT_ROOT / os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
TOKEN_PATH = _PROJECT_ROOT / "token.json"


def get_credentials() -> Credentials:
    """
    Return valid Google OAuth2 credentials.
    Loads from token.json if present; runs the browser consent flow otherwise.
    Automatically refreshes expired tokens.
    """
    creds: Credentials | None = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"credentials.json not found at {CREDENTIALS_PATH}. "
                    "Download it from Google Cloud Console and place it in the project root. "
                    "See the setup guide in start.md for instructions."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_PATH.write_text(creds.to_json())

    return creds
