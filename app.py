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

# Load prompt from file
PROMPT_FILE = os.path.join(os.path.dirname(__file__), 'prompt.txt')
with open(PROMPT_FILE, 'r') as f:
    DEFAULT_PROMPT = f.read().strip()

# Environment variables with defaults
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', 'none')
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'google/gemini-2.0-flash-001')

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
    <script>
        console.log('=== PROMPT ===');
        console.log(`{{ debug_prompt | safe }}`);
        console.log('=== LLM RESPONSE ===');
        console.log(`{{ debug_response | safe }}`);
    </script>
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
        
        # Check for rate limiting
        if response.status_code == 429:
            error_msg = "<h1>Error</h1><p>Rate limited by OpenRouter API. Please try again in a few moments.</p>"
            return prompt, error_msg
            
        response.raise_for_status()
        response_json = response.json()
        
        # Debug logging
        print("API Response:", response_json)
        
        if 'choices' not in response_json or not response_json['choices']:
            error_msg = f"<h1>Error</h1><p>Invalid API response structure: {response_json}</p>"
            return prompt, error_msg
            
        content = response_json['choices'][0]['message']['content']
        
        # Filter out code block markers and unwanted patterns
        content = content.replace('```html', '').replace('```', '')
        
        # Remove any lines containing backtick patterns
        cleaned_lines = []
        for line in content.split('\n'):
            if '`);' not in line and '`' not in line:
                cleaned_lines.append(line)
        content = '\n'.join(cleaned_lines).strip()
        
        return prompt, content
    except requests.exceptions.RequestException as e:
        error_msg = f"<h1>Error</h1><p>API request failed: {str(e)}</p>"
        return prompt, error_msg
    except Exception as e:
        error_msg = f"<h1>Error</h1><p>Failed to generate content: {str(e)}</p>"
        return prompt, error_msg

@app.route('/', defaults={'path': 'home'})
@app.route('/<path:path>')
def dynamic_page(path):
    """Handle all routes by generating dynamic content"""
    # Clean up path for title
    title = path.replace('-', ' ').replace('/', ' - ').title()
    
    # Check cache first
    cached_content = get_cached_content(path)
    if cached_content:
        return render_template_string(
            BASE_TEMPLATE,
            title=title,
            content=cached_content,
            debug_prompt="(Cached) Original prompt not available",
            debug_response="(Cached) Original response not available"
        )
    
    # Generate new content if not cached
    prompt, content = generate_content(path)
    
    # Cache the new content
    cache_content(path, content)
    
    # Escape backticks and backslashes for JavaScript template literal
    safe_prompt = prompt.replace('\\', '\\\\').replace('`', '\\`')
    safe_content = content.replace('\\', '\\\\').replace('`', '\\`')
    
    # Render with base template and debug info
    return render_template_string(
        BASE_TEMPLATE,
        title=title,
        content=content,
        debug_prompt=safe_prompt,
        debug_response=safe_content
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
