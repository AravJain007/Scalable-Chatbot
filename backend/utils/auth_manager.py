# backend/utils/auth_manager.py
import hashlib
import uuid
import re
import psycopg2
from psycopg2 import sql
import streamlit as st
from typing import Optional, Dict
from backend.config import Config

class AuthManager:
    @classmethod
    def get_connection(cls):
        """
        Establish a connection to PostgreSQL database
        """
        try:
            conn = psycopg2.connect(
                host=Config.POSTGRES_HOST,
                database=Config.POSTGRES_DB,
                user=Config.POSTGRES_USER,
                password=Config.POSTGRES_PASSWORD
            )
            return conn
        except Exception as e:
            st.error(f"PostgreSQL Connection Error: {e}")
            return None

    @classmethod
    def hash_password(cls, password: str) -> str:
        """
        Hash password using SHA-256
        
        :param password: Plain text password
        :return: Hashed password
        """
        return hashlib.sha256(password.encode()).hexdigest()

    @classmethod
    def validate_email(cls, email: str) -> bool:
        """
        Validate email format
        
        :param email: Email address to validate
        :return: Boolean indicating valid email
        """
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_regex, email) is not None

    @classmethod
    def create_user(cls, username: str, email: str, password: str) -> Optional[uuid.UUID]:
        """
        Create a new user in the database
        
        :param username: Desired username
        :param email: User's email address
        :param password: User's password
        :return: User ID or None if creation fails
        """
        # Validate inputs
        if not cls.validate_email(email):
            st.error("Invalid email format")
            return None

        conn = cls.get_connection()
        if not conn:
            return None

        try:
            cur = conn.cursor()
            
            # Check if email or username already exists
            cur.execute("""
                SELECT 1 FROM users 
                WHERE email = %s OR username = %s
            """, (email, username))
            
            if cur.fetchone():
                st.error("Email or username already exists")
                return None

            # Hash password
            hashed_password = cls.hash_password(password)

            # Create user
            cur.execute("""
                INSERT INTO users (username, email, password_hash) 
                VALUES (%s, %s, %s) 
                RETURNING user_id
            """, (username, email, hashed_password))

            user_id = cur.fetchone()[0]
            conn.commit()
            
            st.success("User account created successfully!")
            return user_id

        except Exception as e:
            st.error(f"Error creating user: {e}")
            return None
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    @classmethod
    def authenticate_user(cls, email: str, password: str) -> Optional[Dict]:
        """
        Authenticate user credentials
        
        :param email: User's email
        :param password: User's password
        :return: User information or None if authentication fails
        """
        conn = cls.get_connection()
        if not conn:
            return None

        try:
            cur = conn.cursor()
            
            # Retrieve user by email
            cur.execute("""
                SELECT user_id, username, email, password_hash 
                FROM users 
                WHERE email = %s
            """, (email,))
            
            user = cur.fetchone()
            
            if not user:
                st.error("User not found")
                return None

            # Verify password
            hashed_input = cls.hash_password(password)
            if hashed_input != user[3]:
                st.error("Incorrect password")
                return None

            # Update last login
            cur.execute("""
                UPDATE users 
                SET last_login = CURRENT_TIMESTAMP 
                WHERE user_id = %s
            """, (user[0],))
            conn.commit()

            # Return user information
            return {
                'user_id': user[0],
                'username': user[1],
                'email': user[2]
            }

        except Exception as e:
            st.error(f"Authentication error: {e}")
            return None
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    @classmethod
    def update_user_password(cls, user_id: uuid.UUID, old_password: str, new_password: str) -> bool:
        """
        Update user password
        
        :param user_id: User's ID
        :param old_password: Current password
        :param new_password: New password
        :return: Boolean indicating successful password update
        """
        conn = cls.get_connection()
        if not conn:
            return False

        try:
            cur = conn.cursor()
            
            # Verify current password
            cur.execute("""
                SELECT password_hash 
                FROM users 
                WHERE user_id = %s
            """, (user_id,))
            
            stored_hash = cur.fetchone()[0]
            
            # Check old password
            if stored_hash != cls.hash_password(old_password):
                st.error("Current password is incorrect")
                return False

            # Update password
            new_hash = cls.hash_password(new_password)
            cur.execute("""
                UPDATE users 
                SET password_hash = %s 
                WHERE user_id = %s
            """, (new_hash, user_id))
            
            conn.commit()
            st.success("Password updated successfully!")
            return True

        except Exception as e:
            st.error(f"Password update error: {e}")
            return False
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    @classmethod
    def reset_password(cls, email: str, new_password: str) -> bool:
        """
        Reset password (typically after verification)
        
        :param email: User's email
        :param new_password: New password
        :return: Boolean indicating successful password reset
        """
        conn = cls.get_connection()
        if not conn:
            return False

        try:
            cur = conn.cursor()
            
            # Update password
            new_hash = cls.hash_password(new_password)
            cur.execute("""
                UPDATE users 
                SET password_hash = %s 
                WHERE email = %s
            """, (new_hash, email))
            
            # Check if update was successful
            if cur.rowcount == 0:
                st.error("No user found with this email")
                return False
            
            conn.commit()
            st.success("Password reset successfully!")
            return True

        except Exception as e:
            st.error(f"Password reset error: {e}")
            return False
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()