import os
import json
import requests
import random
import time
import sys
import subprocess

# Auto-install dependencies if missing
try:
    import feedparser
    from bs4 import BeautifulSoup
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "feedparser", "beautifulsoup4"])
    import feedparser
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
# 2. Fetch Story Title & Scrap Original Image URL
# ---------------------------------------------------------
def get_news18_story_with_image():
    url = "https://www.news18.com/viral/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        articles = []
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-original')
            alt = img.get('alt', '').strip()
            
            if src and alt and len(alt) > 20 and ('images' in src or 'news18' in src or 'imengine' in src):
                if not src.startswith('http'):
                    src = "https:" + src if src.startswith('//') else "https://www.news18.com" + src
                articles.append({'title': alt, 'original_image': src})
        
        if articles:
            return random.choice(articles[:8])
            
    except Exception as e:
        print(f"Scraping error: {e}")

    return {
        "title": "Delhi man phone stunt in metro gets millions of views",
        "original_image": ""
    }

news_data = get_news18_story_with_image()
print(f"Fetched Story: {news_data['title']}")

# ---------------------------------------------------------
# 3. Gemini API Prompt Setup
# ---------------------------------------------------------
client = genai.Client(api_key=GEMINI_API_KEY)

prompt = f"""
You are an expert news journalist. Rewrite this viral story:
Title: {news_data['title']}

Rules:
1. Write in clear, engaging English (400 to 600 words).
2. Format using HTML tags (<h2>, <h3>, <p>).
3. Create a detailed visual prompt describing the EXACT news scene to recreate the same image.

Return strictly valid JSON with keys:
1. "title": Catchy title for the post.
2. "content": HTML formatted article text.
3. "image_prompt": A highly detailed descriptive prompt matching this news photo (e.g. "a young man dancing in Delhi metro with phone attached to glass window").
"""

# ---------------------------------------------------------
# 4. Generate Content via Gemini
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
image_prompt = data.get('image_prompt', news_data['title'])

# ---------------------------------------------------------
# 5. Image Engine: Bypass Hotlink using Proxy or AI Re-creation
# ---------------------------------------------------------
if news_data['original_image']:
    # Bypass News18 Hotlink protection using wsrv.nl CDN Proxy for EXACT photo
    raw_img = news_data['original_image']
    featured_image_url = f"https://wsrv.nl/?url={requests.utils.quote(raw_img)}&w=800&output=webp"
else:
    # Generate identical context photo using Pollinations AI
    clean_prompt = requests.utils.quote(image_prompt)
    featured_image_url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=800&height=450&nologo=true"

image_html = f'''
<div style="text-align: center; margin-bottom: 25px;">
    <img src="{featured_image_url}" alt="{post_title}" style="width:100%; max-width:850px; height:auto; border-radius:12px; box-shadow: 0 4px 15px rgba(0,0,0,0.15); object-fit: cover;"/>
</div>
'''

final_blog_content = image_html + post_content

# ---------------------------------------------------------
# 6. Blogger OAuth Access Token Refresh
# ---------------------------------------------------------
token_url = "https://oauth2.googleapis.com/token"
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
blogger_url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts/"
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
