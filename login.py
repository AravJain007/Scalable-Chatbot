# login.py
import streamlit as st
from backend.utils.auth_manager import AuthManager
from backend.utils.postgres_manager import PostgresManager

def login_page():
    st.title("Chat Application Login")

    # Choose login method
    login_method = st.radio("Login Method", ["Login", "Create Account"])

    if login_method == "Login":
        # Login Form
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            login_button = st.form_submit_button("Login")

            if login_button:
                user = AuthManager.authenticate_user(email, password)
                if user:
                    # Store user info in session state
                    st.session_state.user_id = user['user_id']
                    st.session_state.username = user['username']
                    st.session_state.logged_in = True
                    
                    # Reset chat session variables
                    st.session_state.active_session_id = None
                    st.session_state.messages = []
                    
                    st.experimental_rerun()
                else:
                    st.error("Invalid email or password")

    else:
        # Create Account Form
        with st.form("signup_form"):
            username = st.text_input("Username")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            signup_button = st.form_submit_button("Create Account")

            if signup_button:
                if password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    user_id = AuthManager.create_user(username, email, password)
                    if user_id:
                        st.success("Account created successfully! Please log in.")

def main():
    # Check if user is logged in
    if 'logged_in' not in st.session_state or not st.session_state.logged_in:
        login_page()
    else:
        # Show sessions page or redirect to chat
        if 'active_session_id' not in st.session_state or not st.session_state.active_session_id:
            show_sessions_page()
        else:
            # Redirect to main chat application
            import ollama_chatbot
            ollama_chatbot.main()

def show_sessions_page():
    """
    Display a page showing all chat sessions and allowing user to create a new one
    """
    st.title("Your Chat Sessions")
    
    # Get user's chat sessions
    user_id = st.session_state.user_id
    chat_sessions = PostgresManager.get_user_chat_sessions(user_id)
    
    # New Session button prominently displayed
    if st.button("➕ Start New Chat Session", type="primary"):
        st.session_state.active_session_id = None
        st.session_state.messages = []
        
        # Redirect to chat page
        import ollama_chatbot
        ollama_chatbot.main()
        st.experimental_rerun()
    
    # No sessions yet message
    if not chat_sessions:
        st.info("You don't have any chat sessions yet. Start a new chat to begin!")
        return
    
    # Display existing sessions in a grid
    st.subheader("Recent Chat Sessions")
    
    # Use columns to create a grid layout
    col_count = 3
    cols = st.columns(col_count)
    
    for i, session in enumerate(chat_sessions):
        col_idx = i % col_count
        
        with cols[col_idx]:
            session_preview = PostgresManager.get_session_preview(session['session_id'])
            
            # Format the card
            with st.container(border=True):
                st.subheader(session['title'])
                st.caption(f"Last updated: {format_datetime(session['updated_at'])}")
                
                if session_preview and session_preview.get('first_message'):
                    st.text_area(
                        "First message:", 
                        session_preview['first_message'][:100] + "..." if len(session_preview['first_message']) > 100 else session_preview['first_message'],
                        height=60,
                        disabled=True
                    )
                
                # Button to open this session
                if st.button("Open Chat", key=f"open_{session['session_id']}"):
                    # Set this as the active session
                    st.session_state.active_session_id = session['session_id']
                    
                    # Load messages for this session
                    messages = PostgresManager.get_session_messages(session['session_id'])
                    st.session_state.messages = [{
                        "role": msg["role"],
                        "content": msg["content"]
                    } for msg in messages]
                    
                    # Set the model for this session
                    st.session_state.model = session['model_name']
                    
                    st.experimental_rerun()

def format_datetime(dt):
    """Format datetime to a user-friendly string (e.g., "6th March 2025, 7:00 pm")"""
    if not dt:
        return ""
    
    # Convert to user's timezone if needed (default to UTC)
    import pytz
    local_tz = pytz.timezone('UTC')  # Replace with user's timezone
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    local_dt = dt.astimezone(local_tz)
    
    # Format the date with day suffix (e.g., 1st, 2nd, 3rd)
    day = local_dt.day
    if 4 <= day <= 20 or 24 <= day <= 30:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    
    return local_dt.strftime(f"%-d{suffix} %B %Y, %-I:%M %p")

if __name__ == "__main__":
    main()