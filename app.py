import os
import json
import hashlib
import re
import ipaddress
from datetime import datetime
from flask import Flask, render_template_string, redirect, url_for, send_from_directory, abort, request
import requests

app = Flask(__name__)

# List of known crawler User-Agents to block
BLOCKED_USER_AGENTS = [
    'CCBot', 'GPTBot', 'ChatGPT-User', 'Google-Extended', 'anthropic-ai',
    'Claude-Web', 'Omgilibot', 'FacebookBot', 'Bytespider', 'crawler',
    'spider', 'bot', 'scraper', 'archive.org', 'Googlebot', 'Bingbot',
    'Slurp', 'DuckDuckBot', 'Baiduspider', 'YandexBot', 'Sogou'
]

# Meta IP ranges (example ranges - you should regularly update these)
META_IP_RANGES = [
    '157.240.0.0/16',
    '69.63.176.0/20',
    '66.220.144.0/20',
    '66.220.144.0/21',
    '69.63.184.0/21',
    '69.63.176.0/21',
    '74.119.76.0/22',
]

def is_meta_ip(ip):
    """Check if an IP is in Meta's ranges"""
    try:
        ip_addr = ipaddress.ip_address(ip)
        return any(ip_addr in ipaddress.ip_network(range) for range in META_IP_RANGES)
    except ValueError:
        return False

@app.before_request
def block_crawlers():
    """Block known crawlers and Meta IPs"""
    # Check User-Agent
    user_agent = request.headers.get('User-Agent', '').lower()
    if any(bot.lower() in user_agent for bot in BLOCKED_USER_AGENTS):
        abort(403, "Crawlers not allowed")
    
    # Check IP
    if is_meta_ip(request.remote_addr):
        abort(403, "Access denied")

# Security headers
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; script-src 'unsafe-inline'"
    response.headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    response.headers['X-Crawler'] = 'no-crawl'
    response.headers['CommonCrawl'] = 'no-crawl'
    return response

# Ensure cache directory exists
CACHE_DIR = '/cache'
os.makedirs(CACHE_DIR, exist_ok=True)

def get_cache_path(path):
    """Generate a unique cache file path for the given URL path"""
    # Sanitize path to prevent directory traversal
    safe_path = re.sub(r'[^a-zA-Z0-9-_.]', '', path)
    hash_object = hashlib.md5(safe_path.encode())
    return os.path.join(CACHE_DIR, f"{hash_object.hexdigest()}.json")

def get_cached_content(path):
    """Retrieve cached content if it exists"""
    cache_path = get_cache_path(path)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                cached_data = json.load(f)
                return cached_data['content']
        except (json.JSONDecodeError, KeyError, ValueError, IOError):
            pass
    return None

def cache_content(path, content):
    """Save content to cache"""
    try:
        cache_path = get_cache_path(path)
        cache_data = {
            'content': content,
            'timestamp': datetime.now().isoformat()
        }
        with open(cache_path, 'w') as f:
            json.dump(cache_data, f)
    except IOError:
        app.logger.error(f"Failed to write to cache file: {cache_path}")

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
    {{ content | safe }}
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

@app.route('/robots.txt')
def robots():
    """Serve robots.txt file"""
    return send_from_directory('.', 'robots.txt')

@app.route('/')
def index():
    """Serve the index.html file"""
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def dynamic_page(path):
    """Handle all routes by generating dynamic content"""
    # Redirect non-.html paths
    if not path.endswith('.html'):
        return redirect(f'/{path}.html')
    
    # Remove .html for processing
    base_path = path[:-5] if path.endswith('.html') else path
    
    # Validate path
    if not re.match(r'^[a-zA-Z0-9-_/]+$', base_path):
        abort(400, description="Invalid path")
    
    # Clean up path for title
    title = base_path.replace('-', ' ').replace('/', ' - ').title()
    
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
