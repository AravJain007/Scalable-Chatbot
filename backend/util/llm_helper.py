import ollama
from backend.config import Config

system_prompt = Config.SYSTEM_PROMPT

def chat(user_prompt, model, images):
    if model == "deepseek-r1:1.5b":
        stream = ollama.chat(
            model=model,
            messages=[{'role': 'assistant', 'content': system_prompt},
                    {'role': 'user', 'content': f"{user_prompt}"}],
            stream=True,
        )

        return stream
    elif model == "granite3.2-vision":
        stream = ollama.chat(
            model=model,
            messages=[{'role': 'assistant', 'content': system_prompt, "images":[]},
                    {'role': 'user', 'content': f"{user_prompt}", 'images':[images]}],
            stream=True,
        )

        return stream

# handles stream response back from LLM
def stream_parser(stream):
    for chunk in stream:
        yield chunk['message']['content']