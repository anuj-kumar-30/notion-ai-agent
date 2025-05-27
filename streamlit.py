import streamlit as st
import os
import importlib.util
import sys
import re
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

# Dynamically import notion_pages.py and notion_databases.py
spec = importlib.util.spec_from_file_location("notion_pages", "notion_pages.py")
notion_pages = importlib.util.module_from_spec(spec)
sys.modules["notion_pages"] = notion_pages
spec.loader.exec_module(notion_pages)

spec = importlib.util.spec_from_file_location("notion_databases", "notion_databases.py")
notion_databases = importlib.util.module_from_spec(spec)
sys.modules["notion_databases"] = notion_databases
spec.loader.exec_module(notion_databases)

# Custom CSS for modern styling
st.markdown("""
<style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
        font-family: 'Inter', sans-serif;
    }
    .sidebar .sidebar-content {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
    }
    .stButton > button {
        background-color: #007bff;
        color: white;
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        background-color: #0056b3;
        transform: translateY(-2px);
    }
    .chat-message {
        background-color: #e9ecef;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .response-container {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-top: 20px;
    }
    .stTextInput > div > div > input {
        border-radius: 8px;
        padding: 10px;
        border: 1px solid #ced4da;
    }
    h1, h2, h3 {
        color: #343a40;
    }
    .content-type-selector {
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

def configure_gemini():
    """Configure the Gemini API client"""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        st.error("GOOGLE_API_KEY environment variable is not set")
        return None
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-2.0-flash')

def query_gemini(model, content, query):
    """Query the Gemini API with Notion content as context"""
    try:
        prompt = f"""You are a helpful assistant with access to the following Notion content:
{content}

Answer the following query based on the content:
{query}

If the query asks for specific information (e.g., to-do lists, definitions, or database entries), extract and format it clearly. If the information isn't in the content, say so. Be concise and clear."""
        
        response = model.generate_content(prompt)
        return response.text.strip()
    
    except Exception as e:
        return f"Error querying Gemini API: {str(e)}"

def load_content(pages, databases, content_type, selected_page, selected_db):
    """Load content based on selections"""
    all_content = ""
    
    if content_type in ["Pages", "Both"] and pages:
        if selected_page == "All Pages":
            for i, page in enumerate(pages, 1):
                st.sidebar.text(f"Processing page {i}/{len(pages)}: {page['title']}")
                content_data = notion_pages.get_page_content(page['id'])
                if content_data:
                    all_content += f"\n{'='*80}\nPAGE: {content_data['title']}\n{'='*80}\n{content_data['content']}\n\n"
        else:
            page_index = [f"{page['title']} (Last edited: {page['last_edited_time'][:10]})" for page in pages].index(selected_page)
            selected_page_data = pages[page_index]
            content_data = notion_pages.get_page_content(selected_page_data['id'])
            if content_data:
                all_content += f"\n{'='*80}\nPAGE: {content_data['title']}\n{'='*80}\n{content_data['content']}\n\n"

    if content_type in ["Databases", "Both"] and databases:
        if selected_db == "All Databases":
            for i, db in enumerate(databases, 1):
                st.sidebar.text(f"Processing database {i}/{len(databases)}: {db['title']}")
                content = notion_databases.get_database_content(db['id'])
                if content:
                    formatted_content = notion_databases.format_database_content(content)
                    all_content += f"\n{'='*80}\n{formatted_content}\n\n"
        else:
            db_index = [f"{db['title']} (Last edited: {db['last_edited_time'][:10]})" for db in databases].index(selected_db)
            selected_db_data = databases[db_index]
            content = notion_databases.get_database_content(selected_db_data['id'])
            if content:
                formatted_content = notion_databases.format_database_content(content)
                all_content += f"\n{'='*80}\n{formatted_content}\n\n"
    
    return all_content

def main():
    st.title("🚀 Notion + Gemini AI Chat")
    st.markdown("Interact with your Notion content using Google's Gemini 2.0 Flash API. Select content type, ask questions, and get insights!")

    # Initialize session state
    if "pages" not in st.session_state:
        with st.spinner("🔍 Fetching Notion pages..."):
            st.session_state["pages"] = notion_pages.get_accessible_pages()
    if "databases" not in st.session_state:
        with st.spinner("🔍 Fetching Notion databases..."):
            st.session_state["databases"] = notion_databases.get_accessible_databases()
    if "selected_content" not in st.session_state:
        st.session_state["selected_content"] = ""
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
    if "last_selections" not in st.session_state:
        st.session_state["last_selections"] = {}

    # Content type selection
    st.sidebar.header("📚 Content Type")
    content_type = st.sidebar.radio(
        "Select content type",
        ["Pages", "Databases", "Both"],
        index=2,
        key="content_type"
    )

    # Configure Gemini
    model = configure_gemini()
    if not model:
        st.sidebar.warning("Please enter a valid Google API key to proceed.")
        return

    # Content selection based on type
    selected_page = None
    selected_db = None
    
    if content_type in ["Pages", "Both"]:
        st.sidebar.header("📄 Notion Pages")
        pages = st.session_state["pages"]
        if not pages:
            st.sidebar.warning("No accessible pages found.")
        else:
            page_options = ["All Pages"] + [f"{page['title']} (Last edited: {page['last_edited_time'][:10]})" for page in pages]
            selected_page = st.sidebar.selectbox("Select a Notion page", page_options, index=0)

    if content_type in ["Databases", "Both"]:
        st.sidebar.header("🗃️ Notion Databases")
        databases = st.session_state["databases"]
        if not databases:
            st.sidebar.warning("No accessible databases found.")
        else:
            db_options = ["All Databases"] + [f"{db['title']} (Last edited: {db['last_edited_time'][:10]})" for db in databases]
            selected_db = st.sidebar.selectbox("Select a Notion database", db_options, index=0)

    # Check if selections have changed
    current_selections = {
        "content_type": content_type,
        "selected_page": selected_page,
        "selected_db": selected_db
    }
    
    if current_selections != st.session_state["last_selections"]:
        with st.spinner("📥 Loading content..."):
            st.session_state["selected_content"] = load_content(
                st.session_state["pages"],
                st.session_state["databases"],
                content_type,
                selected_page,
                selected_db
            )
        st.session_state["last_selections"] = current_selections

    # Chat interface
    st.subheader("🤖 Chat with Your Notion Content")
    st.markdown("Ask about to-do lists, definitions, database entries, or anything in your Notion content.")

    # Query input
    query = st.text_input("Your query", placeholder="Enter your question here...")
    if st.button("Send Query", key="send_query"):
        if query:
            with st.spinner("Processing your query..."):
                response = query_gemini(model, st.session_state["selected_content"], query)
                st.session_state["chat_history"].append({"query": query, "response": response})
        else:
            st.warning("Please enter a query.")

    # Display chat history
    if st.session_state["chat_history"]:
        st.subheader("📜 Conversation History")
        for i, chat in enumerate(reversed(st.session_state["chat_history"])):
            with st.container():
                st.markdown(f"<div class='chat-message'><b>You:</b> {chat['query']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='response-container'><b>Gemini:</b><br>{chat['response']}</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()