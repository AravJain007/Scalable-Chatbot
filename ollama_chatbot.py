import streamlit as st
from backend.config import Config
from backend.util.llm_helper import chat, stream_parser

# Set page configuration
st.set_page_config(
    page_title=Config.PAGE_TITLE,
    initial_sidebar_state="expanded"
)
st.title(Config.PAGE_TITLE)

# Sidebar navigation
with st.sidebar:
    st.markdown("# Chat Options")
    model = st.selectbox('What model would you like to use?', Config.OLLAMA_MODELS)

# Initialize session state for messages
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display existing chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if model == "deepseek-r1:1.5b":
    # User input
    if user_prompt := st.chat_input("What would you like to ask?"):
        # Display user message
        with st.chat_message("user"):
            st.markdown(user_prompt)
        
        # Add user message to session state
        st.session_state.messages.append({"role": "user", "content": user_prompt})

        # Retrieve response from model
        llm_stream = chat(user_prompt, model=model)
        
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
        
        # Add assistant response to session state
        st.session_state.messages.append({"role": "assistant", "content": output_response})

elif model == "granite3.2-vision":
    uploaded_files = st.file_uploader(
        "Choose a CSV file", accept_multiple_files=True
    )
    for uploaded_file in uploaded_files:
        bytes_data = uploaded_file.read()
        st.write("filename:", uploaded_file.name)
        st.write(bytes_data)
    if user_prompt := st.chat_input("What would you like to ask?"):
        # Display user message
        with st.chat_message("user"):
            st.markdown(user_prompt)
        
        # Add user message to session state
        st.session_state.messages.append({"role": "user", "content": user_prompt})

        # Retrieve response from model
        llm_stream = chat(user_prompt, model=model)
        
        # Display assistant response
        with st.chat_message("assistant"):
            output_response = ""
            output_placeholder = st.empty()
            
            for token in stream_parser(llm_stream):
                if token and token not in ["<think>", "</think>"]:
                    output_response += token
                    output_placeholder.markdown(output_response)
        
        # Add assistant response to session state
        st.session_state.messages.append({"role": "assistant", "content": output_response})