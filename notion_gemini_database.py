import os
import importlib.util
import sys
import re
import google.generativeai as genai
from datetime import datetime
from notion_client import Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

def configure_gemini():
    """Configure the Gemini API client"""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        api_key = input("Please enter your Google API key: ").strip()
        os.environ["GOOGLE_API_KEY"] = api_key
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-2.0-flash')

def get_notion_client():
    """Initialize and return Notion client"""
    notion_token = os.getenv('NOTION_TOKEN')
    if not notion_token:
        notion_token = input("Please enter your Notion token: ").strip()
        os.environ["NOTION_TOKEN"] = notion_token
    return Client(auth=notion_token)

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

def extract_database_content(client, database_id):
    """Extract content from a Notion database"""
    try:
        # Get database structure
        database = client.databases.retrieve(database_id)
        
        # Get database contents
        response = client.databases.query(
            database_id=database_id,
            page_size=100  # Adjust as needed
        )
        
        # Format database content
        content = f"Database: {database.get('title', [{'plain_text': 'Untitled'}])[0]['plain_text']}\n"
        content += "=" * 80 + "\n\n"
        
        # Add properties/columns
        content += "Properties:\n"
        for prop_name, prop in database.get('properties', {}).items():
            content += f"- {prop_name} ({prop['type']})\n"
        content += "\n"
        
        # Add rows
        content += "Entries:\n"
        for page in response.get('results', []):
            content += "-" * 40 + "\n"
            for prop_name, prop in page.get('properties', {}).items():
                value = "N/A"
                if prop['type'] == 'title' and prop['title']:
                    value = prop['title'][0]['plain_text']
                elif prop['type'] == 'rich_text' and prop['rich_text']:
                    value = prop['rich_text'][0]['plain_text']
                elif prop['type'] == 'number':
                    value = str(prop['number'])
                elif prop['type'] == 'select' and prop['select']:
                    value = prop['select']['name']
                elif prop['type'] == 'multi_select':
                    value = ", ".join([item['name'] for item in prop['multi_select']])
                elif prop['type'] == 'date' and prop['date']:
                    value = prop['date']['start']
                elif prop['type'] == 'checkbox':
                    value = "Yes" if prop['checkbox'] else "No"
                
                content += f"{prop_name}: {value}\n"
            content += "\n"
        
        return content
    
    except Exception as e:
        return f"Error extracting database content: {str(e)}"

def get_page_content(client, page_id):
    """Extract content from a Notion page"""
    try:
        # Get page blocks
        blocks = client.blocks.children.list(block_id=page_id)
        
        # Format page content
        content = ""
        for block in blocks.get('results', []):
            block_type = block.get('type')
            
            if block_type == 'paragraph':
                if block['paragraph'].get('rich_text'):
                    content += block['paragraph']['rich_text'][0]['plain_text'] + "\n"
            
            elif block_type == 'heading_1':
                if block['heading_1'].get('rich_text'):
                    content += "# " + block['heading_1']['rich_text'][0]['plain_text'] + "\n"
            
            elif block_type == 'heading_2':
                if block['heading_2'].get('rich_text'):
                    content += "## " + block['heading_2']['rich_text'][0]['plain_text'] + "\n"
            
            elif block_type == 'heading_3':
                if block['heading_3'].get('rich_text'):
                    content += "### " + block['heading_3']['rich_text'][0]['plain_text'] + "\n"
            
            elif block_type == 'bulleted_list_item':
                if block['bulleted_list_item'].get('rich_text'):
                    content += "• " + block['bulleted_list_item']['rich_text'][0]['plain_text'] + "\n"
            
            elif block_type == 'numbered_list_item':
                if block['numbered_list_item'].get('rich_text'):
                    content += "1. " + block['numbered_list_item']['rich_text'][0]['plain_text'] + "\n"
            
            elif block_type == 'to_do':
                if block['to_do'].get('rich_text'):
                    checkbox = "☑" if block['to_do']['checked'] else "☐"
                    content += f"{checkbox} {block['to_do']['rich_text'][0]['plain_text']}\n"
            
            elif block_type == 'code':
                if block['code'].get('rich_text'):
                    content += "```" + block['code']['language'] + "\n"
                    content += block['code']['rich_text'][0]['plain_text'] + "\n"
                    content += "```\n"
            
            elif block_type == 'quote':
                if block['quote'].get('rich_text'):
                    content += "> " + block['quote']['rich_text'][0]['plain_text'] + "\n"
            
            elif block_type == 'callout':
                if block['callout'].get('rich_text'):
                    content += "💡 " + block['callout']['rich_text'][0]['plain_text'] + "\n"
            
            # Recursively get content from child blocks
            if block.get('has_children'):
                child_blocks = client.blocks.children.list(block_id=block['id'])
                content += get_page_content(client, block['id'])
        
        return content
    
    except Exception as e:
        return f"Error extracting page content: {str(e)}"

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
{content}

Answer the following query based on the content:
{query}

If the query asks for specific information (e.g., to-do lists, definitions, or database entries), extract and format it clearly. If the information isn't in the content, say so. Be concise and clear."""
        
        response = model.generate_content(prompt)
        return response.text.strip()
    
    except Exception as e:
        return f"Error querying Gemini API: {str(e)}"

def main():
    print(" Notion + Gemini AI Chat (Pages & Databases)")
    print("=" * 60)
    
    # Initialize clients
    notion_client = get_notion_client()
    gemini_model = configure_gemini()
    
    # First, get pages
    print(" Fetching accessible Notion pages...")
    pages_response = notion_client.search(
        query="",
        filter={
            'property': 'object',
            'value': 'page'
        }
    )
    
    pages = pages_response.get('results', [])
    
    # Then, get databases
    print(" Fetching accessible Notion databases...")
    databases_response = notion_client.search(
        query="",
        filter={
            'property': 'object',
            'value': 'database'
        }
    )
    
    databases = databases_response.get('results', [])
    
    if not pages and not databases:
        print(" No accessible pages or databases found.")
        return
    
    # Display available pages
    if pages:
        print("\n Available pages:")
        for i, page in enumerate(pages, 1):
            title = page.get('properties', {}).get('title', {}).get('title', [{'plain_text': 'Untitled'}])[0]['plain_text']
            print(f"{i}. {title} (Page)")
    
    # Display available databases
    if databases:
        print("\n Available databases:")
        for i, db in enumerate(databases, 1):
            title = db.get('title', [{'plain_text': 'Untitled'}])[0]['plain_text']
            print(f"{i}. {title} (Database)")
    
    # Get user choice
    while True:
        try:
            total_items = len(pages) + len(databases)
            choice = input(f"\nEnter item number (1-{total_items}), 'all' for all content, or 'q' to quit: ").strip()
            
            if choice.lower() == 'q':
                print(" Goodbye!")
                return
            
            if choice.lower() == 'all':
                print("\n Extracting content from all pages and databases...")
                all_content = ""
                
                # Process pages
                for i, page in enumerate(pages, 1):
                    print(f"Processing page {i}/{len(pages)}: {page.get('properties', {}).get('title', {}).get('title', [{'plain_text': 'Untitled'}])[0]['plain_text']}")
                    content = get_page_content(notion_client, page['id'])
                    all_content += f"\n{'='*80}\n"
                    all_content += content + "\n\n"
                
                # Process databases
                for i, db in enumerate(databases, 1):
                    print(f"Processing database {i}/{len(databases)}: {db.get('title', [{'plain_text': 'Untitled'}])[0]['plain_text']}")
                    content = extract_database_content(notion_client, db['id'])
                    all_content += f"\n{'='*80}\n"
                    all_content += content + "\n\n"
                break
            
            item_num = int(choice)
            if 1 <= item_num <= total_items:
                if item_num <= len(pages):
                    # Selected a page
                    selected_item = pages[item_num - 1]
                    all_content = get_page_content(notion_client, selected_item['id'])
                else:
                    # Selected a database
                    selected_item = databases[item_num - len(pages) - 1]
                    all_content = extract_database_content(notion_client, selected_item['id'])
                break
            else:
                print(f" Please enter a number between 1 and {total_items}")
                
        except ValueError:
            print(" Please enter a valid number, 'all', or 'q' to quit")
    
    # Conversational loop
    print("\n Ready to chat! Ask about your Notion content.")
    print("Type 'q' to quit.")
    
    while True:
        query = input("\nYour query: ").strip()
        if query.lower() == 'q':
            print(" Goodbye!")
            break
        
        if not query:
            print(" Please enter a valid query.")
            continue
        
        response = query_gemini(gemini_model, all_content, query)
        print("\n Response:")
        print(response)
        print("=" * 60)

if __name__ == '__main__':
    main() 