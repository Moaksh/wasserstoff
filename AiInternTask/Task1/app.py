import os
import base64
from flask import Flask, render_template, redirect, url_for, session, request, jsonify
from dotenv import load_dotenv

load_dotenv()

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')

@app.route('/')
def index():
    if 'credentials' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login')
def login():
    try:
        from src.auth.web_auth import get_google_auth_url
        auth_url, state = get_google_auth_url()

        if not auth_url:
            return "Error: Could not generate authentication URL.", 500

        session['oauth_state'] = state
        return redirect(auth_url)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"An internal error occurred: {e}", 500

@app.route('/oauth2callback')
def oauth2callback():
    from src.auth.web_auth import exchange_code_for_credentials

    state = session.pop('oauth_state', None)
    if state is None or state != request.args.get('state'):
        return 'Invalid state parameter.', 400

    credentials = exchange_code_for_credentials(request.url)
    if credentials:
        session['credentials'] = credentials
        return redirect(url_for('dashboard'))
    else:
        return 'Failed to obtain credentials from Google.', 400

@app.route('/dashboard')
def dashboard():
    if 'credentials' not in session:
        return redirect(url_for('index'))

    from src.auth.web_auth import credentials_from_session
    from src.email_client.gmail_client import get_gmail_service, list_messages, get_message_detail

    creds = credentials_from_session(session['credentials'])
    if not creds:
        session.pop('credentials', None)
        return redirect(url_for('login'))

    service = get_gmail_service(creds)
    if not service:
        return "Could not connect to Gmail service.", 500

    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    messages_refs = list_messages(service, max_results=100)
    total_messages = len(messages_refs) if messages_refs else 0
    total_pages = (total_messages + per_page - 1) // per_page

    current_page_messages = messages_refs[offset:offset+per_page] if messages_refs else []

    emails_data = []
    if current_page_messages:
        for msg_ref in current_page_messages:
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

    return render_template('dashboard.html', emails=emails_data, current_page=page, total_pages=total_pages)

@app.route('/api/emails')
def api_emails():
    if 'credentials' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    from src.auth.web_auth import credentials_from_session
    from src.email_client.gmail_client import get_gmail_service, list_messages, get_message_detail

    creds = credentials_from_session(session['credentials'])
    if not creds:
        return jsonify({'error': 'Invalid credentials'}), 401

    service = get_gmail_service(creds)
    if not service:
        return jsonify({'error': 'Could not connect to Gmail service'}), 500

    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    messages_refs = list_messages(service, max_results=100)
    total_messages = len(messages_refs) if messages_refs else 0
    total_pages = (total_messages + per_page - 1) // per_page

    current_page_messages = messages_refs[offset:offset+per_page] if messages_refs else []

    emails_data = []
    if current_page_messages:
        for msg_ref in current_page_messages:
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

    return jsonify({
        'emails': emails_data,
        'pagination': {
            'current_page': page,
            'total_pages': total_pages,
            'total_messages': total_messages,
            'per_page': per_page
        }
    })

@app.route('/api/email/<email_id>')
def api_email_detail(email_id):
    if 'credentials' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    from src.auth.web_auth import credentials_from_session
    from src.email_client.gmail_client import get_gmail_service, get_message_detail

    creds = credentials_from_session(session['credentials'])
    if not creds:
        return jsonify({'error': 'Invalid credentials'}), 401

    service = get_gmail_service(creds)
    if not service:
        return jsonify({'error': 'Could not connect to Gmail service'}), 500

    msg_detail = get_message_detail(service, email_id, format='full')
    if not msg_detail:
        return jsonify({'error': 'Email not found'}), 404

    headers = msg_detail.get('payload', {}).get('headers', [])

    body = ''
    html_body = ''

    if 'parts' in msg_detail.get('payload', {}):
        for part in msg_detail['payload']['parts']:
            if part.get('mimeType') == 'text/html' and 'data' in part.get('body', {}):
                body_data = part['body']['data']
                html_body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                break

        if not html_body:
            for part in msg_detail['payload']['parts']:
                if part.get('mimeType') == 'text/plain' and 'data' in part.get('body', {}):
                    body_data = part['body']['data']
                    body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                    break
    elif 'body' in msg_detail.get('payload', {}) and 'data' in msg_detail['payload']['body']:
        body_data = msg_detail['payload']['body']['data']
        mime_type = msg_detail.get('payload', {}).get('mimeType', 'text/plain')
        decoded_content = base64.urlsafe_b64decode(body_data).decode('utf-8')

        if mime_type == 'text/html':
            html_body = decoded_content
        else:
            body = decoded_content

    if html_body:
        body = html_body
    else:
        body = body.replace('\n', '<br>')

    attachments = []
    if 'parts' in msg_detail.get('payload', {}):
        for part in msg_detail['payload']['parts']:
            if 'filename' in part and part['filename']:
                attachments.append({
                    'id': part['body'].get('attachmentId', ''),
                    'filename': part['filename'],
                    'mimeType': part.get('mimeType', 'application/octet-stream'),
                    'size': part['body'].get('size', 0)
                })

    email_data = {
        'id': email_id,
        'subject': next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'N/A'),
        'from': next((h['value'] for h in headers if h['name'].lower() == 'from'), 'N/A'),
        'to': next((h['value'] for h in headers if h['name'].lower() == 'to'), 'N/A'),
        'date': next((h['value'] for h in headers if h['name'].lower() == 'date'), 'N/A'),
        'body': body,
        'attachments': attachments
    }

    return jsonify(email_data)

@app.route('/api/email/<email_id>/<action>', methods=['POST'])
def api_email_action(email_id, action):
    if 'credentials' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    from src.auth.web_auth import credentials_from_session
    from src.email_client.gmail_client import get_gmail_service, get_message_detail

    creds = credentials_from_session(session['credentials'])
    if not creds:
        return jsonify({'error': 'Invalid credentials'}), 401

    service = get_gmail_service(creds)
    if not service:
        return jsonify({'error': 'Could not connect to Gmail service'}), 500

    if action == 'delete':
        try:
            service.users().messages().trash(userId='me', id=email_id).execute()
            return jsonify({'success': True, 'message': 'Email moved to trash'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    elif action == 'archive':
        try:
            service.users().messages().modify(
                userId='me',
                id=email_id,
                body={'removeLabelIds': ['INBOX']}
            ).execute()
            return jsonify({'success': True, 'message': 'Email archived'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    elif action == 'reply':
        msg_detail = get_message_detail(service, email_id, format='metadata', 
                                      metadata_headers=['subject', 'from', 'to', 'message-id'])
        if not msg_detail:
            return jsonify({'error': 'Email not found'}), 404

        headers = msg_detail.get('payload', {}).get('headers', [])

        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
        if not subject.lower().startswith('re:'):
            subject = f"Re: {subject}"

        from_email = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')

        reply_data = {
            'to': from_email,
            'subject': subject,
            'in_reply_to': next((h['value'] for h in headers if h['name'].lower() == 'message-id'), '')
        }

        return jsonify({'success': True, 'replyData': reply_data})

    else:
        return jsonify({'error': 'Invalid action'}), 400

@app.route('/api/email/<email_id>/reply', methods=['POST'])
def api_send_reply(email_id):
    if 'credentials' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'error': 'No message provided'}), 400

    from src.auth.web_auth import credentials_from_session
    from src.email_client.gmail_client import get_gmail_service, get_message_detail
    import email.mime.text
    import email.mime.multipart
    import base64

    creds = credentials_from_session(session['credentials'])
    if not creds:
        return jsonify({'error': 'Invalid credentials'}), 401

    service = get_gmail_service(creds)
    if not service:
        return jsonify({'error': 'Could not connect to Gmail service'}), 500

    msg_detail = get_message_detail(service, email_id, format='metadata', 
                                  metadata_headers=['subject', 'from', 'to', 'message-id', 'references'])
    if not msg_detail:
        return jsonify({'error': 'Email not found'}), 404

    headers = msg_detail.get('payload', {}).get('headers', [])

    subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
    if not subject.lower().startswith('re:'):
        subject = f"Re: {subject}"

    from_email = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
    message_id = next((h['value'] for h in headers if h['name'].lower() == 'message-id'), '')
    references = next((h['value'] for h in headers if h['name'].lower() == 'references'), message_id)

    message = email.mime.multipart.MIMEMultipart()
    message['to'] = from_email
    message['subject'] = subject
    message['In-Reply-To'] = message_id
    message['References'] = references

    msg_text = email.mime.text.MIMEText(data['message'])
    message.attach(msg_text)

    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    try:
        sent_message = service.users().messages().send(
            userId='me',
            body={'raw': encoded_message}
        ).execute()
        return jsonify({'success': True, 'message': 'Reply sent', 'id': sent_message['id']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/logout')
def logout():
    session.pop('credentials', None)
    session.pop('oauth_state', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
