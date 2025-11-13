"""Database connection and cursor helpers for streaming large result sets."""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Iterator, Dict, Any, Optional
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Connection pool (simple single connection for now)
_connection: Optional[psycopg2.extensions.connection] = None


def get_conn():
    """Get or create a database connection."""
    global _connection
    
    if _connection is None or _connection.closed:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable not set")
        
        _connection = psycopg2.connect(database_url)
        _connection.autocommit = False
    
    return _connection


def close_conn():
    """Close the database connection."""
    global _connection
    if _connection and not _connection.closed:
        _connection.close()
        _connection = None


@contextmanager
def transaction():
    """Context manager for database transactions."""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Transaction rolled back: {e}")
        raise


def stream_rows(query: str, params: tuple = None, name: str = "stream_cursor", 
                fetch_size: int = 500) -> Iterator[Dict[str, Any]]:
    """
    Stream rows from a query using a server-side named cursor.
    
    This uses a PostgreSQL named cursor to fetch rows in batches,
    avoiding loading entire result sets into memory.
    
    Args:
        query: SQL query string (use %s placeholders for parameters)
        params: Tuple of parameters for the query
        name: Name for the server-side cursor
        fetch_size: Number of rows to fetch per batch
    
    Yields:
        Dictionary rows (using RealDictCursor)
    """
    conn = get_conn()
    
    # Create a named server-side cursor
    # This keeps the result set on the server and fetches in batches
    cursor = conn.cursor(name=name, cursor_factory=RealDictCursor)
    
    try:
        cursor.execute(query, params or ())
        
        while True:
            rows = cursor.fetchmany(fetch_size)
            if not rows:
                break
            
            for row in rows:
                yield dict(row)
    
    finally:
        cursor.close()


def execute_query(query: str, params: tuple = None) -> list:
    """Execute a query and return all results (for small result sets)."""
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(query, params or ())
        return [dict(row) for row in cursor.fetchall()]


def execute_update(query: str, params: tuple = None) -> int:
    """Execute an update/insert/delete and return row count."""
    conn = get_conn()
    with conn.cursor() as cursor:
        cursor.execute(query, params or ())
        return cursor.rowcount


