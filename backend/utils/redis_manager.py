# backend/utils/redis_manager.py
import redis
import json
import streamlit as st
from backend.config import Config

class RedisManager:
    @classmethod
    def get_connection(cls):
        """
        Establish a connection to Redis
        """
        try:
            redis_client = redis.Redis(
                host=Config.REDIS_HOST, 
                port=Config.REDIS_PORT, 
                db=0
            )
            # Test the connection
            redis_client.ping()
            return redis_client
        except Exception as e:
            st.error(f"Redis Connection Error: {e}")
            return None

    @classmethod
    def cache_response(cls, key, response, expiration=3600):
        """
        Cache a response in Redis
        
        :param key: Unique cache key
        :param response: Response to cache
        :param expiration: Expiration time in seconds (default 1 hour)
        :return: Boolean indicating success
        """
        redis_client = cls.get_connection()
        if not redis_client:
            return False
        
        try:
            # Cache response with specified expiration
            redis_client.setex(key, expiration, json.dumps(response))
            return True
        except Exception as e:
            st.error(f"Redis caching error: {e}")
            return False
        finally:
            if redis_client:
                redis_client.close()

    @classmethod
    def get_cached_response(cls, key):
        """
        Retrieve a cached response from Redis
        
        :param key: Unique cache key
        :return: Cached response or None
        """
        redis_client = cls.get_connection()
        if not redis_client:
            return None
        
        try:
            cached_response = redis_client.get(key)
            return json.loads(cached_response) if cached_response else None
        except Exception as e:
            st.error(f"Redis retrieval error: {e}")
            return None
        finally:
            if redis_client:
                redis_client.close()

    @classmethod
    def delete_cached_response(cls, key):
        """
        Delete a specific cached response
        
        :param key: Unique cache key
        :return: Boolean indicating success
        """
        redis_client = cls.get_connection()
        if not redis_client:
            return False
        
        try:
            redis_client.delete(key)
            return True
        except Exception as e:
            st.error(f"Redis deletion error: {e}")
            return False
        finally:
            if redis_client:
                redis_client.close()

    @classmethod
    def clear_all_cache(cls):
        """
        Clear all cache in the current Redis database
        
        :return: Boolean indicating success
        """
        redis_client = cls.get_connection()
        if not redis_client:
            return False
        
        try:
            redis_client.flushdb()
            return True
        except Exception as e:
            st.error(f"Redis flush error: {e}")
            return False
        finally:
            if redis_client:
                redis_client.close()