# ollama_chatbot.py
from importlib.metadata import files
from json import tool
from turtle import mode
import streamlit as st
import hashlib
import json
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
    if "pending_evaluation" not in st.session_state:
        st.session_state.pending_evaluation = None
    if "evaluation_stage" not in st.session_state:
        st.session_state.evaluation_stage = None
    if "web_search_results" not in st.session_state:
        st.session_state.web_search_results = None

    def start_new_session():
        st.session_state.active_session_id = None
        st.session_state.model = Config.OLLAMA_MODELS[0]
        st.session_state.pending_evaluation = None
        st.session_state.evaluation_stage = None
        st.session_state.web_search_results = None
    
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
    
    # Handle evaluation stage if active
    if st.session_state.evaluation_stage == "pending" and st.session_state.pending_evaluation:
        # First show the original response
        with st.chat_message("assistant"):
            st.markdown(st.session_state.pending_evaluation)
            
            # Then show the evaluation option
            st.info("This response contains information from web search. Would you like to evaluate the factual accuracy?")
            
            col1, col2 = st.columns(2)
            if col1.button("Evaluate", type="primary"):
                st.session_state.evaluation_stage = "evaluating"
                st.rerun()
                
            if col2.button("Don't Evaluate"):
                # Save original response
                PostgresManager.add_message(
                    st.session_state.active_session_id, 
                    "assistant", 
                    st.session_state.pending_evaluation
                )
                RedisManager.update_recent_context(
                    st.session_state.active_session_id, 
                    "assistant", 
                    st.session_state.pending_evaluation
                )
                
                # Reset evaluation state
                st.session_state.pending_evaluation = None
                st.session_state.evaluation_stage = None
                st.session_state.web_search_results = None
                st.rerun()
    
    elif st.session_state.evaluation_stage == "evaluating" and st.session_state.pending_evaluation:
        # Perform evaluation
        with st.status("Evaluating response accuracy...", expanded=True) as status:
            # Break response into statements
            response_text = st.session_state.pending_evaluation
            statements = break_into_statements(response_text)
            
            # Get web search results
            search_results = st.session_state.web_search_results
            
            # Prepare evaluation prompt with JSON output format
            evaluation_results = {}
            
            st.write("Analyzing statements for factual accuracy...")
            
            # Process statements in batches to avoid long prompts
            batch_size = 3
            for i in range(0, len(statements), batch_size):
                batch = statements[i:i+batch_size]
                batch_nums = list(range(i+1, i+len(batch)+1))
                
                # Create evaluation prompt for this batch
                evaluation_prompt = create_json_evaluation_prompt(
                    batch, 
                    batch_nums,
                    search_results
                )
                
                st.write(f"Evaluating statements {batch_nums[0]}-{batch_nums[-1]}...")
                
                # Send to LLM for evaluation
                model = st.session_state.model
                messages = [{"role": "user", "content": evaluation_prompt}]
                evaluation_stream = generate_response(model, messages)
                
                evaluation_response = ""
                for token in stream_parser(evaluation_stream):
                    if token:
                        evaluation_response += token
                
                # Parse JSON response
                batch_results = parse_json_evaluation(evaluation_response)
                evaluation_results.update(batch_results)
            
            # Apply highlighting
            highlighted_response = apply_highlighting(response_text, statements, evaluation_results)
            status.update(label="Evaluation complete", state="complete", expanded=False)
        
        # Display highlighted response
        with st.chat_message("assistant"):
            st.markdown(highlighted_response)
            
            # Save highlighted response
            PostgresManager.add_message(
                st.session_state.active_session_id, 
                "assistant", 
                highlighted_response
            )
            RedisManager.update_recent_context(
                st.session_state.active_session_id, 
                "assistant", 
                highlighted_response
            )
            
            # Reset evaluation state
            st.session_state.pending_evaluation = None
            st.session_state.evaluation_stage = None
            st.session_state.web_search_results = None
    
    # Normal chat input functionality
    user_prompt = st.chat_input("Type your message here...")
    img_data = None
    if st.session_state.model == "granite3.2-vision":
        img_data = st.file_uploader('Upload a PNG image', type=['png', 'jpg', 'jpeg'])
            
    # Handle user input
    if user_prompt and st.session_state.evaluation_stage is None:
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
            elif model == "qwen2.5":
                with st.status("🛠️ Processing tools...", expanded=True) as tool_status:
                    # First status update for analysis
                    st.write("🔍 Analyzing query for tool requirements...")
                    tool_selection = select_tool(model, user_prompt)
                    tool_name = tool_selection.get("tool", "none")
                    tool_results = ""
                    tool_context = None
                    is_web_search = False  # Flag to track if we used web search
                    search_results = None  # Store search results for evaluation

                    if tool_name != "none":
                        # Display selected tool
                        st.write(f"🛠️ Selected tool: {tool_name.replace('_', ' ')}")
                        
                        # Define the status callback function
                        def update_tool_status(message):
                            st.write(message)
                            
                        parameters = tool_selection.get("parameters", {})
                        tool_results = execute_tool(tool_name, parameters, st.session_state.active_session_id, update_tool_status)
                        
                        # Set web_search flag if applicable
                        is_web_search = (tool_name == "web_search")
                        
                        # Save search results for evaluation if needed
                        if is_web_search:
                            # Assuming tool_results contains search results
                            # This part depends on how your web search returns results
                            try:
                                search_results = tool_results
                            except:
                                search_results = f"Search results: {tool_results}"
                        
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
                is_web_search = False

            # Default for other models
            else:
                modified_user_message = messages + [{"role": "user", "content": user_prompt}]
                stream = generate_response(model, modified_user_message)
                is_web_search = False

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
                output_response = r""
                output_placeholder = st.empty()
                
                for token in stream_parser(stream):
                    if token and token not in ["<think>", "</think>"]:
                        output_response += token
                        output_placeholder.markdown(output_response)
            
            # Cache response
            RedisManager.cache_response(cache_key, output_response)
            
            # If web search was used, enter evaluation stage
            if model == "qwen2.5":
                if is_web_search:
                    st.session_state.pending_evaluation = output_response
                    st.session_state.web_search_results = search_results
                    st.session_state.evaluation_stage = "pending"
                    st.rerun()
            else:
                # Save to DB for non-web search responses
                PostgresManager.add_message(st.session_state.active_session_id, "assistant", output_response)
                RedisManager.update_recent_context(st.session_state.active_session_id, "assistant", output_response)

# Helper functions for evaluation
def break_into_statements(text):
    """
    Break text into individual statements for evaluation.
    This is a simple implementation - for production, you might want more sophisticated sentence parsing.
    """
    # Split by periods, exclamation points, and question marks
    sentences = []
    current_sentence = ""
    
    for char in text:
        current_sentence += char
        if char in ['.', '!', '?'] and len(current_sentence.strip()) > 0:
            sentences.append(current_sentence.strip())
            current_sentence = ""
    
    # Add any remaining text as a sentence
    if current_sentence.strip():
        sentences.append(current_sentence.strip())
    
    # Filter out very short statements, headings, or other non-factual content
    return [s for s in sentences if len(s.split()) > 3 and not s.startswith('#')]

def create_json_evaluation_prompt(statements, statement_numbers, search_results):
    """Create a prompt for the LLM to evaluate statements with JSON output"""
    numbered_statements = [f"{i}. {statement}" for i, statement in zip(statement_numbers, statements)]
    statements_text = "\n".join(numbered_statements)
    
    return f"""You are a factual accuracy evaluator. 
Evaluate each statement below against the provided search results to determine if it's accurate.

SEARCH RESULTS:
{search_results}

STATEMENTS TO EVALUATE:
{statements_text}

Provide your evaluation as a JSON object with the following structure:
{{
  "evaluations": [
    {{
      "statement_number": 1,
      "is_accurate": true/false,
      "confidence": "high/medium/low",
      "explanation": "Brief explanation"
    }},
    ...
  ]
}}

Only include the JSON object in your response, nothing else.
"""

def parse_json_evaluation(evaluation_response):
    """
    Parse the LLM's JSON evaluation response
    Returns a dictionary mapping statement numbers to accuracy evaluations
    """
    # Extract JSON from response (in case there's other text)
    try:
        # Find JSON content (anything between braces)
        json_start = evaluation_response.find('{')
        json_end = evaluation_response.rfind('}') + 1
        
        if json_start >= 0 and json_end > 0:
            json_content = evaluation_response[json_start:json_end]
            data = json.loads(json_content)
            
            # Build the results dictionary
            results = {}
            if "evaluations" in data:
                for eval_item in data["evaluations"]:
                    statement_num = eval_item.get("statement_number")
                    is_accurate = eval_item.get("is_accurate", True)
                    
                    if statement_num is not None:
                        results[statement_num] = is_accurate
            
            return results
        else:
            # Fallback if no JSON brackets found
            return {}
            
    except json.JSONDecodeError:
        # Fallback with manual parsing in case JSON is malformed
        results = {}
        if "statement_number" in evaluation_response and "is_accurate" in evaluation_response:
            lines = evaluation_response.split("\n")
            for line in lines:
                if "statement_number" in line and "is_accurate" in line:
                    try:
                        num_part = line.split("statement_number")[1].split(",")[0]
                        num = int(''.join(filter(str.isdigit, num_part)))
                        
                        is_accurate = "true" in line.lower() and "false" not in line.lower()
                        results[num] = is_accurate
                    except:
                        continue
        return results

def apply_highlighting(text, statements, evaluation_results):
    """
    Apply highlighting to the original text based on evaluation results
    """
    highlighted_text = text
    
    # Replace statements that were marked as inaccurate (false)
    for i, statement in enumerate(statements, 1):
        if i in evaluation_results and not evaluation_results[i]:
            # Mark false statements with red highlighting (using Streamlit markdown syntax)
            highlighted_statement = f":red[:red-background[{statement}]]"
            # Replace in the text, being careful about exact matches
            highlighted_text = highlighted_text.replace(statement, highlighted_statement)
    
    return highlighted_text

if __name__ == "__main__":
    main()