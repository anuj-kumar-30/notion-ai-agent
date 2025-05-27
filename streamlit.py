import streamlit as st
import os
import importlib.util
import sys
import re
from datetime import datetime
import google.generativeai as genai

# Dynamically import notion_gemini_chat.py
spec = importlib.util.spec_from_file_location("notion_gemini_chat", "notion_gemini_chat.py")
notion_gemini_chat = importlib.util.module_from_spec(spec)
sys.modules["notion_gemini_chat"] = notion_gemini_chat
spec.loader.exec_module(notion_gemini_chat)

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
</style>
""", unsafe_allow_html=True)

def configure_gemini():
    """Configure the Gemini API client"""
    api_key = st.session_state.get("api_key", os.environ.get("GOOGLE_API_KEY", ""))
    if not api_key:
        api_key = st.sidebar.text_input("Enter Google API Key", type="password")
        if api_key:
            st.session_state["api_key"] = api_key
            os.environ["GOOGLE_API_KEY"] = api_key
            genai.configure(api_key=api_key)
            return genai.GenerativeModel('gemini-2.0-flash')
        return None
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-2.0-flash')

def main():
    st.title("🚀 Notion + Gemini AI Chat")
    st.markdown("Interact with your Notion content using Google's Gemini 2.0 Flash API. Select a page, ask questions, and get insights!")

    # Initialize session state
    if "pages" not in st.session_state:
        with st.spinner("🔍 Fetching Notion pages..."):
            st.session_state["pages"] = notion_gemini_chat.notion_pages.get_accessible_pages()
    if "selected_content" not in st.session_state:
        st.session_state["selected_content"] = ""
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    # Sidebar for page selection and API key
    st.sidebar.header("📄 Notion Pages")
    pages = st.session_state["pages"]
    if not pages:
        st.sidebar.error("❌ No accessible pages found! Share pages with your Notion integration first.")
        return

    page_options = ["All Pages"] + [f"{page['title']} (Last edited: {page['last_edited_time'][:10]})" for page in pages]
    selected_page = st.sidebar.selectbox("Select a Notion page", page_options, index=0)

    # Configure Gemini
    model = configure_gemini()
    if not model:
        st.sidebar.warning("Please enter a valid Google API key to proceed.")
        return

    # Fetch content based on selection
    if selected_page == "All Pages":
        if not st.session_state["selected_content"]:
            with st.spinner("📥 Extracting content from all pages..."):
                all_content = ""
                for i, page in enumerate(pages, 1):
                    st.sidebar.text(f"Processing {i}/{len(pages)}: {page['title']}")
                    content_data = notion_gemini_chat.notion_pages.get_page_content(page['id'])
                    if content_data:
                        all_content += f"\n{'='*80}\nPAGE: {content_data['title']}\n{'='*80}\n{content_data['content']}\n\n"
                st.session_state["selected_content"] = all_content
    else:
        page_index = page_options.index(selected_page) - 1
        selected_page_data = pages[page_index]
        if not st.session_state["selected_content"] or st.session_state.get("last_selected_page") != selected_page:
            with st.spinner(f"📥 Extracting content from {selected_page_data['title']}..."):
                content_data = notion_gemini_chat.notion_pages.get_page_content(selected_page_data['id'])
                if content_data:
                    st.session_state["selected_content"] = content_data['content']
                else:
                    st.error("❌ Failed to extract content.")
                    return
        st.session_state["last_selected_page"] = selected_page

    # Chat interface
    st.subheader("🤖 Chat with Your Notion Content")
    st.markdown("Ask about to-do lists, definitions, or anything in your Notion pages. Example: *What are my today's to-do items?* or *Show me definitions*.")

    # Query input
    query = st.text_input("Your query", placeholder="Enter your question here...")
    if st.button("Send Query", key="send_query"):
        if query:
            with st.spinner("Processing your query..."):
                response = notion_gemini_chat.query_gemini(model, st.session_state["selected_content"], query)
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