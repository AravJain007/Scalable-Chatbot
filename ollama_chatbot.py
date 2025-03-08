# ollama_chatbot.py
import streamlit as st
import hashlib
from datetime import datetime
import pytz
from backend.config import Config
from backend.utils.llm_helper import chat, stream_parser
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
    
    # User input area
    user_prompt = st.chat_input("Type your message here...")
    
    if st.session_state.model == "granite3.2-vision":
        img_data = st.file_uploader('Upload a PNG image', type=['png', 'jpg', 'jpeg'])
        print(img_data)
            
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
        
        # Update Redis context with new user message
        RedisManager.update_recent_context(
            st.session_state.active_session_id,
            "user",
            user_prompt
        )
        
        # Cache key for potentially reusing responses
        cache_key = f"chat:{model}:{hashlib.md5(user_prompt.encode()).hexdigest()}"
        cached_response = RedisManager.get_cached_response(cache_key)
        
        if cached_response:
            # Use cached response
            output_response = cached_response
            output_placeholder.markdown(output_response)
        else:
            # Handle special models with thinking capabilities
            if model == "deepseek-r1:1.5b":
                # Get response from model with thinking
                llm_stream = chat(st.session_state.active_session_id, model, images=None)
                
                # Create a status container for thinking state
                with st.status("Thinking...", expanded=True) as status:
                    try:
                        # Collect and display only thinking tokens
                        thinking_placeholder = st.empty()
                        thinking_response = ""
                        
                        for token in stream_parser(llm_stream):
                            if token == "<think>":
                                continue
                            elif token != "</think>" and token != "<think>":
                                thinking_response += token
                                thinking_placeholder.markdown(thinking_response)
                            elif token == "</think>":
                                break
                        
                        # Update status
                        status.update(label="Thinking complete", state="complete", expanded=False)
                    
                    except Exception as e:
                        status.update(label=f"Error: {str(e)}", state="error", expanded=True)
                
                # Display assistant response
                with st.chat_message("assistant"):
                    output_response = ""
                    output_placeholder = st.empty()
                    
                    for token in stream_parser(llm_stream):
                        if token and token not in ["<think>", "</think>"]:
                            output_response += token
                            output_placeholder.markdown(output_response)
            
            # Handle vision models
            elif model == "granite3.2-vision":
                
                # Get response from model
                llm_stream = chat(st.session_state.active_session_id, model, img_data)
                
                # Display assistant response
                with st.chat_message("assistant"):
                    output_response = ""
                    output_placeholder = st.empty()
                    
                    for token in stream_parser(llm_stream):
                        output_response += token
                        output_placeholder.markdown(output_response)
            
            # Cache the response
            RedisManager.cache_response(cache_key, output_response)
        
        PostgresManager.add_message(st.session_state.active_session_id, "assistant", output_response)
        
        # Update Redis with assistant response
        RedisManager.update_recent_context(
            st.session_state.active_session_id,
            "assistant",
            output_response
        )

if __name__ == "__main__":
    main()