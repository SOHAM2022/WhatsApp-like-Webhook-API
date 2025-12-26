"""
Database storage operations for messages.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.models import db


async def insert_message(
    message_id: str,
    from_msisdn: str,
    to_msisdn: str,
    ts: str,
    text: Optional[str] = None
) -> bool:
    """
    Insert a new message into the database.
    
    Returns:
        True if inserted, False if duplicate (idempotent behavior)
    """
    created_at = datetime.utcnow().isoformat() + "Z"
    
    try:
        await db.connection.execute(
            """
            INSERT INTO messages (message_id, from_msisdn, to_msisdn, ts, text, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (message_id, from_msisdn, to_msisdn, ts, text, created_at)
        )
        await db.connection.commit()
        return True
    except Exception as e:
        # If it's a unique constraint violation, message already exists (idempotent)
        if "UNIQUE constraint failed" in str(e):
            return False
        raise


async def get_messages(
    limit: int = 50,
    offset: int = 0,
    from_filter: Optional[str] = None,
    since: Optional[str] = None,
    q: Optional[str] = None
) -> tuple[List[Dict[str, Any]], int]:
    """
    Get paginated and filtered messages.
    
    Returns:
        Tuple of (messages list, total count)
    """
    # Build query with filters
    where_clauses = []
    params = []
    
    if from_filter:
        where_clauses.append("from_msisdn = ?")
        params.append(from_filter)
    
    if since:
        where_clauses.append("ts >= ?")
        params.append(since)
    
    if q:
        where_clauses.append("text LIKE ?")
        params.append(f"%{q}%")
    
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    # Get total count
    count_query = f"SELECT COUNT(*) as total FROM messages WHERE {where_sql}"
    cursor = await db.connection.execute(count_query, params)
    row = await cursor.fetchone()
    total = row["total"] if row else 0
    
    # Get paginated data - ORDER BY ts ASC, message_id ASC
    data_query = f"""
        SELECT message_id, from_msisdn as "from", to_msisdn as "to", ts, text
        FROM messages
        WHERE {where_sql}
        ORDER BY ts ASC, message_id ASC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    
    cursor = await db.connection.execute(data_query, params)
    rows = await cursor.fetchall()
    
    messages = [dict(row) for row in rows]
    
    return messages, total


async def get_stats() -> Dict[str, Any]:
    """
    Get message statistics.
    
    Returns:
        Dictionary with analytics data
    """
    # Total messages
    cursor = await db.connection.execute("SELECT COUNT(*) as total FROM messages")
    row = await cursor.fetchone()
    total_messages = row["total"] if row else 0
    
    # Senders count
    cursor = await db.connection.execute(
        "SELECT COUNT(DISTINCT from_msisdn) as count FROM messages"
    )
    row = await cursor.fetchone()
    senders_count = row["count"] if row else 0
    
    # Top 10 senders by message count
    cursor = await db.connection.execute("""
        SELECT from_msisdn as "from", COUNT(*) as count
        FROM messages
        GROUP BY from_msisdn
        ORDER BY count DESC
        LIMIT 10
    """)
    rows = await cursor.fetchall()
    messages_per_sender = [dict(row) for row in rows]
    
    # First and last message timestamps
    cursor = await db.connection.execute("""
        SELECT MIN(ts) as first_ts, MAX(ts) as last_ts
        FROM messages
    """)
    row = await cursor.fetchone()
    first_message_ts = row["first_ts"] if row and row["first_ts"] else None
    last_message_ts = row["last_ts"] if row and row["last_ts"] else None
    
    return {
        "total_messages": total_messages,
        "senders_count": senders_count,
        "messages_per_sender": messages_per_sender,
        "first_message_ts": first_message_ts,
        "last_message_ts": last_message_ts
    }
