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
# 2. Fetch Unique News Title from News18 RSS Feed
# ---------------------------------------------------------
def get_unique_news18_story():
    rss_urls = [
        "https://www.news18.com/common-html/v1/eng/ssr/rss/viral.xml",
        "https://www.news18.com/rss/viral.xml"
    ]
    
    entries = []
    for url in rss_urls:
        feed = feedparser.parse(url)
        if feed.entries:
            entries = feed.entries
            break

    if entries:
        selected_entry = random.choice(entries[:10])
        title = selected_entry.title
        summary_raw = getattr(selected_entry, 'summary', getattr(selected_entry, 'description', ''))
        
        soup = BeautifulSoup(summary_raw, 'html.parser')
        clean_summary = soup.get_text(strip=True)
        
        return {
            "title": title,
            "summary": clean_summary if clean_summary else title
        }
    else:
        topics = [
            "Viral Social Media Trend Takes Internet By Storm",
            "Bizarre Internet Meme Causes Wild Online Reactions",
            "Shocking Viral Video Leaves Social Media Users Divided"
        ]
        chosen = random.choice(topics)
        return {"title": chosen, "summary": chosen}

news_data = get_unique_news18_story()
print(f"Fetched Unique News Topic: {news_data['title']}")

# ---------------------------------------------------------
# 3. Gemini API Rewrite Prompt Setup
# ---------------------------------------------------------
client = genai.Client(api_key=GEMINI_API_KEY)

prompt = f"""
You are an expert viral news reporter and SEO blog writer.
Rewrite and expand upon the following trending viral news story into a brand-new, original blog article:

News Title: {news_data['title']}
News Context: {news_data['summary']}

Instructions:
1. LANGUAGE: Write strictly in fluent, natural ENGLISH.
2. WORD COUNT: Write a complete story between 400 and 600 WORDS.
3. STRUCTURE: Include an engaging title, background context, social media reaction, and conclusion.
4. FORMATTING: Use clean HTML tags like <h2>, <h3>, and <p>. Do NOT use markdown block ticks.
5. NO PROMOTIONAL LINKS: Do not add external URLs.

Return strictly valid JSON with these exact keys:
1. "title": An engaging, catchy headline (50-70 characters).
2. "content": The HTML formatted article body (400-600 words).
3. "image_keyword": A 1-2 word relevant English keyword for a contextual image.
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
image_keyword = data.get('image_keyword', 'news').strip().lower()

# ---------------------------------------------------------
# 5. Dynamic Featured Image Stream (Picsum CDN)
# ---------------------------------------------------------
random_seed = random.randint(10000, 99999)
featured_image_url = f"https://picsum.photos/seed/{random_seed}/800/450"

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
    print(f"Successfully posted new topic: {post_title}")
else:
    print(f"Error publishing post: {res.status_code} - {res.text}")
