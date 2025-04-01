# test_embeddings.py

import os
import sys
from database.embeddings import EmailEmbeddings
from database.vector_store import VectorStore

# Test the embedding dimensions
emb = EmailEmbeddings()
vs = VectorStore()

# Generate a test embedding
test_embedding = emb.get_embedding("This is a test email to check embedding dimensions")

print(f"Embedding model: {emb.model_name}")
print(f"Embedding dimension: {test_embedding.shape}")
print(f"Vector store dimension: {vs.dimension}")

# Verify dimensions match
if test_embedding.shape[0] == vs.dimension:
    print("SUCCESS: Embedding dimension matches vector store dimension")
else:
    print(f"ERROR: Dimensions don't match! Embedding: {test_embedding.shape[0]}, Vector store: {vs.dimension}")