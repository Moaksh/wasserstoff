# database/gmail_integration.py

import os
from .email_db import EmailDB

class GmailDBIntegration:
    def __init__(self, db_path=None, vector_dir=None):
        """
        Initialize the Gmail-Database integration.
        
        Args:
            db_path: Path to the SQLite database file
            vector_dir: Directory to store the vector index
        """
        # Set default paths if not provided
        if db_path is None:
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'emails.db')
        
        if vector_dir is None:
            vector_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'vector_index')
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize the email database
        self.email_db = EmailDB(db_path, vector_dir)
    
    def process_messages(self, service, messages, full_sync=False):
        """
        Process and store messages from Gmail API.
        
        Args:
            service: Gmail API service instance
            messages: List of message references from Gmail API
            full_sync: Whether to fetch full message details for all messages
            
        Returns:
            Number of messages processed and a list of message metadata
        """
        processed_count = 0
        message_metadata_list = []
        
        for msg_ref in messages:
            try:
                # Get message details
                msg_id = msg_ref['id']
                
                # Only get metadata for all messages to improve performance
                # Full message details will be fetched only when viewing the email
                msg_metadata = service.users().messages().get(
                    userId='me', 
                    id=msg_id, 
                    format='metadata', 
                    metadataHeaders=['subject', 'from', 'date', 'message-id']
                ).execute()
                
                message_metadata_list.append(msg_metadata)
                processed_count += 1
            
            except Exception as e:
                print(f"Error processing message {msg_ref.get('id', 'unknown')}: {e}")
                continue
        
        return processed_count, message_metadata_list
    
    def sync_emails(self, service, max_results=100, full_sync=False):
        """
        Sync emails from Gmail to the database.
        
        Args:
            service: Gmail API service instance
            max_results: Maximum number of emails to sync
            full_sync: Whether to perform a full sync (slower but more thorough)
            
        Returns:
            Tuple of (number of emails synced, list of message metadata)
        """
        try:
            # List messages from Gmail
            response = service.users().messages().list(userId='me', maxResults=max_results).execute()
            messages = response.get('messages', [])
            
            if not messages:
                print("No messages found.")
                return 0, []
            
            # Process messages but don't store them yet
            return self.process_messages(service, messages, full_sync)
            
        except Exception as e:
            print(f"Error syncing emails: {e}")
            return 0, []
    
    def get_email(self, email_id):
        """
        Get an email by its ID.
        
        Args:
            email_id: Database ID of the email
            
        Returns:
            Email data dictionary
        """
        return self.email_db.get_email(email_id)
        
    def get_email_by_message_id(self, message_id):
        """
        Get an email by its Gmail message ID.
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            Email data dictionary or None if not found
        """
        return self.email_db.get_email_by_message_id(message_id)
    
    def get_thread(self, thread_id):
        """
        Get all emails in a thread.
        
        Args:
            thread_id: Gmail thread ID
            
        Returns:
            List of email data dictionaries
        """
        return self.email_db.get_thread(thread_id)
    
    def search_emails(self, query, limit=10):
        """
        Search emails using both keyword and semantic search.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            List of email data dictionaries
        """
        return self.email_db.search(query, limit)
    
    def get_context_for_thread(self, thread_id, max_emails=5):
        """
        Get context information for a thread to provide to an LLM.
        
        Args:
            thread_id: Gmail thread ID
            max_emails: Maximum number of emails to include in context
            
        Returns:
            Formatted context string for LLM
        """
        return self.email_db.get_context_for_thread(thread_id, max_emails)
    
    def close(self):
        """
        Close the database connection.
        """
        self.email_db.close()