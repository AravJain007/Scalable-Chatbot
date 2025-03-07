import os

class Config:
    SYSTEM_PROMPT = "You are a helpful chatbot that fulfills the users queries"
    PAGE_TITLE = "Scalable-Chatbot"
    OLLAMA_MODELS = ('deepseek-r1:1.5b', 'granite3.2-vision')
    
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "pgbouncer")  # PgBouncer service
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", 6432)         # PgBouncer port
    POSTGRES_DB = "yourappdb"
    POSTGRES_USER = "postgres"    # Default user
    POSTGRES_PASSWORD = "sarvam_litmus_test"
    
    REDIS_HOST = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT = os.getenv("REDIS_PORT", 6379)
    
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "ollama")
    OLLAMA_PORT = os.getenv("OLLAMA_PORT", 11434)