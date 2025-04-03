# database/vector_store.py

import os
import json
import numpy as np
import faiss
from datetime import datetime

class VectorStore:
    def __init__(self, index_dir='vector_index'):
        """
        Initialize the vector store for email embeddings.
        
        Args:
            index_dir: Directory to store the FAISS index and metadata
        """
        self.index_dir = index_dir
        os.makedirs(index_dir, exist_ok=True)
        
        self.index_path = os.path.join(index_dir, 'email_embeddings.index')
        self.metadata_path = os.path.join(index_dir, 'email_metadata.json')
        
        # Initialize or load index and metadata
        self.dimension = 384  # Default dimension for Hugging Face all-MiniLM-L6-v2 embeddings
        self.index = None
        self.metadata = {}
        self._initialize_index()
    
    def _initialize_index(self):
        """
        Initialize or load the FAISS index and metadata.
        """
        try:
            if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
                # Load existing index and metadata
                self.index = faiss.read_index(self.index_path)
                with open(self.metadata_path, 'r') as f:
                    self.metadata = json.load(f)
            else:
                # Create new index
                self.index = faiss.IndexFlatL2(self.dimension)
                self.metadata = {'emails': {}}
        except Exception as e:
            print(f"Error initializing vector store: {e}")
            # Create new index as fallback
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = {'emails': {}}
    
    def add_email(self, email_id, embedding, email_metadata=None):
        """
        Add an email embedding to the vector store.
        
        Args:
            email_id: Database ID of the email
            embedding: Embedding vector of the email content
            email_metadata: Additional metadata to store with the embedding
            
        Returns:
            Index ID if successful, None if failed with error details in logs
        """
        try:
            # Check if embedding is None or empty
            if embedding is None or (isinstance(embedding, np.ndarray) and embedding.size == 0):
                print(f"Error adding email {email_id} to vector store: Embedding is None or empty")
                return None
                
            if not isinstance(embedding, np.ndarray):
                try:
                    embedding = np.array(embedding, dtype=np.float32)
                except Exception as e:
                    print(f"Error adding email {email_id} to vector store: Could not convert embedding to numpy array: {e}")
                    return None
            
            # Ensure embedding is 2D for FAISS
            if embedding.ndim == 1:
                embedding = embedding.reshape(1, -1)
            
            # Check for NaN or Inf values
            if not np.isfinite(embedding).all():
                print(f"Error adding email {email_id} to vector store: Embedding contains NaN or Inf values")
                # Replace NaN/Inf with zeros to prevent errors
                embedding = np.nan_to_num(embedding)
            
            # Verify dimensions match and handle mismatches
            if embedding.shape[1] != self.dimension:
                print(f"Warning: Email {email_id} embedding dimension {embedding.shape[1]} does not match vector store dimension {self.dimension}")
                # Resize embedding to match expected dimension
                if embedding.shape[1] > self.dimension:
                    # Truncate to expected dimension
                    embedding = embedding[:, :self.dimension]
                else:
                    # Pad with zeros to match expected dimension
                    padding = np.zeros((embedding.shape[0], self.dimension - embedding.shape[1]), dtype=np.float32)
                    embedding = np.hstack((embedding, padding))
            
            # Normalize the embedding to unit length to improve search quality
            # This can help with numerical stability issues
            norm = np.linalg.norm(embedding, axis=1, keepdims=True)
            if norm.any():
                embedding = embedding / norm
            
            # Add to index
            index_id = self.index.ntotal
            try:
                self.index.add(embedding)
            except Exception as e:
                print(f"FAISS error adding embedding for email {email_id}: {e}")
                # Try to recover by creating a new index if the current one is corrupted
                if "index not trained" in str(e).lower():
                    print(f"Attempting to retrain index for email {email_id}")
                    self.index = faiss.IndexFlatL2(self.dimension)
                    self.index.add(embedding)
                else:
                    raise
            
            # Store metadata
            self.metadata['emails'][str(index_id)] = {
                'email_id': email_id,
                'timestamp': datetime.now().isoformat(),
                'metadata': email_metadata or {}
            }
            
            # Save index and metadata
            try:
                self._save()
            except Exception as e:
                print(f"Error saving vector store after adding email {email_id}: {e}")
                # Continue anyway since the email is in memory
                # We'll try to save again on the next operation
            
            return index_id
        except Exception as e:
            print(f"Error adding email {email_id} to vector store: {e}")
            import traceback
            traceback.print_exc()
            # Return None instead of raising to prevent cascading failures
            return None
    
    def search(self, query_embedding, k=5):
        """
        Search for similar emails using a query embedding.
        
        Args:
            query_embedding: Embedding vector of the query
            k: Number of results to return
            
        Returns:
            List of (email_id, score) tuples
        """
        try:
            if not isinstance(query_embedding, np.ndarray):
                query_embedding = np.array(query_embedding, dtype=np.float32)
            
            # Ensure query is 2D for FAISS
            if query_embedding.ndim == 1:
                query_embedding = query_embedding.reshape(1, -1)
            
            # Search index
            distances, indices = self.index.search(query_embedding, k)
            
            # Get email IDs from metadata
            results = []
            for i, idx in enumerate(indices[0]):
                if idx != -1 and str(idx) in self.metadata['emails']:
                    email_id = self.metadata['emails'][str(idx)]['email_id']
                    score = float(distances[0][i])  # Convert to Python float for JSON serialization
                    results.append((email_id, score))
            
            return results
        except Exception as e:
            print(f"Error searching vector store: {e}")
            return []
    
    def delete_email(self, email_id):
        """
        Delete an email from the vector store.
        Note: This is a soft delete that only removes from metadata.
        A full rebuild would be needed for complete removal from FAISS.
        
        Args:
            email_id: Database ID of the email to delete
        """
        try:
            # Find all indices with this email_id
            indices_to_remove = []
            for idx, data in self.metadata['emails'].items():
                if data['email_id'] == email_id:
                    indices_to_remove.append(idx)
            
            # Remove from metadata
            for idx in indices_to_remove:
                if idx in self.metadata['emails']:
                    del self.metadata['emails'][idx]
            
            # Save metadata
            self._save_metadata()
            
            return len(indices_to_remove)
        except Exception as e:
            print(f"Error deleting email from vector store: {e}")
            return 0
    
    def _save(self):
        """
        Save both the index and metadata to disk.
        """
        try:
            # Create a temporary file to avoid corruption if the process is interrupted
            temp_index_path = f"{self.index_path}.temp"
            temp_metadata_path = f"{self.metadata_path}.temp"
            
            # Save to temporary files first
            faiss.write_index(self.index, temp_index_path)
            with open(temp_metadata_path, 'w') as f:
                json.dump(self.metadata, f, indent=2)
                
            # Rename temporary files to final files (atomic operation)
            import os
            os.replace(temp_index_path, self.index_path)
            os.replace(temp_metadata_path, self.metadata_path)
            
            return True
        except Exception as e:
            print(f"Error saving vector store: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _save_index(self):
        """
        Save the FAISS index to disk.
        """
        try:
            faiss.write_index(self.index, self.index_path)
        except Exception as e:
            print(f"Error saving index: {e}")
    
    def _save_metadata(self):
        """
        Save the metadata to disk.
        """
        try:
            with open(self.metadata_path, 'w') as f:
                json.dump(self.metadata, f)
        except Exception as e:
            print(f"Error saving metadata: {e}")
    
    def rebuild_index(self):
        """
        Rebuild the index from scratch (useful after many deletions).
        This requires re-embedding all emails, so it's not implemented here.
        In a real application, you would store the original embeddings and rebuild.
        """
        pass