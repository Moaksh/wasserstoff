# llm/email_understanding.py

import os
import openai
from dotenv import load_dotenv
from database.gmail_integration import GmailDBIntegration

load_dotenv()

# Set OpenAI API key from environment variable
openai.api_key = os.getenv('OPENAI_API_KEY')

class EmailUnderstanding:
    def __init__(self, model="gpt-3.5-turbo"):
        """
        Initialize the email understanding component.
        
        Args:
            model: OpenAI model to use for understanding emails
        """
        self.model = model
        self.gmail_db = GmailDBIntegration()
    
    def summarize_email(self, email_id):
        """
        Summarize a single email.
        
        Args:
            email_id: Database ID of the email
            
        Returns:
            Summary of the email
        """
        try:
            # Get email from database
            email = self.gmail_db.get_email(email_id)
            if not email:
                return "Email not found"
            
            # Extract relevant information
            subject = email.get('subject', 'No Subject')
            sender = f"{email.get('sender_name', '')} <{email.get('sender_email', '')}>" if email.get('sender_name') else email.get('sender_email', '')
            body = email.get('body_text', '') or email.get('body_html', '')
            
            # Create prompt for OpenAI
            prompt = f"""Please summarize the following email in 2-3 sentences:

From: {sender}
Subject: {subject}
Body:
{body}

Summary:"""
            
            # Call OpenAI API
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an AI assistant that summarizes emails concisely and accurately."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            print(f"Error summarizing email: {e}")
            return "Error generating summary"
    
    def summarize_thread(self, thread_id):
        """
        Summarize an email thread.
        
        Args:
            thread_id: Gmail thread ID
            
        Returns:
            Summary of the thread
        """
        try:
            # Get thread context from database
            context = self.gmail_db.get_context_for_thread(thread_id)
            if not context:
                return "Thread not found or empty"
            
            # Create prompt for OpenAI
            prompt = f"""Please summarize the following email thread in 3-5 sentences, capturing the key points and any action items:

{context}

Thread Summary:"""
            
            # Call OpenAI API
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an AI assistant that summarizes email threads concisely and accurately."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            print(f"Error summarizing thread: {e}")
            return "Error generating thread summary"
    
    def draft_reply(self, email_id):
        """
        Draft a reply to an email.
        
        Args:
            email_id: Database ID of the email
            
        Returns:
            Draft reply text
        """
        try:
            # Get email from database
            email = self.gmail_db.get_email(email_id)
            if not email:
                return "Email not found"
            
            # Extract relevant information
            subject = email.get('subject', 'No Subject')
            sender = f"{email.get('sender_name', '')} <{email.get('sender_email', '')}>" if email.get('sender_name') else email.get('sender_email', '')
            body = email.get('body_text', '') or email.get('body_html', '')
            
            # Get thread context if available
            thread_context = ""
            if 'gmail_thread_id' in email:
                thread_emails = self.gmail_db.get_thread(email['gmail_thread_id'])
                if thread_emails and len(thread_emails) > 1:
                    # Format thread context (simplified)
                    thread_context = "\n\nPrevious messages in this thread:\n"
                    for i, thread_email in enumerate(thread_emails[:-1]):  # Exclude the current email
                        thread_context += f"\nEmail {i+1}:\nFrom: {thread_email.get('sender_email', '')}\nSubject: {thread_email.get('subject', '')}\n"
            
            # Create prompt for OpenAI
            prompt = f"""Please draft a professional and helpful reply to the following email:

From: {sender}
Subject: {subject}
Body:
{body}
{thread_context}

Draft Reply:"""
            
            # Call OpenAI API
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an AI assistant that drafts helpful, concise, and professional email replies."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.5
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            print(f"Error drafting reply: {e}")
            return "Error generating draft reply"
    
    def extract_action_items(self, email_id):
        """
        Extract action items from an email.
        
        Args:
            email_id: Database ID of the email
            
        Returns:
            List of action items
        """
        try:
            # Get email from database
            email = self.gmail_db.get_email(email_id)
            if not email:
                return "Email not found"
            
            # Extract relevant information
            subject = email.get('subject', 'No Subject')
            sender = f"{email.get('sender_name', '')} <{email.get('sender_email', '')}>" if email.get('sender_name') else email.get('sender_email', '')
            body = email.get('body_text', '') or email.get('body_html', '')
            
            # Create prompt for OpenAI
            prompt = f"""Please extract any action items, tasks, or requests from the following email. Format them as a bulleted list. If there are no action items, respond with "No action items found.":

From: {sender}
Subject: {subject}
Body:
{body}

Action Items:"""
            
            # Call OpenAI API
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an AI assistant that extracts action items from emails accurately."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            print(f"Error extracting action items: {e}")
            return "Error extracting action items"
    
    def search_semantic(self, query, limit=5):
        """
        Search emails semantically based on meaning rather than keywords.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of relevant emails
        """
        try:
            # Use the database's semantic search capability
            results = self.gmail_db.search_emails(query, limit)
            
            # Format results
            formatted_results = []
            for email in results:
                formatted_results.append({
                    'id': email.get('id'),
                    'subject': email.get('subject', 'No Subject'),
                    'sender': email.get('sender_email', ''),
                    'date': email.get('timestamp', ''),
                    'snippet': email.get('snippet', '') or email.get('body_text', '')[:100] + '...'
                })
            
            return formatted_results
        
        except Exception as e:
            print(f"Error in semantic search: {e}")
            return []
    
    def close(self):
        """
        Close database connections.
        """
        self.gmail_db.close()