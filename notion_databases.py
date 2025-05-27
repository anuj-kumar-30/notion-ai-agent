import os
from notion_client import Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

def get_notion_client():
    """Initialize and return Notion client"""
    notion_token = os.getenv('NOTION_TOKEN')
    if not notion_token:
        raise ValueError("NOTION_TOKEN environment variable is not set")
    return Client(auth=notion_token)

def get_accessible_databases():
    """Get all accessible databases from Notion"""
    client = get_notion_client()
    
    try:
        response = client.search(
            query="",
            filter={
                'property': 'object',
                'value': 'database'
            }
        )
        
        databases = []
        for db in response.get('results', []):
            title = db.get('title', [{'plain_text': 'Untitled'}])[0]['plain_text']
            databases.append({
                'id': db['id'],
                'title': title,
                'url': db.get('url', ''),
                'created_time': db.get('created_time', ''),
                'last_edited_time': db.get('last_edited_time', '')
            })
        
        return databases
    
    except Exception as e:
        print(f"Error fetching databases: {str(e)}")
        return []

def get_database_content(database_id):
    """Extract content from a Notion database"""
    client = get_notion_client()
    
    try:
        # Get database structure
        database = client.databases.retrieve(database_id)
        
        # Get database contents
        response = client.databases.query(
            database_id=database_id,
            page_size=100  # Adjust as needed
        )
        
        # Format database content
        content = {
            'title': database.get('title', [{'plain_text': 'Untitled'}])[0]['plain_text'],
            'properties': {},
            'entries': []
        }
        
        # Add properties/columns
        for prop_name, prop in database.get('properties', {}).items():
            content['properties'][prop_name] = prop['type']
        
        # Add rows
        for page in response.get('results', []):
            entry = {}
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
                    value = [item['name'] for item in prop['multi_select']]
                elif prop['type'] == 'date' and prop['date']:
                    value = prop['date']['start']
                elif prop['type'] == 'checkbox':
                    value = prop['checkbox']
                
                entry[prop_name] = value
            
            content['entries'].append(entry)
        
        return content
    
    except Exception as e:
        print(f"Error extracting database content: {str(e)}")
        return None

def format_database_content(content):
    """Format database content for display or processing"""
    if not content:
        return "No database content available."
    
    formatted = f"Database: {content['title']}\n"
    formatted += "=" * 80 + "\n\n"
    
    # Add properties
    formatted += "Properties:\n"
    for prop_name, prop_type in content['properties'].items():
        formatted += f"- {prop_name} ({prop_type})\n"
    formatted += "\n"
    
    # Add entries
    formatted += "Entries:\n"
    for entry in content['entries']:
        formatted += "-" * 40 + "\n"
        for prop_name, value in entry.items():
            if isinstance(value, list):
                value = ", ".join(value)
            formatted += f"{prop_name}: {value}\n"
        formatted += "\n"
    
    return formatted

def get_all_databases_content():
    """Get content from all accessible databases"""
    databases = get_accessible_databases()
    all_content = ""
    
    for db in databases:
        print(f"Processing database: {db['title']}")
        content = get_database_content(db['id'])
        if content:
            formatted_content = format_database_content(content)
            all_content += f"\n{'='*80}\n"
            all_content += formatted_content + "\n\n"
    
    return all_content 