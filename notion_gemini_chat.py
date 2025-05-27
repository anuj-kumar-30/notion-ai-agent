import os
import importlib.util
import sys
import re
import google.generativeai as genai
from datetime import datetime

# Dynamically import notion_pages.py
spec = importlib.util.spec_from_file_location("notion_pages", "notion_pages.py")
notion_pages = importlib.util.module_from_spec(spec)
sys.modules["notion_pages"] = notion_pages
spec.loader.exec_module(notion_pages)

def configure_gemini():
    """Configure the Gemini API client"""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        api_key = input("Please enter your Google API key: ").strip()
        os.environ["GOOGLE_API_KEY"] = api_key
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-2.0-flash')

def extract_todos(content, date=None):
    """Extract to-do items from content, optionally for a specific date"""
    todos = []
    lines = content.split('\n')
    date_pattern = re.compile(r'(\d{4}-\d{2}-\d{2})')
    
    for i, line in enumerate(lines):
        if line.startswith('☐') or line.startswith('☑'):
            todo_text = line[2:].strip()
            # Check for date in the line or nearby lines
            associated_date = None
            for j in range(max(0, i-2), min(len(lines), i+3)):
                match = date_pattern.search(lines[j])
                if match:
                    associated_date = match.group(1)
                    break
            
            if date:
                if associated_date == date:
                    todos.append({'text': todo_text, 'completed': line.startswith('☑')})
            else:
                todos.append({
                    'text': todo_text,
                    'completed': line.startswith('☑'),
                    'date': associated_date if associated_date else 'No date'
                })
    
    return todos

def extract_definitions(content):
    """Extract definitions from markdown content"""
    definitions = []
    current_section = None
    lines = content.split('\n')
    
    for line in lines:
        if line.startswith('## ') or line.startswith('# '):
            current_section = line.strip('# ').strip()
        elif line.strip() and current_section and 'definition' in current_section.lower():
            definitions.append({'term': current_section, 'definition': line.strip()})
    
    return definitions

def query_gemini(model, content, query):
    """Query the Gemini API with Notion content as context"""
    try:
        # Check for specific query types
        today = datetime.now().strftime('%Y-%m-%d')
        if 'today' in query.lower() and 'todo' in query.lower():
            todos = extract_todos(content, date=today)
            if not todos:
                return "No to-do items found for today."
            response = "Today's to-do items:\n"
            for todo in todos:
                status = '✓' if todo['completed'] else 'X'
                response += f"{status} {todo['text']}\n"
            return response
        
        elif 'definition' in query.lower():
            definitions = extract_definitions(content)
            if not definitions:
                return "No definitions found in the content."
            response = "Definitions found:\n"
            for defn in definitions:
                response += f"**{defn['term']}**: {defn['definition']}\n"
            return response
        
        # General query: send to Gemini
        prompt = f"""You are a helpful assistant with access to the following Notion content:
{content[:]}  # Truncate to avoid API limits

Answer the following query based on the content:
{query}

If the query asks for specific information (e.g., to-do lists or definitions), extract and format it clearly. If the information isn't in the content, say so. Be concise and clear."""
        
        response = model.generate_content(prompt)
        return response.text.strip()
    
    except Exception as e:
        return f"Error querying Gemini API: {str(e)}"

def main():
    print(" Notion + Gemini AI Chat")
    print("=" * 60)
    
    # Fetch Notion pages
    print(" Fetching accessible Notion pages...")
    pages = notion_pages.get_accessible_pages()
    
    if not notion_pages.display_pages(pages):
        return
    
    # Get user choice
    while True:
        try:
            choice = input(f"\nEnter page number (1-{len(pages)}), 'all' for all pages, or 'q' to quit: ").strip()
            
            if choice.lower() == 'q':
                print(" Goodbye!")
                return
            
            if choice.lower() == 'all':
                print("\n Extracting content from all pages...")
                all_content = ""
                for i, page in enumerate(pages, 1):
                    print(f"Processing page {i}/{len(pages)}: {page['title']}")
                    content_data = notion_pages.get_page_content(page['id'])
                    if content_data:
                        all_content += f"\n{'='*80}\n"
                        all_content += f"PAGE: {content_data['title']}\n"
                        all_content += f"{'='*80}\n"
                        all_content += content_data['content'] + "\n\n"
                break
            
            page_num = int(choice)
            if 1 <= page_num <= len(pages):
                selected_page = pages[page_num - 1]
                content_data = notion_pages.get_page_content(selected_page['id'])
                if content_data:
                    all_content = content_data['content']
                else:
                    print(" Failed to extract content")
                    return
                break
            else:
                print(f" Please enter a number between 1 and {len(pages)}")
                
        except ValueError:
            print(" Please enter a valid number, 'all', or 'q' to quit")
    
    # Configure Gemini
    model = configure_gemini()
    
    # Conversational loop
    print("\n Ready to chat! Ask about your Notion content (e.g., 'What are my today's to-do items?' or 'Show me definitions').")
    print("Type 'q' to quit.")
    
    while True:
        query = input("\nYour query: ").strip()
        if query.lower() == 'q':
            print(" Goodbye!")
            break
        
        if not query:
            print(" Please enter a valid query.")
            continue
        
        response = query_gemini(model, all_content, query)
        print("\n Response:")
        print(response)
        print("=" * 60)

if __name__ == '__main__':
    main()