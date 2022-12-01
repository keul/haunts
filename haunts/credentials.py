"""Credentials for Google Calendar API"""

import sys

import click
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

credentials_cache = {}


def get_credentials(config_dir, scopes, token_file):
    global credentials_cache
    creds = credentials_cache.get(token_file)
    if creds:
        return creds
    # The file at token_file stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    token = config_dir / token_file
    credentials = config_dir / "credentials.json"
    if not credentials.exists():
        click.echo(
            f"Missing credentials file at {credentials.resolve()}. "
            f"Did you created a Google Cloud project and downloaded the credentials file?"
        )
        sys.exit(1)
    if token.is_file():
        creds = Credentials.from_authorized_user_file(token.resolve(), scopes)
        credentials_cache[token_file] = creds
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials.resolve(), scopes
            )
            creds = flow.run_local_server(port=0)
            credentials_cache[token_file] = creds
        # Save the credentials for the next run
        with open(token.resolve(), "w") as token:
            token.write(creds.to_json())
    return creds
