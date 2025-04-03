# database/email_storage.py

import base64
import email
import re
from datetime import datetime
from .schema import EmailDatabase

class EmailStorage:
    def __init__(self, db_path='emails.db'):
        """
        Initialize the email storage system with the specified database path.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db = EmailDatabase(db_path)
    
    def store_email(self, email_data):
        """
        Parse and store an email from Gmail API response into the database.
        
        Args:
            email_data: The email data from Gmail API
            
        Returns:
            The ID of the stored email in the database
        """
        try:
            # Extract email fields
            message_id = email_data.get('id')
            thread_id = email_data.get('threadId')
            snippet = email_data.get('snippet', '')
            
            # Check if email already exists in database
            self.db.cursor.execute('SELECT id FROM emails WHERE message_id = ?', (message_id,))
            existing_email = self.db.cursor.fetchone()
            if existing_email:
                print(f"Email with message_id {message_id} already exists in database with id {existing_email['id']}")
                return existing_email['id']
            
            # Get headers
            headers = email_data.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
            recipients = next((h['value'] for h in headers if h['name'].lower() == 'to'), '')
            cc = next((h['value'] for h in headers if h['name'].lower() == 'cc'), '')
            date_str = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')
            in_reply_to = next((h['value'] for h in headers if h['name'].lower() == 'in-reply-to'), None)
            message_id_header = next((h['value'] for h in headers if h['name'].lower() == 'message-id'), '')
            
            # Parse timestamp
            timestamp = self._parse_date(date_str)
            
            # Extract body content
            body_text, body_html = self._extract_body(email_data.get('payload', {}))
            
            # Extract labels/flags
            labels = email_data.get('labelIds', [])
            is_read = 'UNREAD' not in labels
            is_archived = 'INBOX' not in labels
            is_deleted = 'TRASH' in labels
            
            # Extract attachments
            attachments = self._extract_attachments(email_data.get('payload', {}))
            
            # Store in database
            with self.db.conn:
                # Store or get thread
                thread_db_id = self._store_thread(thread_id, subject, snippet)
                
                # Store or get sender
                sender_name, sender_email = self._parse_email_address(sender)
                sender_id = self._store_user(sender_email, sender_name)
                
                # Store email
                self.db.cursor.execute('''
                INSERT INTO emails 
                (message_id, thread_id, sender_id, subject, body_text, body_html, 
                snippet, timestamp, in_reply_to, is_read, is_archived, is_deleted, raw_data) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (message_id, thread_db_id, sender_id, subject, body_text, body_html, 
                      snippet, timestamp, in_reply_to, is_read, is_archived, is_deleted, 
                      str(email_data)))
                
                # Get the email ID
                self.db.cursor.execute('SELECT id FROM emails WHERE message_id = ?', (message_id,))
                email_id = self.db.cursor.fetchone()['id']
                
                # Store recipients
                self._store_recipients(email_id, recipients, 'to')
                if cc:
                    self._store_recipients(email_id, cc, 'cc')
                
                # Store attachments
                for attachment in attachments:
                    self._store_attachment(email_id, attachment)
                
                # Store labels
                for label in labels:
                    self._store_label(email_id, label)
                
                return email_id
                
        except Exception as e:
            print(f"Error storing email: {e}")
            self.db.conn.rollback()
            raise
    
    def _parse_date(self, date_str):
        """
        Parse email date string into a datetime object.
        
        Args:
            date_str: Date string from email header
            
        Returns:
            Datetime object or None if parsing fails
        """
        try:
            # Try different date formats
            for fmt in ['%a, %d %b %Y %H:%M:%S %z', '%d %b %Y %H:%M:%S %z']:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            # If all formats fail, return current time
            return datetime.now()
        except Exception:
            return datetime.now()
    
    def _extract_body(self, payload):
        """
        Extract text and HTML body from email payload.
        
        Args:
            payload: Email payload from Gmail API
            
        Returns:
            Tuple of (text_body, html_body)
        """
        text_body = ''
        html_body = ''
        
        if 'parts' in payload:
            for part in payload['parts']:
                mime_type = part.get('mimeType', '')
                
                if mime_type == 'text/plain' and 'data' in part.get('body', {}):
                    body_data = part['body']['data']
                    text_body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')
                
                elif mime_type == 'text/html' and 'data' in part.get('body', {}):
                    body_data = part['body']['data']
                    html_body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')
                
                elif 'parts' in part:
                    # Recursive extraction for multipart messages
                    sub_text, sub_html = self._extract_body(part)
                    if sub_text and not text_body:
                        text_body = sub_text
                    if sub_html and not html_body:
                        html_body = sub_html
        
        elif 'body' in payload and 'data' in payload['body']:
            body_data = payload['body']['data']
            decoded_content = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')
            
            if payload.get('mimeType') == 'text/html':
                html_body = decoded_content
            else:
                text_body = decoded_content
        
        return text_body, html_body
    
    def _extract_attachments(self, payload):
        """
        Extract attachments from email payload.
        
        Args:
            payload: Email payload from Gmail API
            
        Returns:
            List of attachment dictionaries
        """
        attachments = []
        
        if 'parts' in payload:
            for part in payload['parts']:
                if 'filename' in part and part['filename']:
                    attachments.append({
                        'filename': part['filename'],
                        'mimeType': part.get('mimeType', 'application/octet-stream'),
                        'size': part['body'].get('size', 0),
                        'attachmentId': part['body'].get('attachmentId', '')
                    })
                
                if 'parts' in part:
                    # Recursive extraction for nested parts
                    attachments.extend(self._extract_attachments(part))
        
        return attachments
    
    def _parse_email_address(self, address_str):
        """
        Parse email address string into name and email components.
        
        Args:
            address_str: Email address string (e.g., "John Doe <john@example.com>")
            
        Returns:
            Tuple of (name, email)
        """
        if not address_str:
            return ('', '')
        
        # Try to match "Name <email>" format
        match = re.match(r'([^<]*)<([^>]*)>', address_str)
        if match:
            name = match.group(1).strip()
            email_addr = match.group(2).strip()
            return (name, email_addr)
        
        # If no match, assume the string is just an email
        return ('', address_str.strip())
    
    def _store_thread(self, thread_id, subject, snippet):
        """
        Store or get thread ID from database.
        
        Args:
            thread_id: Gmail thread ID
            subject: Email subject
            snippet: Email snippet
            
        Returns:
            Database ID for the thread
        """
        self.db.cursor.execute('SELECT id FROM email_threads WHERE thread_id = ?', (thread_id,))
        result = self.db.cursor.fetchone()
        
        if result:
            # Update last_updated timestamp
            self.db.cursor.execute(
                'UPDATE email_threads SET last_updated = CURRENT_TIMESTAMP WHERE id = ?', 
                (result['id'],)
            )
            return result['id']
        
        # Insert new thread
        self.db.cursor.execute(
            'INSERT INTO email_threads (thread_id, subject, snippet) VALUES (?, ?, ?)',
            (thread_id, subject, snippet)
        )
        return self.db.cursor.lastrowid
    
    def _store_user(self, email_addr, name=None):
        """
        Store or get user ID from database.
        
        Args:
            email_addr: Email address
            name: User's name (optional)
            
        Returns:
            Database ID for the user
        """
        if not email_addr:
            return None
        
        self.db.cursor.execute('SELECT id FROM users WHERE email = ?', (email_addr,))
        result = self.db.cursor.fetchone()
        
        if result:
            return result['id']
        
        # Insert new user
        self.db.cursor.execute(
            'INSERT INTO users (email, name) VALUES (?, ?)',
            (email_addr, name)
        )
        return self.db.cursor.lastrowid
    
    def _store_recipients(self, email_id, recipients_str, recipient_type):
        """
        Store email recipients in the database.
        
        Args:
            email_id: Database ID of the email
            recipients_str: String of recipients (comma-separated)
            recipient_type: Type of recipient ('to', 'cc', 'bcc')
        """
        if not recipients_str:
            return
        
        # Split by comma and process each recipient
        for recipient in recipients_str.split(','):
            name, email_addr = self._parse_email_address(recipient.strip())
            if email_addr:
                user_id = self._store_user(email_addr, name)
                
                self.db.cursor.execute(
                    'INSERT INTO recipients (email_id, user_id, type) VALUES (?, ?, ?)',
                    (email_id, user_id, recipient_type)
                )
    
    def _store_attachment(self, email_id, attachment):
        """
        Store email attachment in the database.
        
        Args:
            email_id: Database ID of the email
            attachment: Attachment dictionary
        """
        self.db.cursor.execute(
            'INSERT INTO attachments (email_id, filename, content_type, size, attachment_id) VALUES (?, ?, ?, ?, ?)',
            (email_id, attachment['filename'], attachment['mimeType'], 
             attachment['size'], attachment['attachmentId'])
        )
    
    def _store_label(self, email_id, label_name):
        """
        Store email label in the database.
        
        Args:
            email_id: Database ID of the email
            label_name: Name of the label
        """
        # Get or create label
        self.db.cursor.execute('SELECT id FROM labels WHERE name = ?', (label_name,))
        result = self.db.cursor.fetchone()
        
        if result:
            label_id = result['id']
        else:
            self.db.cursor.execute('INSERT INTO labels (name) VALUES (?)', (label_name,))
            label_id = self.db.cursor.lastrowid
        
        # Associate label with email
        self.db.cursor.execute(
            'INSERT OR IGNORE INTO email_labels (email_id, label_id) VALUES (?, ?)',
            (email_id, label_id)
        )
    
    def get_email_by_id(self, email_id):
        """
        Retrieve an email by its database ID.
        
        Args:
            email_id: Database ID of the email
            
        Returns:
            Email data dictionary or None if not found
        """
        self.db.cursor.execute('''
        SELECT e.*, u.email as sender_email, u.name as sender_name, t.thread_id as gmail_thread_id 
        FROM emails e 
        JOIN users u ON e.sender_id = u.id 
        JOIN email_threads t ON e.thread_id = t.id 
        WHERE e.id = ?
        ''', (email_id,))
        
        email_data = self.db.cursor.fetchone()
        if not email_data:
            return None
        
        # Convert to dictionary
        result = dict(email_data)
        
        # Get recipients
        self.db.cursor.execute('''
        SELECT r.type, u.email, u.name 
        FROM recipients r 
        JOIN users u ON r.user_id = u.id 
        WHERE r.email_id = ?
        ''', (email_id,))
        
        recipients = self.db.cursor.fetchall()
        result['recipients'] = {}
        
        for r in recipients:
            r_type = r['type']
            if r_type not in result['recipients']:
                result['recipients'][r_type] = []
            
            result['recipients'][r_type].append({
                'email': r['email'],
                'name': r['name']
            })
        
        # Get attachments
        self.db.cursor.execute('SELECT * FROM attachments WHERE email_id = ?', (email_id,))
        result['attachments'] = [dict(a) for a in self.db.cursor.fetchall()]
        
        # Get labels
        self.db.cursor.execute('''
        SELECT l.name 
        FROM email_labels el 
        JOIN labels l ON el.label_id = l.id 
        WHERE el.email_id = ?
        ''', (email_id,))
        
        result['labels'] = [l['name'] for l in self.db.cursor.fetchall()]
        
        return result
        
    def get_email_by_message_id(self, message_id):
        """
        Retrieve an email by its Gmail message ID.
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            Email data dictionary or None if not found
        """
        self.db.cursor.execute('''
        SELECT id FROM emails WHERE message_id = ?
        ''', (message_id,))
        
        result = self.db.cursor.fetchone()
        if not result:
            return None
        
        # Use the existing method to get the full email data
        return self.get_email_by_id(result['id'])
    
    def get_thread_emails(self, thread_id):
        """
        Retrieve all emails in a thread.
        
        Args:
            thread_id: Gmail thread ID
            
        Returns:
            List of email data dictionaries sorted by timestamp
        """
        self.db.cursor.execute('''
        SELECT e.id 
        FROM emails e 
        JOIN email_threads t ON e.thread_id = t.id 
        WHERE t.thread_id = ? 
        ORDER BY e.timestamp
        ''', (thread_id,))
        
        email_ids = [row['id'] for row in self.db.cursor.fetchall()]
        return [self.get_email_by_id(eid) for eid in email_ids]
    
    def search_emails(self, query, limit=50, offset=0):
        """
        Search emails by query string.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
            offset: Offset for pagination
            
        Returns:
            List of email data dictionaries matching the query
        """
        search_term = f'%{query}%'
        
        self.db.cursor.execute('''
        SELECT e.id 
        FROM emails e 
        LEFT JOIN users u ON e.sender_id = u.id 
        WHERE e.subject LIKE ? OR e.body_text LIKE ? OR u.email LIKE ? OR u.name LIKE ? 
        ORDER BY e.timestamp DESC 
        LIMIT ? OFFSET ?
        ''', (search_term, search_term, search_term, search_term, limit, offset))
        
        email_ids = [row['id'] for row in self.db.cursor.fetchall()]
        return [self.get_email_by_id(eid) for eid in email_ids]
    
    def get_emails_by_label(self, label, limit=50, offset=0):
        """
        Get emails with a specific label.
        
        Args:
            label: Label name
            limit: Maximum number of results to return
            offset: Offset for pagination
            
        Returns:
            List of email data dictionaries with the specified label
        """
        self.db.cursor.execute('''
        SELECT e.id 
        FROM emails e 
        JOIN email_labels el ON e.id = el.email_id 
        JOIN labels l ON el.label_id = l.id 
        WHERE l.name = ? 
        ORDER BY e.timestamp DESC 
        LIMIT ? OFFSET ?
        ''', (label, limit, offset))
        
        email_ids = [row['id'] for row in self.db.cursor.fetchall()]
        return [self.get_email_by_id(eid) for eid in email_ids]
    
    def close(self):
        """
        Close the database connection.
        """
        self.db.close()