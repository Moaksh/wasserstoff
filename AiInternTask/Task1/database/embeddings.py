# database/embeddings.py

import os
import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

class EmailEmbeddings:
    def __init__(self, model="all-MiniLM-L6-v2"):
        """
        Initialize the email embeddings generator.
        
        Args:
            model: Hugging Face sentence-transformer model to use
        """
        self.model_name = model
        self.model = SentenceTransformer(model)
    
    def get_embedding(self, text):
        """
        Generate an embedding vector for the given text.
        
        Args:
            text: Text to generate embedding for
            
        Returns:
            Numpy array containing the embedding vector
        """
        try:
            # Truncate text if too long (model may have token limits)
            # A simple character-based truncation; in production, use a proper tokenizer
            max_chars = 8000
            if len(text) > max_chars:
                text = text[:max_chars]
            
            # Get embedding from Hugging Face model
            embedding = self.model.encode(text)
            
            # Return as numpy array
            return np.array(embedding, dtype=np.float32)
        
        except Exception as e:
            print(f"Error generating embedding: {e}")
            # Return a zero vector as fallback - use the correct dimension for the model
            # all-MiniLM-L6-v2 has 384 dimensions
            return np.zeros(384, dtype=np.float32)
    
    def get_email_embedding(self, email_data):
        """
        Generate an embedding for an email by combining relevant fields.
        
        Args:
            email_data: Dictionary containing email data
            
        Returns:
            Numpy array containing the embedding vector
        """
        # Combine relevant fields for embedding
        text_parts = []
        
        if 'subject' in email_data and email_data['subject']:
            text_parts.append(f"Subject: {email_data['subject']}")
        
        if 'sender_name' in email_data and email_data['sender_name']:
            text_parts.append(f"From: {email_data['sender_name']} <{email_data.get('sender_email', '')}>")
        
        if 'body_text' in email_data and email_data['body_text']:
            # Use plain text body if available
            text_parts.append(email_data['body_text'])
        elif 'body_html' in email_data and email_data['body_html']:
            # Fall back to HTML body if plain text not available
            # In a real application, you might want to strip HTML tags
            text_parts.append(email_data['body_html'])
        
        # Combine all parts with newlines
        combined_text = "\n\n".join(text_parts)
        
        # Generate embedding
        return self.get_embedding(combined_text)
    
    def get_query_embedding(self, query):
        """
        Generate an embedding for a search query.
        
        Args:
            query: Search query text
            
        Returns:
            Numpy array containing the embedding vector
        """
        return self.get_embedding(query)