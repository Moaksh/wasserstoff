# database/email_db.py

import os
from .schema import EmailDatabase
from .email_storage import EmailStorage
from .vector_store import VectorStore
from .embeddings import EmailEmbeddings

class EmailDB:
    def __init__(self, db_path='emails.db', vector_dir='vector_index'):
        """
        Initialize the unified email database system.
        
        Args:
            db_path: Path to the SQLite database file
            vector_dir: Directory to store the vector index
        """
        # Ensure paths are absolute
        if not os.path.isabs(db_path):
            db_path = os.path.abspath(db_path)
        if not os.path.isabs(vector_dir):
            vector_dir = os.path.abspath(vector_dir)
        
        # Initialize components
        self.email_storage = EmailStorage(db_path)
        self.vector_store = VectorStore(vector_dir)
        self.embeddings = EmailEmbeddings()
    
    def store_email(self, email_data):
        """
        Store an email in both the structured database and vector store.
        
        Args:
            email_data: Email data from Gmail API
            
        Returns:
            Database ID of the stored email
        """
        try:
            # Check if email already exists in database by message_id
            message_id = email_data.get('id')
            existing_email = self.email_storage.get_email_by_message_id(message_id)
            
            if existing_email:
                print(f"Email with message_id {message_id} already exists in database, skipping storage")
                # Return the existing email's database ID
                return existing_email.get('id')
                
            # Store in structured database if it doesn't exist
            email_id = self.email_storage.store_email(email_data)
            
            # Get the stored email with all fields
            stored_email = self.email_storage.get_email_by_id(email_id)
            
            if not stored_email:
                print(f"Error: Could not retrieve email {email_id} from database after storing")
                return email_id
            
            # Check if email has content to embed
            has_content = stored_email.get('body_text') or stored_email.get('body_html')
            if not has_content:
                print(f"Warning: Email {email_id} has no content to generate embedding from")
                return email_id
            
            # Generate embedding
            embedding = self.embeddings.get_email_embedding(stored_email)
            
            if embedding is None:
                print(f"Warning: Failed to generate embedding for email {email_id}")
                return email_id
            
            # Store in vector database
            vector_result = self.vector_store.add_email(
                email_id, 
                embedding, 
                {
                    'subject': stored_email.get('subject', ''),
                    'sender': stored_email.get('sender_email', ''),
                    'timestamp': stored_email.get('timestamp', '').isoformat() if hasattr(stored_email.get('timestamp', ''), 'isoformat') else stored_email.get('timestamp', '')
                }
            )
            
            # Even if vector storage fails, we still return the email_id since the email is stored in the structured database
            if vector_result is None:
                print(f"Warning: Email {email_id} stored in database but not in vector store")
            else:
                print(f"Success: Email {email_id} stored in both database and vector store")
            
            return email_id
        except Exception as e:
            print(f"Error storing email in unified database: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def get_email(self, email_id):
        """
        Retrieve an email by its database ID.
        
        Args:
            email_id: Database ID of the email
            
        Returns:
            Email data dictionary
        """
        return self.email_storage.get_email_by_id(email_id)
        
    def get_email_by_message_id(self, message_id):
        """
        Retrieve an email by its Gmail message ID.
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            Email data dictionary or None if not found
        """
        return self.email_storage.get_email_by_message_id(message_id)
    
    def get_thread(self, thread_id):
        """
        Retrieve all emails in a thread.
        
        Args:
            thread_id: Gmail thread ID
            
        Returns:
            List of email data dictionaries
        """
        return self.email_storage.get_thread_emails(thread_id)
    
    def search(self, query, limit=10):
        """
        Search emails using both keyword and semantic search.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            List of email data dictionaries
        """
        # Get embedding for query
        query_embedding = self.embeddings.get_query_embedding(query)
        
        # Semantic search using vector store
        semantic_results = self.vector_store.search(query_embedding, k=limit*2)
        
        # Keyword search using structured database
        keyword_results = self.email_storage.search_emails(query, limit=limit*2)
        
        # Combine results (giving preference to semantic search)
        email_ids = []
        seen_ids = set()
        
        # Add semantic search results first
        for email_id, _ in semantic_results:
            if email_id not in seen_ids:
                email_ids.append(email_id)
                seen_ids.add(email_id)
        
        # Add keyword search results
        for email in keyword_results:
            if email['id'] not in seen_ids:
                email_ids.append(email['id'])
                seen_ids.add(email['id'])
        
        # Limit results
        email_ids = email_ids[:limit]
        
        # Get full email data
        return [self.email_storage.get_email_by_id(eid) for eid in email_ids]
    
    def get_emails_by_label(self, label, limit=50, offset=0):
        """
        Get emails with a specific label.
        
        Args:
            label: Label name
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            List of email data dictionaries
        """
        return self.email_storage.get_emails_by_label(label, limit, offset)
    
    def get_context_for_thread(self, thread_id, max_emails=5):
        """
        Get context information for a thread to provide to an LLM.
        
        Args:
            thread_id: Gmail thread ID
            max_emails: Maximum number of emails to include in context
            
        Returns:
            Formatted context string for LLM
        """
        # Get thread emails
        emails = self.email_storage.get_thread_emails(thread_id)
        
        # Limit to most recent emails if there are too many
        if len(emails) > max_emails:
            emails = emails[-max_emails:]
        
        # Format context
        context_parts = ["Email Thread Context:"]
        
        for i, email in enumerate(emails):
            # Format sender
            sender = f"{email.get('sender_name', '')} <{email.get('sender_email', '')}>" if email.get('sender_name') else email.get('sender_email', '')
            
            # Format recipients
            recipients = []
            if 'recipients' in email and 'to' in email['recipients']:
                for r in email['recipients']['to']:
                    recipients.append(f"{r.get('name', '')} <{r.get('email', '')}>" if r.get('name') else r.get('email', ''))
            
            recipients_str = ", ".join(recipients) if recipients else "N/A"
            
            # Add email metadata
            context_parts.append(f"Email {i+1}:")
            context_parts.append(f"From: {sender}")
            context_parts.append(f"To: {recipients_str}")
            context_parts.append(f"Subject: {email.get('subject', 'No Subject')}")
            context_parts.append(f"Date: {email.get('timestamp', '')}")
            
            # Add email body (prefer text over HTML)
            body = email.get('body_text', '') or email.get('body_html', '')
            if body:
                # Truncate body if too long
                max_body_chars = 1000
                if len(body) > max_body_chars:
                    body = body[:max_body_chars] + "..."
                context_parts.append(f"Body:\n{body}")
            
            context_parts.append("---")
        
        return "\n\n".join(context_parts)
    
    def close(self):
        """
        Close all database connections.
        """
        self.email_storage.close()