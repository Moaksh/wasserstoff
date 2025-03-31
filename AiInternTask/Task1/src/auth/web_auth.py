import os
import google.oauth2.credentials
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

# Load client secrets file path from environment variable
CLIENT_SECRETS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials/credentials.json')

# Define scopes - ensure they match what you configured in Google Cloud Console
SCOPES = [
    'https://www.googleapis.com/auth/userinfo.email', # Get user email
    'https://www.googleapis.com/auth/userinfo.profile', # Get user profile info
    'openid', # Standard OpenID scope
    'https://www.googleapis.com/auth/gmail.readonly', # Read Gmail messages
    'https://www.googleapis.com/auth/gmail.modify', # Modify Gmail messages (archive, mark as read)
    'https://www.googleapis.com/auth/gmail.labels', # Manage labels
    'https://www.googleapis.com/auth/gmail.compose' # Send emails and manage drafts
]
# The redirect URI must exactly match one configured in Google Cloud Console
# Best practice: construct it dynamically if your app host/port can change
# For local dev assuming http://127.0.0.1:5000
REDIRECT_URI = 'http://127.0.0.1:5000/oauth2callback'

def get_google_auth_url():
    """Generates the Google Authorization URL."""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise FileNotFoundError(f"Credentials file not found at {CLIENT_SECRETS_FILE}")

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    # Generate authorization URL and include state for CSRF protection
    authorization_url, state = flow.authorization_url(
        access_type='offline',  # Request refresh token
        include_granted_scopes='true', # Include previously granted scopes
        # prompt='consent' # Force consent screen every time (useful for testing scope changes)
    )
    print(f"Generated Auth URL: {authorization_url}") # Debugging
    print(f"Generated State: {state}") # Debugging
    return authorization_url, state

def exchange_code_for_credentials(authorization_response_url):
    """Exchanges the authorization code for credentials."""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise FileNotFoundError(f"Credentials file not found at {CLIENT_SECRETS_FILE}")

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    try:
        # Fetch the token using the full callback URL provided by Google
        flow.fetch_token(authorization_response=authorization_response_url)
        credentials = flow.credentials
        print("Token fetched successfully.")
        # Return credentials as a dictionary for session serialization
        return credentials_to_dict(credentials)
    except Exception as e:
        print(f"Error fetching token: {e}")
        import traceback
        traceback.print_exc()
        return None

def credentials_to_dict(credentials):
    """Converts Google credentials object to a serializable dictionary."""
    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes,
            'expiry': credentials.expiry.isoformat() if credentials.expiry else None} # Store expiry as ISO string

def credentials_from_session(creds_dict):
    """Reconstructs credentials object from a dictionary stored in session."""
    if not creds_dict or 'token' not in creds_dict:
        return None
    try:
        # Convert expiry from ISO string to datetime if it exists
        if creds_dict.get('expiry'):
            from datetime import datetime
            creds_dict['expiry'] = datetime.fromisoformat(creds_dict['expiry'])
        
        creds = google.oauth2.credentials.Credentials(
            **creds_dict
        )
        # Optional: Check if token needs refresh and attempt it
        # from google.auth.transport.requests import Request
        # if creds and creds.expired and creds.refresh_token:
        #     try:
        #         creds.refresh(Request())
        #         print("Credentials refreshed automatically.")
        #         # TODO: Update the stored credentials in session/DB after refresh
        #     except Exception as e:
        #         print(f"Failed to refresh credentials: {e}")
        #         return None # Treat as invalid if refresh fails
        return creds
    except Exception as e:
        print(f"Error reconstructing credentials: {e}")
        return None