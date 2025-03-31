from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64
import email as em

# Remove the dependency on the old auth method
# from src.auth.gmail_auth import get_gmail_credentials # REMOVE THIS

# Modify get_gmail_service to accept credentials
def get_gmail_service(credentials):
    """
    Builds and returns an authorized Gmail API service object
    using the provided credentials.

    Args:
        credentials: Authorized google.oauth2.credentials.Credentials object.

    Returns:
        Gmail API service instance or None if an error occurs.
    """
    if not credentials or not credentials.valid:
        print("Error: Invalid or missing credentials passed to get_gmail_service.")
        # Optionally try to refresh if possible? Depends on application flow.
        # For now, just fail if invalid creds are passed.
        return None

    try:
        service = build('gmail', 'v1', credentials=credentials)
        print("Gmail service created successfully using provided credentials.")
        return service
    except HttpError as error:
        print(f'An error occurred building the service: {error}')
        return None
    except Exception as e:
        print(f'An unexpected error occurred building service: {e}')
        return None

# --- Functions list_messages, get_message_detail, parse_email_body remain the same ---
# Ensure they use the 'service' object passed to them correctly.

def list_messages(service, user_id='me', max_results=10):
    # ... (Keep implementation as before) ...
    try:
        response = service.users().messages().list(userId=user_id, maxResults=max_results).execute()
        messages = response.get('messages', [])
        # print(f"Found {len(messages)} messages.") # Less verbose logging maybe
        return messages
    except HttpError as error:
        print(f'An error occurred listing messages: {error}')
        return None
    except Exception as e:
         print(f'Unexpected error listing messages: {e}')
         return None


def get_message_detail(service, message_id, user_id='me', format='metadata', metadata_headers=None):
     # ... (Keep implementation as before) ...
    if metadata_headers is None:
        metadata_headers = ['subject', 'from', 'to', 'date'] # Default headers for metadata format

    try:
        message = service.users().messages().get(
            userId=user_id,
            id=message_id,
            format=format,
            metadataHeaders=metadata_headers if format == 'metadata' else None
        ).execute()
        return message
    except HttpError as error:
        print(f'An error occurred getting message {message_id}: {error}')
        return None
    except Exception as e:
         print(f'Unexpected error getting message {message_id}: {e}')
         return None

def parse_email_body(parts):
    # ... (Keep implementation as before) ...
    pass # Assume it's correct from previous step