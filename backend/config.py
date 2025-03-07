class Config:
    PAGE_TITLE = "Streamlit Ollama Chatbot"
    SYSTEM_PROMPT = f"""You can answer questions for users on any topic."""

    # Ollama Configuration
    OLLAMA_PORT = 8080
    OLLAMA_MODELS = ('deepseek-r1:1.5b', 'granite3.2-vision')
    
    # PostgreSQL Configuration
    POSTGRES_HOST = 'postgres-service'
    POSTGRES_PORT = 30432
    POSTGRES_DB = 'yourappdb'
    POSTGRES_USER = 'postgres'
    POSTGRES_PASSWORD = 'sarvam_litmus_test'
    
    # Redis Configuration
    REDIS_HOST = 'localhost'
    REDIS_PORT = 30379  # Default Redis port