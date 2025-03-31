import os
from flask import Flask, render_template, redirect, url_for, session, request
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Allow OAuth to work over HTTP for development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY') # Load secret key for session management

# --- Routes ---

@app.route('/')
def index():
    """Homepage: Check if user is logged in."""
    if 'credentials' in session:
        # User is logged in (or at least has credentials in session)
        return redirect(url_for('dashboard'))
    # User not logged in, show login prompt
    # return render_template('login.html') # Option 1: Show a dedicated login page
    return render_template('index.html') # Option 2: Show homepage with login button

# Inside app.py

@app.route('/login')
def login():
    """Initiates the OAuth 2.0 authorization flow."""
    print("--- Reached /login route ---") # DEBUG
    try:
        from src.auth.web_auth import get_google_auth_url
        print("Attempting to get Google auth URL...") # DEBUG
        auth_url, state = get_google_auth_url()

        if not auth_url:
             print("ERROR: get_google_auth_url returned None or empty URL!") # DEBUG
             return "Error: Could not generate authentication URL.", 500

        print(f"Auth URL generated: {auth_url}") # DEBUG
        print(f"State generated: {state}") # DEBUG
        session['oauth_state'] = state
        print("State stored in session. Redirecting...") # DEBUG
        return redirect(auth_url)
    except Exception as e:
        print(f"!!! EXCEPTION in /login route: {e}") # DEBUG
        import traceback
        traceback.print_exc() # Print detailed error stack
        return f"An internal error occurred: {e}", 500
@app.route('/oauth2callback')
def oauth2callback():
    """Handles the callback from Google after user authorization."""
    from src.auth.web_auth import exchange_code_for_credentials

    # Check for state mismatch to prevent CSRF
    state = session.pop('oauth_state', None)
    if state is None or state != request.args.get('state'):
        return 'Invalid state parameter.', 400

    # Exchange authorization code for credentials
    credentials = exchange_code_for_credentials(request.url) # Pass the full callback URL
    if credentials:
        # Store credentials securely in the session (simplest way for now)
        # Note: Storing serialized credentials directly in session has size limits
        # and potential security implications. DB storage is better for production.
        session['credentials'] = credentials # Storing the serialized dictionary
        print("Stored credentials in session.")
        return redirect(url_for('dashboard'))
    else:
        return 'Failed to obtain credentials from Google.', 400

@app.route('/dashboard')
def dashboard():
    """Displays the user's emails if logged in."""
    if 'credentials' not in session:
        print("No credentials in session, redirecting to index.")
        return redirect(url_for('index'))

    # Credentials should be in session, reconstruct them
    from src.auth.web_auth import credentials_from_session
    from src.email_client.gmail_client import get_gmail_service, list_messages, get_message_detail

    creds = credentials_from_session(session['credentials'])
    if not creds:
        # If credentials failed to reconstruct (e.g., invalid format)
        session.pop('credentials', None) # Clear invalid credentials
        return redirect(url_for('login')) # Force re-login

    service = get_gmail_service(creds) # Pass credentials to service builder
    if not service:
        return "Could not connect to Gmail service.", 500

    print("Fetching emails for dashboard...")
    messages_refs = list_messages(service, max_results=10)
    emails_data = []
    if messages_refs:
        for msg_ref in messages_refs:
            msg_id = msg_ref['id']
            msg_detail = get_message_detail(service, msg_id, format='metadata', metadata_headers=['subject', 'from', 'date'])
            if msg_detail:
                headers = msg_detail.get('payload', {}).get('headers', [])
                email_info = {
                    'id': msg_id,
                    'snippet': msg_detail.get('snippet', ''),
                    'subject': next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'N/A'),
                    'from': next((h['value'] for h in headers if h['name'].lower() == 'from'), 'N/A'),
                    'date': next((h['value'] for h in headers if h['name'].lower() == 'date'), 'N/A')
                }
                emails_data.append(email_info)
            else:
                 print(f"Could not fetch metadata for {msg_id}")

    return render_template('dashboard.html', emails=emails_data)

@app.route('/logout')
def logout():
    """Logs the user out by clearing the session."""
    session.pop('credentials', None)
    session.pop('oauth_state', None)
    print("User logged out, session cleared.")
    return redirect(url_for('index'))

# --- Helper ---
# Modify get_gmail_service to accept credentials
# We'll adjust src/email_client/gmail_client.py in the next step

if __name__ == '__main__':
    # Important: Run with SSL for OAuth callbacks during development if not using localhost/127.0.0.1
    # For production, use a proper WSGI server like Gunicorn or uWSGI behind Nginx/Apache
    # Using port 5000, ensure it matches Google Cloud Redirect URI
    app.run(debug=True, port=5000) # debug=True reloads on code changes