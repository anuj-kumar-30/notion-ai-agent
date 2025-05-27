from notion_client import Client
import json
import re
import os 
from dotenv import load_dotenv

load_dotenv(override=True)
notion_token = os.getenv('NOTION_TOKEN')

def get_accessible_pages():
    """Get all pages that the integration has access to"""
    client = Client(auth=notion_token)
    
    try:
        response = client.search(
            query="",
            page_size=100,
            filter={
                "property": "object",
                "value": "page"
            }
        )
        
        pages = []
        for result in response.get('results', []):
            if result.get('object') == 'page':
                title = extract_title(result)
                
                pages.append({
                    'id': result['id'],
                    'title': title,
                    'url': result.get('url', ''),
                    'created_time': result.get('created_time', ''),
                    'last_edited_time': result.get('last_edited_time', ''),
                })
        
        return pages
        
    except Exception as e:
        print(f"Error fetching pages: {str(e)}")
        return []

def extract_title(page_data):
    """Extract title from page data"""
    title = "Untitled"
    if page_data.get('properties'):
        title_prop = page_data['properties'].get('title') or page_data['properties'].get('Name')
        if title_prop and title_prop.get('title') and len(title_prop['title']) > 0:
            title = title_prop['title'][0]['plain_text']
        elif title_prop and title_prop.get('rich_text') and len(title_prop['rich_text']) > 0:
            title = title_prop['rich_text'][0]['plain_text']
    return title

def extract_text_from_block(block):
    """Extract text content from a Notion block"""
    text_content = ""
    
    # Handle different block types
    block_type = block.get('type', '')
    block_data = block.get(block_type, {})
    
    # Text-containing blocks
    if 'rich_text' in block_data:
        for text_obj in block_data['rich_text']:
            text_content += text_obj.get('plain_text', '')
    
    # Special handling for different block types
    if block_type == 'heading_1':
        text_content = f"\n# {text_content}\n"
    elif block_type == 'heading_2':
        text_content = f"\n## {text_content}\n"
    elif block_type == 'heading_3':
        text_content = f"\n### {text_content}\n"
    elif block_type == 'paragraph':
        text_content = f"{text_content}\n"
    elif block_type == 'bulleted_list_item':
        text_content = f"• {text_content}\n"
    elif block_type == 'numbered_list_item':
        text_content = f"1. {text_content}\n"
    elif block_type == 'to_do':
        checkbox = "☑" if block_data.get('checked') else "☐"
        text_content = f"{checkbox} {text_content}\n"
    elif block_type == 'quote':
        text_content = f"> {text_content}\n"
    elif block_type == 'code':
        language = block_data.get('language', '')
        text_content = f"```{language}\n{text_content}\n```\n"
    elif block_type == 'divider':
        text_content = "\n---\n"
    
    return text_content

def get_page_content(page_id):
    """Get the full content of a Notion page"""
    client = Client(auth=notion_token)
    
    try:
        # Get page metadata
        page = client.pages.retrieve(page_id)
        title = extract_title(page)
        
        # Get page blocks (content)
        blocks_response = client.blocks.children.list(block_id=page_id, page_size=100)
        
        content = f"# {title}\n\n"
        
        # Process each block
        for block in blocks_response.get('results', []):
            block_text = extract_text_from_block(block)
            content += block_text
            
            # Handle nested blocks (like indented lists)
            if block.get('has_children'):
                try:
                    children_response = client.blocks.children.list(block_id=block['id'])
                    for child_block in children_response.get('results', []):
                        child_text = extract_text_from_block(child_block)
                        # Indent child content
                        indented_text = '\n'.join(['  ' + line for line in child_text.split('\n')])
                        content += indented_text
                except:
                    pass  # Skip if can't get children
        
        # Clean up extra whitespace
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        content = content.strip()
        
        return {
            'title': title,
            'content': content,
            'word_count': len(content.split()),
            'char_count': len(content),
            'page_id': page_id,
            'url': page.get('url', ''),
            'last_edited': page.get('last_edited_time', '')
        }
        
    except Exception as e:
        print(f"Error extracting content: {str(e)}")
        return None

def display_pages(pages):
    """Display pages for selection"""
    if not pages:
        print(" No accessible pages found!")
        print("\n💡 Share pages with your 'xyz_abc' integration first.")
        return False
    
    print(f" Found {len(pages)} accessible page(s):")
    print("=" * 60)
    
    for i, page in enumerate(pages, 1):
        print(f"{i:2d}. {page['title']}")
        print(f"    Last edited: {page['last_edited_time'][:10] if page['last_edited_time'] else 'Unknown'}")
        print("-" * 60)
    
    return True

def save_content_to_file(content_data, filename=None):
    """Save extracted content to a text file"""
    if not filename:
        # Create filename from title
        safe_title = re.sub(r'[^\w\s-]', '', content_data['title'])
        safe_title = re.sub(r'[-\s]+', '_', safe_title)
        filename = f"notion_content_{safe_title}.txt"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"Title: {content_data['title']}\n")
            f.write(f"Last Edited: {content_data['last_edited']}\n")
            f.write(f"Word Count: {content_data['word_count']}\n")
            f.write(f"Character Count: {content_data['char_count']}\n")
            f.write("=" * 60 + "\n\n")
            f.write(content_data['content'])
        
        print(f" Content saved to: {filename}")
        return filename
    except Exception as e:
        print(f" Error saving file: {str(e)}")
        return None

def main():
    print(" Notion Content Extractor for AI Chat")
    print("Integration: xyz_abc")
    print("=" * 60)
    
    print("🔍 Fetching accessible pages...")
    pages = get_accessible_pages()
    
    if not display_pages(pages):
        return
    
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
                    content_data = get_page_content(page['id'])
                    
                    if content_data:
                        all_content += f"\n{'='*80}\n"
                        all_content += f"PAGE: {content_data['title']}\n"
                        all_content += f"{'='*80}\n"
                        all_content += content_data['content'] + "\n\n"
                
                if all_content:
                    # Save combined content
                    with open('all_notion_pages.txt', 'w', encoding='utf-8') as f:
                        f.write(all_content)
                    
                    print(f"\n All pages extracted!")
                    print(f" Total content length: {len(all_content)} characters")
                    print(f" Saved to: all_notion_pages.txt")
                    print(f"\n Content ready for Google AI API!")
                    
                    # Display preview
                    preview = all_content[:500] + "..." if len(all_content) > 500 else all_content
                    print(f"\n Preview:\n{preview}")
                
                return
            
            page_num = int(choice)
            if 1 <= page_num <= len(pages):
                selected_page = pages[page_num - 1]
                break
            else:
                print(f" Please enter a number between 1 and {len(pages)}")
                
        except ValueError:
            print(" Please enter a valid number, 'all', or 'q' to quit")
    
    # Extract content from selected page
    print(f"\n Extracting content from: {selected_page['title']}")
    print("=" * 60)
    
    content_data = get_page_content(selected_page['id'])
    
    if content_data:
        print(" Content extracted successfully!")
        print(f" Stats:")
        print(f"   • Words: {content_data['word_count']}")
        print(f"   • Characters: {content_data['char_count']}")
        
        # Save to file
        filename = save_content_to_file(content_data)
        
        print(f"\n📋 Content ready for Google AI API!")
        
        # Display preview
        preview = content_data['content'][:500] + "..." if len(content_data['content']) > 500 else content_data['content']
        print(f"\n📖 Preview:\n{preview}")
        
        # Return content for API use
        return content_data['content']
    
    else:
        print(" Failed to extract content")
        return None

if __name__ == '__main__':
    extracted_content = main()