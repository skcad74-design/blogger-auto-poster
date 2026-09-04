import os
import json
import requests
import random
import time
import sys
import subprocess

# Auto-install dependencies if missing
try:
    from bs4 import BeautifulSoup
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "beautifulsoup4"])
    from bs4 import BeautifulSoup

from google import genai
from google.genai import types

# ---------------------------------------------------------
# 1. Environment Variables Loading
# ---------------------------------------------------------
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
BLOG_ID = os.environ.get('BLOGGER_BLOG_ID')
CLIENT_ID = os.environ.get('BLOGGER_CLIENT_ID')
CLIENT_SECRET = os.environ.get('BLOGGER_CLIENT_SECRET')
REFRESH_TOKEN = os.environ.get('BLOGGER_REFRESH_TOKEN')

# ---------------------------------------------------------
# 2. Scrape Real Headline & Original Image from News18 Viral
# ---------------------------------------------------------
def fetch_news18_viral_data():
    url = "https://www.news18.com/viral/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        articles = []
        
        # Extract article blocks with images and links
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-original')
            alt = img.get('alt', '').strip()
            
            # Filter valid news hero images
            if src and alt and len(alt) > 20 and ('images' in src or 'news18' in src or 'imengine' in src):
                if not src.startswith('http'):
                    src = "https:" + src if src.startswith('//') else "https://www.news18.com" + src
                articles.append({'title': alt, 'image': src})
        
        if articles:
            # Randomly select 1 trending news item from the top scraped items
            selected = random.choice(articles[:6])
            return selected
            
    except Exception as e:
        print(f"Scraping error: {e}")

    # Fallback default if scraping gets blocked
    return {
        "title": "American Woman Calls Out AI Video Painting India As Filthy, Says 'This Is Not What India Looks Like'",
        "image": "https://images.news18.com/ibnlive/uploads/2024/09/viral-image.jpg"
    }

news_data = fetch_news18_viral_data()
print(f"Scraped Headline: {news_data['title']}")
print(f"Original Article Image: {news_data['image']}")

# ---------------------------------------------------------
# 3. Gemini API Rewrite Prompt Setup
# ---------------------------------------------------------
client = genai.Client(api_key=GEMINI_API_KEY)

prompt = f"""
You are an expert viral news reporter and SEO blog generator.
Rewrite the following trending viral news headline from News18 into a compelling, fresh, and detailed blog article:

News Headline: {news_data['title']}

Instructions:
1. LANGUAGE: Write strictly in fluent, natural ENGLISH.
2. WORD COUNT: Write a complete story within 400 to 600 WORDS.
3. STRUCTURE: Include an engaging intro, context/background story, internet reactions, and a concluding thought.
4. FORMATTING: Use clean HTML styling tags like <h2>, <h3>, and paragraph tags <p>. Do not include markdown codeblock tags like ```html.
5. NO LINKS: Do not add any promotional text or external hyperlinks.

Return strictly valid JSON with these keys:
1. "title": An catchy, engaging article title (50-70 characters).
2. "content": The HTML formatted article body (under 600 words).
"""

# ---------------------------------------------------------
# 4. Generate Content via Gemini API (gemini-3.6-flash)
# ---------------------------------------------------------
MODEL_NAME = 'gemini-3.6-flash'
response = None
max_retries = 3

for attempt in range(max_retries):
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            ),
        )
        break
    except Exception as e:
        print(f"Attempt {attempt + 1} failed: {e}")
        if attempt < max_retries - 1:
            time.sleep(10)
        else:
            raise e

data = json.loads(response.text)
post_title = data['title']
post_content = data['content']

# ---------------------------------------------------------
# 5. Embed the Original News Photo into Article Content
# ---------------------------------------------------------
original_image_url = news_data['image']

image_html = f'''
<div style="text-align: center; margin-bottom: 25px;">
    <img src="{original_image_url}" alt="{post_title}" style="width:100%; max-width:850px; height:auto; border-radius:12px; box-shadow: 0 4px 15px rgba(0,0,0,0.15); object-fit: cover;"/>
</div>
'''

final_blog_content = image_html + post_content

# ---------------------------------------------------------
# 6. Blogger OAuth Access Token Refresh
# ---------------------------------------------------------
token_url = "[https://oauth2.googleapis.com/token](https://oauth2.googleapis.com/token)"
token_data = {
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET,
    'refresh_token': REFRESH_TOKEN,
    'grant_type': 'refresh_token'
}

token_res = requests.post(token_url, data=token_data)
token_json = token_res.json()

if 'access_token' not in token_json:
    raise Exception(f"Failed to refresh access token: {token_res.text}")

access_token = token_json['access_token']

# ---------------------------------------------------------
# 7. Publish Article to Blogger
# ---------------------------------------------------------
blogger_url = f"[https://www.googleapis.com/blogger/v3/blogs/](https://www.googleapis.com/blogger/v3/blogs/){BLOG_ID}/posts/"
headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
}
payload = {
    'kind': 'blogger#post',
    'title': post_title,
    'content': final_blog_content
}

res = requests.post(blogger_url, headers=headers, json=payload)

if res.status_code == 200:
    print(f"Successfully posted: {post_title}")
else:
    print(f"Error publishing post: {res.status_code} - {res.text}")
