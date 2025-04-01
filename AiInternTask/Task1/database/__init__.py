# database/__init__.py

from .email_db import EmailDB
from .schema import EmailDatabase
from .email_storage import EmailStorage
from .vector_store import VectorStore
from .embeddings import EmailEmbeddings

__all__ = ['EmailDB', 'EmailDatabase', 'EmailStorage', 'VectorStore', 'EmailEmbeddings']