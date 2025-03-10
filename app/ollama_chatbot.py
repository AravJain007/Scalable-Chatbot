# ollama_chatbot.py
from importlib.metadata import files
from json import tool
import streamlit as st
import hashlib
from datetime import datetime
import pytz
from backend.config import Config
from backend.utils.llm_helper import *
from backend.utils.postgres_manager import PostgresManager
from backend.utils.redis_manager import RedisManager

def main():
    st.title(Config.PAGE_TITLE)
    
    # Ensure user is logged in
    if 'user_id' not in st.session_state:
        st.warning("Please log in to use the chat application")
        st.stop()
    
    user_id = st.session_state.user_id
    
    # Initialize session states
    if "active_session_id" not in st.session_state:
        st.session_state.active_session_id = None
    if "model" not in st.session_state:
        st.session_state.model = Config.OLLAMA_MODELS[0]

    def start_new_session():
        st.session_state.active_session_id = None
        st.session_state.model = Config.OLLAMA_MODELS[0]
    
    # Function to load a chat session
    def load_chat_session(session_id):
        messages = PostgresManager.get_session_messages(session_id)

        st.session_state.active_session_id = session_id
        recent_messages = messages[-3:] if len(messages) >=3 else messages
        for msg in reversed(recent_messages):
            RedisManager.update_recent_context(
                session_id, 
                msg["role"], 
                msg["content"]
            )
        
        # Also update the session model if available
        session_info = PostgresManager.get_session_preview(session_id)
        if session_info and 'info' in session_info:
            st.session_state.model = session_info['info']['model_name']
    
    # Sidebar for navigation and chat history
    with st.sidebar:
        st.markdown("# Chat Options")
        
        # New Session button at the top
        if st.button("➕ New Chat Session", key="new_session"):
            start_new_session()
            st.rerun()
        
        # Model selection
        st.session_state.model = st.selectbox(
            'Model', 
            Config.OLLAMA_MODELS,
            index=Config.OLLAMA_MODELS.index(st.session_state.model) if st.session_state.model in Config.OLLAMA_MODELS else 0
        )
        
        # Display chat history
        st.markdown("## Chat History")
        
        # Retrieve user's chat sessions
        chat_sessions = PostgresManager.get_user_chat_sessions(user_id)
        
        if not chat_sessions:
            st.info("No previous chat sessions found.")
        
        # Display each session with formatted timestamps
        for session in chat_sessions:
            session_title = session['title']
            
            # Create a special button that looks like a session entry
            if st.button(
                f"**{session_title}**",
                key=f"session_{session['session_id']}",
                help="Click to load this chat session"
            ):
                load_chat_session(session['session_id'])
                st.rerun()
    
    # Main chat area
    if not st.session_state.active_session_id and not st.session_state.messages:
        # Welcome message for new sessions
        st.markdown("## Welcome to a New Chat Session!")
        st.markdown("Select a model and start typing to begin your conversation.")
    
    # Display existing chat messages
    if st.session_state.active_session_id:
        messages = PostgresManager.get_session_messages(st.session_state.active_session_id)
        for message in messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    user_prompt = st.chat_input("Type your message here...")
    img_data = None
    if st.session_state.model == "granite3.2-vision":
        img_data = st.file_uploader('Upload a PNG image', type=['png', 'jpg', 'jpeg'])
            
    # Handle user input
    if user_prompt:
        model = st.session_state.model
        
        # Create session if not exists
        if not st.session_state.active_session_id:
            session_id = PostgresManager.create_chat_session(
                user_id, 
                model, 
                title=user_prompt[:50] + "..." if len(user_prompt) > 50 else user_prompt
            )
            st.session_state.active_session_id = session_id
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(user_prompt)
        
        # Save user message to DB
        PostgresManager.add_message(st.session_state.active_session_id, "user", user_prompt)
        
        # Update Redis context
        RedisManager.update_recent_context(
            st.session_state.active_session_id,
            "user",
            user_prompt
        )
        
        cache_key = f"chat:{model}:{hashlib.md5(user_prompt.encode()).hexdigest()}"
        cached_response = RedisManager.get_cached_response(cache_key)
        
        if cached_response:
            with st.chat_message("assistant"):
                st.markdown(cached_response)
            PostgresManager.add_message(st.session_state.active_session_id, "assistant", cached_response)
        else:
            messages = RedisManager.get_recent_context(st.session_state.active_session_id)
            if model == "granite3.2-vision":
                with st.status("🛠️ Processing Image...", expanded=True) as tool_status:    
                    messages = RedisManager.get_recent_context(st.session_state.active_session_id)
                    
                    # Process image upload
                    vision_messages = messages.copy()
                    if img_data:
                        import base64
                        img_bytes = img_data.read()
                        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                        
                        if vision_messages and vision_messages[-1]['role'] == 'user':
                            vision_messages[-1]['images'] = [img_base64]
                        else:
                            vision_messages.append({
                                "role": "user",
                                "content": user_prompt,
                                "images": [img_base64]
                            })
                            
                    tool_status.update(label="Processing image...", state="running")
                    stream = ollama.chat(
                        model=model,
                        messages=vision_messages,
                        stream=True
                    )
                    modified_user_message = None

                # Qwen - Function Calling
            elif model == "qwen2.5:3b":
                with st.status("🛠️ Processing tools...", expanded=True) as tool_status:
                    # First status update for analysis
                    st.write("🔍 Analyzing query for tool requirements...")
                    tool_selection = select_tool(model, user_prompt)
                    tool_name = tool_selection.get("tool", "none")
                    tool_results = ""
                    tool_context = None

                    if tool_name != "none":
                        # Display selected tool
                        st.write(f"🛠️ Selected tool: {tool_name.replace('_', ' ')}")
                        
                        # Define the status callback function
                        def update_tool_status(message):
                            st.write(message)
                            
                        parameters = tool_selection.get("parameters", {})
                        tool_results = execute_tool(tool_name, parameters, st.session_state.active_session_id, update_tool_status)
                        
                        # Build tool context
                        if tool_name == "calculator":
                            tool_context = Config.CALCULATOR_CONTEXT
                        elif tool_name == "web_search":
                            tool_context = Config.WEB_SEARCH_CONTEXT
                        else:
                            tool_context = Config.SYSTEM_PROMPT

                    modified_user_message = [{
                        "role": "user",
                        "content": f"""**TOOL RESULTS FROM {tool_name.upper()}:**\n{tool_results}\n{tool_context}\n**USER QUERY:**\n{user_prompt}"""
                    }]
                    stream = generate_response(model, modified_user_message)
                    tool_status.update(label="✅ Tool processing complete!", state="complete", expanded=False)

            # DeepSeek - Thinking Tokens
            elif model == "deepseek-r1:1.5b":
                modified_user_message = messages + [{"role": "user", "content": user_prompt}]
                stream = generate_response(model, modified_user_message)

            # Default for other models
            else:
                modified_user_message = [{"role": "user", "content": user_prompt}]
                stream = generate_response(model, modified_user_message)

            # Thinking Phase (DeepSeek Only)
            if model == "deepseek-r1:1.5b":
                with st.status("🧠 Thinking...", expanded=True) as status:
                    try:
                        thinking_response = ""
                        thinking_container = st.empty()
                        buffer = []
                        
                        for token in stream_parser(stream):
                            buffer.append(token)
                            if token == "<think>":
                                buffer = []
                            elif token == "</think>":
                                break
                            else:
                                thinking_response += token
                                thinking_container.markdown(thinking_response)

                        status.update(label="Thinking complete", state="complete", expanded=False)
                        
                    except Exception as e:
                        status.update(label=f"Error: {str(e)}", state="error", expanded=True)

            # Display Final Response
            with st.chat_message("assistant"):
                output_response = ""
                output_placeholder = st.empty()
                
                for token in stream_parser(stream):
                    if token and token not in ["<think>", "</think>"]:
                        output_response += token
                        output_placeholder.markdown(output_response)
            # Cache and save to DB
            RedisManager.cache_response(cache_key, output_response)
            PostgresManager.add_message(st.session_state.active_session_id, "assistant", output_response)
            RedisManager.update_recent_context(st.session_state.active_session_id, "assistant", output_response)

if __name__ == "__main__":
    main()