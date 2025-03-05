class Config:
    PAGE_TITLE = "Streamlit Ollama Chatbot"

    OLLAMA_MODELS = ('deepseek-r1:1.5b', 'granite3.2-vision')

    SYSTEM_PROMPT = f"""You can answer questions for users on any topic."""