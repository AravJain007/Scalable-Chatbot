from email import message
import ollama
from backend.config import Config
from backend.utils.redis_manager import RedisManager

system_prompt = Config.SYSTEM_PROMPT
# Set Ollama host to connect to Kubernetes service via NodePort
ollama.host = f"http://{Config.OLLAMA_HOST}:{Config.OLLAMA_PORT}"

def chat(session_id, model, images:None):
    messages = RedisManager.get_recent_context(session_id)
    if model == "deepseek-r1:1.5b":
        stream = ollama.chat(
            model=model,
            messages=messages,
            stream=True,
        )

        return stream
    elif model == "granite3.2-vision":
        stream = ollama.chat(
            model=model,
            messages=messages,
            stream=True,
        )

        return stream

# handles stream response back from LLM
def stream_parser(stream):
    for chunk in stream:
        yield chunk['message']['content']