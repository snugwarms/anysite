import os
import json
import hashlib
from datetime import datetime, timedelta
from flask import Flask, render_template_string
import requests

app = Flask(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), 'cache')
CACHE_DURATION = timedelta(hours=24)  # Cache content for 24 hours

def get_cache_path(path):
    """Generate a unique cache file path for the given URL path"""
    hash_object = hashlib.md5(path.encode())
    return os.path.join(CACHE_DIR, f"{hash_object.hexdigest()}.json")

def get_cached_content(path):
    """Retrieve cached content if it exists and is not expired"""
    cache_path = get_cache_path(path)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                cached_data = json.load(f)
                cached_time = datetime.fromisoformat(cached_data['timestamp'])
                if datetime.now() - cached_time < CACHE_DURATION:
                    return cached_data['content']
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
    return None

def cache_content(path, content):
    """Save content to cache"""
    cache_path = get_cache_path(path)
    cache_data = {
        'content': content,
        'timestamp': datetime.now().isoformat()
    }
    with open(cache_path, 'w') as f:
        json.dump(cache_data, f)

# Environment variables with defaults
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', 'none')
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'google/gemini-2.0-flash-001')
DEFAULT_PROMPT = os.getenv('PROMPT_TEMPLATE', '''Generate a webpage about "{path}". 
The content should be informative and engaging.
Return only the HTML content for the body (no <html>, <head>, or <body> tags).
Use semantic HTML elements and include proper headings.''')

# Base HTML template
BASE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
    </style>
</head>
<body>
    {{ content | safe }}
</body>
</html>
"""

def generate_content(path):
    """Generate content for the requested path using OpenRouter API"""
    prompt = DEFAULT_PROMPT.format(path=path)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://localhost:9999",  # Required for OpenRouter API
        "Content-Type": "application/json"
    }

    data = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        return content
    except Exception as e:
        return f"<h1>Error</h1><p>Failed to generate content: {str(e)}</p>"

@app.route('/', defaults={'path': 'home'})
@app.route('/<path:path>')
def dynamic_page(path):
    """Handle all routes by generating dynamic content"""
    # Clean up path for title
    title = path.replace('-', ' ').replace('/', ' - ').title()
    
    # Check cache first
    cached_content = get_cached_content(path)
    if cached_content:
        return render_template_string(BASE_TEMPLATE, title=title, content=cached_content)
    
    # Generate new content if not cached
    content = generate_content(path)
    
    # Cache the new content
    cache_content(path, content)
    
    # Render with base template
    return render_template_string(BASE_TEMPLATE, title=title, content=content)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
