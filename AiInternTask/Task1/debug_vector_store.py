# debug_vector_store.py

import os
import sys
import numpy as np
from database.embeddings import EmailEmbeddings
from database.vector_store import VectorStore

# Test with explicit dimensions
emb = EmailEmbeddings()
vs = VectorStore()

# Generate a test embedding
test_embedding = emb.get_embedding('This is a test email')
print(f'Embedding type: {type(test_embedding)}')
print(f'Embedding shape: {test_embedding.shape}')
print(f'Vector store dimension: {vs.dimension}')

# Test adding to vector store
try:
    # Ensure embedding is the right shape
    if test_embedding.ndim == 1:
        print('Reshaping 1D embedding to 2D')
        test_embedding_reshaped = test_embedding.reshape(1, -1)
    else:
        test_embedding_reshaped = test_embedding
    
    print(f'Reshaped embedding: {test_embedding_reshaped.shape}')
    
    # Try adding to vector store
    vs.add_email(1, test_embedding_reshaped, {'subject': 'Test'})
    print('Successfully added to vector store')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()