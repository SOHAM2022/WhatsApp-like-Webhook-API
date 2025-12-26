"""
Database models and initialization for SQLite.
"""
import aiosqlite
import os
from datetime import datetime


class Database:
    """Singleton database connection manager."""
    
    _instance = None
    _db = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance
    
    async def connect(self, db_url: str):
        """Initialize database connection and create tables."""
        # Extract file path from sqlite:////data/app.db format
        db_path = db_url.replace("sqlite:///", "")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self._db = await aiosqlite.connect(db_path)
        self._db.row_factory = aiosqlite.Row
        
        # Create messages table with schema as specified
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                from_msisdn TEXT NOT NULL,
                to_msisdn TEXT NOT NULL,
                ts TEXT NOT NULL,
                text TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        # Create index for better query performance
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_ts 
            ON messages(ts, message_id)
        """)
        
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_from 
            ON messages(from_msisdn)
        """)
        
        await self._db.commit()
    
    async def close(self):
        """Close database connection."""
        if self._db:
            await self._db.close()
    
    async def is_healthy(self) -> bool:
        """Check if database is reachable."""
        if not self._db:
            return False
        try:
            await self._db.execute("SELECT 1")
            return True
        except Exception:
            return False
    
    @property
    def connection(self):
        """Get database connection."""
        return self._db


# Global database instance
db = Database()
