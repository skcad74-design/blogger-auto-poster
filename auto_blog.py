import os
import json
import requests
import random
import time
import sys
import subprocess
import base64

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
# 2. Fetch Story & Download Real Original Image
# ---------------------------------------------------------
def get_news18_exact_story_and_image():
    url = "https://www.news18.com/viral/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-original')
            alt = img.get('alt', '').strip()
            
            if src and alt and len(alt) > 25 and ('images' in src or 'news18' in src or 'imengine' in src):
                if not src.startswith('http'):
                    src = "https:" + src if src.startswith('//') else "https://www.news18.com" + src
                
                img_res = requests.get(src, headers=headers, timeout=10)
                if img_res.status_code == 200:
                    b64_img = base64.b64encode(img_res.content).decode('utf-8')
                    mime_type = img_res.headers.get('Content-Type', 'image/jpeg')
                    data_uri = f"data:{mime_type};base64,{b64_img}"
                    return {"title": alt, "image_data_uri": data_uri}

    except Exception as e:
        print(f"Error fetching exact photo: {e}")

    return {
        "title": "Delhi Metro Viral Phone Stunt Captures Millions",
        "image_data_uri": "https://picsum.photos/800/450"
    }

news_data = get_news18_exact_story_and_image()
print(f"Fetched Exact Article Title: {news_data['title']}")

# ---------------------------------------------------------
# 3. Gemini Content Rewrite Setup
# ---------------------------------------------------------
client = genai.Client(api_key=GEMINI_API_KEY)

prompt = f"""
You are an expert viral news reporter and SEO blog writer.
Rewrite this viral news story into a compelling blog post:
News Headline: {news_data['title']}

Instructions:
1. LANGUAGE: Write in natural, fluent ENGLISH.
2. WORD COUNT: 400 to 600 words.
3. FORMATTING: Return clean HTML content using <h2>, <h3>, and <p> tags.
4. DO NOT use markdown code blocks like ```html.

Return JSON with exact keys:
"title": Engaging SEO Title.
"content": Complete HTML blog text.
"""

# Valid active models
MODELS_TO_TRY = ['gemini-3.6-flash', 'gemini-3.5-flash-lite']
response = None

for model_name in MODELS_TO_TRY:
    print(f"Attempting content generation with model: {model_name}")
    for attempt in range(5):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            print(f"Successfully generated using {model_name}!")
            break
        except Exception as e:
            error_msg = str(e)
            print(f"Attempt {attempt + 1} with {model_name} failed: {error_msg}")
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "503" in error_msg:
                print("Quota limit or server busy. Retrying after 45 seconds...")
                time.sleep(45)
            elif "404" in error_msg or "NOT_FOUND" in error_msg:
                print(f"Model {model_name} not available. Moving to next fallback model...")
                break
            else:
                time.sleep(10)
                
    if response:
        break

if not response:
    raise Exception("Failed to generate content. Quota limit exhausted for active models.")

data = json.loads(response.text)
post_title = data['title']
post_content = data['content']

image_html = f'''
<div style="text-align: center; margin-bottom: 25px;">
    <img src="{news_data['image_data_uri']}" alt="{post_title}" style="width:100%; max-width:850px; height:auto; border-radius:12px; box-shadow: 0 4px 15px rgba(0,0,0,0.15); object-fit: cover;"/>
</div>
'''

final_blog_content = image_html + post_content

# ---------------------------------------------------------
# 4. Blogger OAuth Token Refresh
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
    raise Exception(f"OAuth failed: {token_res.text}")

access_token = token_json['access_token']

# ---------------------------------------------------------
# 5. Publish Article to Blogger
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
    print(f"Successfully posted exact image story: {post_title}")
else:
    print(f"Publishing failed: {res.status_code} - {res.text}")
