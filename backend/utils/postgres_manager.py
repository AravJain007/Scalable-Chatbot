# backend/utils/postgres_manager.py
import psycopg2
import psycopg2.extras
from datetime import datetime
import streamlit as st
from backend.config import Config

class PostgresManager:
    @classmethod
    def get_connection(cls):
        """
        Establish a connection to PostgreSQL database
        """
        try:
            conn = psycopg2.connect(
                host=Config.POSTGRES_HOST,
                port=Config.POSTGRES_PORT,
                database=Config.POSTGRES_DB,
                user=Config.POSTGRES_USER,
                password=Config.POSTGRES_PASSWORD
            )
            return conn
        except Exception as e:
            st.error(f"PostgreSQL Connection Error: {e}")
            return None

    @classmethod
    def create_chat_session(cls, user_id, model_name, title=None):
        """
        Create a new chat session
        
        :param user_id: User identifier
        :param model_name: Name of the model used for this session
        :param title: Optional title for the session (defaults to timestamp if not provided)
        :return: session_id if successful, None otherwise
        """
        conn = cls.get_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor() as cur:
                # Generate default title if none provided
                if not title:
                    title = f"Chat {datetime.now().strftime('%d %b %Y, %H:%M')}"
                
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
            conn.close()

    @classmethod
    def add_message(cls, session_id, role, content):
        """
        Add a new message to an existing chat session
        
        :param session_id: Chat session identifier
        :param role: Message role (user, assistant, system)
        :param content: Message content
        :return: message_id if successful, None otherwise
        """
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
                
                # Update session's updated_at timestamp
                cur.execute("""
                    UPDATE chat_sessions
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = %s
                """, (session_id,))
                
                conn.commit()
                return message_id
        except Exception as e:
            st.error(f"Error adding message: {e}")
            return None
        finally:
            conn.close()

    @classmethod
    def get_user_chat_sessions(cls, user_id, limit=20):
        """
        Retrieve all chat sessions for a user
        
        :param user_id: User identifier
        :param limit: Maximum number of sessions to retrieve
        :return: List of session data
        """
        conn = cls.get_connection()
        if not conn:
            return []
        
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT session_id, title, model_name, created_at, updated_at
                    FROM chat_sessions
                    WHERE user_id = %s
                    ORDER BY updated_at DESC
                    LIMIT %s
                """, (user_id, limit))
                
                sessions = [dict(row) for row in cur.fetchall()]
                return sessions
        except Exception as e:
            st.error(f"Error retrieving chat sessions: {e}")
            return []
        finally:
            conn.close()

    @classmethod
    def get_session_messages(cls, session_id):
        """
        Retrieve all messages for a chat session
        
        :param session_id: Chat session identifier
        :return: List of messages in the session
        """
        conn = cls.get_connection()
        if not conn:
            return []
        
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT message_id, role, content, created_at
                    FROM messages
                    WHERE session_id = %s
                    ORDER BY created_at ASC
                """, (session_id,))
                
                messages = [dict(row) for row in cur.fetchall()]
                return messages
        except Exception as e:
            st.error(f"Error retrieving session messages: {e}")
            return []
        finally:
            conn.close()

    @classmethod
    def get_session_preview(cls, session_id):
        """
        Get a preview of the session with first and last message
        
        :param session_id: Chat session identifier
        :return: Dict with session info and preview messages
        """
        conn = cls.get_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                # Get session info
                cur.execute("""
                    SELECT title, model_name, created_at, updated_at
                    FROM chat_sessions
                    WHERE session_id = %s
                """, (session_id,))
                
                session_info = dict(cur.fetchone())
                
                # Get first user message
                cur.execute("""
                    SELECT content
                    FROM messages
                    WHERE session_id = %s AND role = 'user'
                    ORDER BY created_at ASC
                    LIMIT 1
                """, (session_id,))
                
                first_message = cur.fetchone()
                
                # Get most recent exchange
                cur.execute("""
                    SELECT role, content
                    FROM messages
                    WHERE session_id = %s
                    ORDER BY created_at DESC
                    LIMIT 2
                """, (session_id,))
                
                recent_messages = [dict(row) for row in cur.fetchall()]
                
                return {
                    'session_id': session_id,
                    'info': session_info,
                    'first_message': first_message['content'] if first_message else None,
                    'recent_messages': recent_messages
                }
        except Exception as e:
            st.error(f"Error retrieving session preview: {e}")
            return None
        finally:
            conn.close()

    @classmethod
    def update_session_title(cls, session_id, title):
        """
        Update the title of a chat session
        
        :param session_id: Chat session identifier
        :param title: New title for the session
        :return: True if successful, False otherwise
        """
        conn = cls.get_connection()
        if not conn:
            return False
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE chat_sessions
                    SET title = %s
                    WHERE session_id = %s
                """, (title, session_id))
                
                conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            st.error(f"Error updating session title: {e}")
            return False
        finally:
            conn.close()