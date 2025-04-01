# database/schema.py

import sqlite3
import os
import json
from datetime import datetime

class EmailDatabase:
    def __init__(self, db_path='emails.db'):
        """
        Initialize the email database with the specified path.
        
        Args:
            db_path: Path to the SQLite database file
        """
        # Make sure the database directory exists
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._connect()
        self._create_tables()
    
    def _connect(self):
        """
        Connect to the SQLite database.
        """
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            self.cursor = self.conn.cursor()
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            raise
    
    def _create_tables(self):
        """
        Create the necessary tables for email storage if they don't exist.
        """
        try:
            # Users table
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Email threads table
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_threads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT UNIQUE NOT NULL,
                subject TEXT,
                snippet TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Emails table with threading support
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE NOT NULL,
                thread_id INTEGER,
                sender_id INTEGER,
                subject TEXT,
                body_text TEXT,
                body_html TEXT,
                snippet TEXT,
                timestamp TIMESTAMP,
                in_reply_to TEXT,
                is_read BOOLEAN DEFAULT 0,
                is_archived BOOLEAN DEFAULT 0,
                is_deleted BOOLEAN DEFAULT 0,
                raw_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (thread_id) REFERENCES email_threads(id),
                FOREIGN KEY (sender_id) REFERENCES users(id)
            )
            ''')
            
            # Recipients table (for to, cc, bcc)
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS recipients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER,
                user_id INTEGER,
                type TEXT CHECK(type IN ('to', 'cc', 'bcc')),
                FOREIGN KEY (email_id) REFERENCES emails(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            ''')
            
            # Attachments table
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER,
                filename TEXT,
                content_type TEXT,
                size INTEGER,
                attachment_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (email_id) REFERENCES emails(id)
            )
            ''')
            
            # Labels/Tags table
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Email-Label relationship table
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_labels (
                email_id INTEGER,
                label_id INTEGER,
                PRIMARY KEY (email_id, label_id),
                FOREIGN KEY (email_id) REFERENCES emails(id),
                FOREIGN KEY (label_id) REFERENCES labels(id)
            )
            ''')
            
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error creating tables: {e}")
            self.conn.rollback()
            raise
    
    def close(self):
        """
        Close the database connection.
        """
        if self.conn:
            self.conn.close()
    
    def __del__(self):
        """
        Ensure the database connection is closed when the object is deleted.
        """
        self.close()