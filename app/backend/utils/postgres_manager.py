import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool
from datetime import datetime
import streamlit as st
from backend.config import Config
from backend.utils.redis_manager import RedisManager

class PostgresManager:
    _pool = None  # Connection pool
    
    @classmethod
    def initialize_pool(cls, minconn=5, maxconn=20):
        """Initialize the PostgreSQL connection pool."""
        if cls._pool is None:
            cls._pool = SimpleConnectionPool(
                minconn, maxconn,
                host=Config.POSTGRES_HOST,
                port=Config.POSTGRES_PORT,
                database=Config.POSTGRES_DB,
                user=Config.POSTGRES_USER,
                password=Config.POSTGRES_PASSWORD
            )

    @classmethod
    def close_pool(cls):
        """Close all connections in the pool."""
        if cls._pool:
            cls._pool.closeall()
            cls._pool = None

    @classmethod
    def get_connection(cls):
        """Get a database connection from the pool."""
        if cls._pool is None:
            cls.initialize_pool()
        return cls._pool.getconn()

    @classmethod
    def release_connection(cls, conn):
        """Release a database connection back to the pool."""
        if cls._pool:
            cls._pool.putconn(conn)

    @classmethod
    def create_chat_session(cls, user_id, model_name, title=None):
        """Create a new chat session."""
        conn = cls.get_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor() as cur:
                title = title or f"Chat {datetime.now().strftime('%d %b %Y, %H:%M')}"
                cur.execute("""
                    INSERT INTO chat_sessions (user_id, title, model_name) 
                    VALUES (%s, %s, %s)
                    RETURNING session_id
                """, (user_id, title, model_name))
                session_id = cur.fetchone()[0]
                conn.commit()
                return session_id
        except Exception as e:
            st.error(f"Error creating chat session: {e}")
            return None
        finally:
            cls.release_connection(conn)

    @classmethod
    def add_message(cls, session_id, role, content):
        """Add a message to a chat session."""
        conn = cls.get_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO messages (session_id, role, content) 
                    VALUES (%s, %s, %s)
                    RETURNING message_id
                """, (session_id, role, content))
                
                message_id = cur.fetchone()[0]
                cur.execute("""
                    UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = %s
                """, (session_id,))
                
                conn.commit()
                RedisManager.update_recent_context(session_id, role, content)
                return message_id
        except Exception as e:
            st.error(f"Error adding message: {e}")
            return None
        finally:
            cls.release_connection(conn)

    @classmethod
    def get_user_chat_sessions(cls, user_id, limit=20):
        """Retrieve chat sessions for a user."""
        conn = cls.get_connection()
        if not conn:
            return []
        
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT session_id, title, model_name, created_at, updated_at
                    FROM chat_sessions WHERE user_id = %s
                    ORDER BY updated_at DESC LIMIT %s
                """, (user_id, limit))
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            st.error(f"Error retrieving chat sessions: {e}")
            return []
        finally:
            cls.release_connection(conn)

    @classmethod
    def get_session_messages(cls, session_id):
        """Retrieve messages for a session."""
        conn = cls.get_connection()
        if not conn:
            return []
        
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT message_id, role, content, created_at
                    FROM messages WHERE session_id = %s
                    ORDER BY created_at ASC
                """, (session_id,))
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            st.error(f"Error retrieving session messages: {e}")
            return []
        finally:
            cls.release_connection(conn)

    @classmethod
    def get_session_preview(cls, session_id):
        """Get a preview of the session with the first and last messages."""
        conn = cls.get_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT title, model_name, created_at, updated_at
                    FROM chat_sessions WHERE session_id = %s
                """, (session_id,))
                session_info = cur.fetchone()

                cur.execute("""
                    SELECT content FROM messages WHERE session_id = %s AND role = 'user'
                    ORDER BY created_at ASC LIMIT 1
                """, (session_id,))
                first_message = cur.fetchone()

                cur.execute("""
                    SELECT role, content FROM messages WHERE session_id = %s
                    ORDER BY created_at DESC LIMIT 2
                """, (session_id,))
                recent_messages = [dict(row) for row in cur.fetchall()]

                return {
                    'session_id': session_id,
                    'info': dict(session_info) if session_info else None,
                    'first_message': first_message['content'] if first_message else None,
                    'recent_messages': recent_messages
                }
        except Exception as e:
            st.error(f"Error retrieving session preview: {e}")
            return None
        finally:
            cls.release_connection(conn)

    @classmethod
    def update_session_title(cls, session_id, title):
        """Update the session title."""
        conn = cls.get_connection()
        if not conn:
            return False
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE chat_sessions SET title = %s WHERE session_id = %s
                """, (title, session_id))
                conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            st.error(f"Error updating session title: {e}")
            return False
        finally:
            cls.release_connection(conn)
