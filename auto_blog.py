import os
import json
import requests
import random
import time
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
# 2. Fetch Latest News from News18 RSS Feed
# ---------------------------------------------------------
def get_latest_news18_story():
    # News18 Viral RSS Feed URL
    rss_url = "https://www.news18.com/common-html/v1/eng/ssr/rss/viral.xml"
    feed = feedparser.parse(rss_url)
    
    if not feed.entries:
        # Fallback RSS feed if main one fails
        rss_url = "https://www.news18.com/rss/viral.xml"
        feed = feedparser.parse(rss_url)

    if feed.entries:
        # Pick a random news item from the top 5 latest entries to avoid repetitive posts
        selected_entry = random.choice(feed.entries[:5])
        
        title = selected_entry.title
        summary_raw = getattr(selected_entry, 'summary', getattr(selected_entry, 'description', ''))
        
        # Clean HTML tags from summary
        soup = BeautifulSoup(summary_raw, 'html.parser')
        clean_summary = soup.get_text(strip=True)
        
        return {
            "title": title,
            "summary": clean_summary if clean_summary else title
        }
    else:
        # Default safety fallback if RSS feed is unreachable
        return {
            "title": "Trending Viral News Story",
            "summary": "Interesting viral story happening around the world on social media."
        }

news_data = get_latest_news18_story()
print(f"Fetched News18 Topic: {news_data['title']}")

# ---------------------------------------------------------
# 3. Gemini API Initialization & Prompt
# ---------------------------------------------------------
client = genai.Client(api_key=GEMINI_API_KEY)

prompt = f"""
You are a professional news journalist and blog writer.
Rewrite and expand upon the following trending news story from News18 Viral into a captivating, viral blog article:

News Headline: {news_data['title']}
News Summary: {news_data['summary']}

Rules:
1. LANGUAGE: Write strictly in fluent, high-quality ENGLISH.
2. WORD COUNT: Keep the word count strictly UP TO 600 WORDS (between 400 and 600 words max).
3. NO ADS OR EXTERNAL LINKS: Do NOT include any promotional text, website URLs, or affiliate links in the text content.
4. FORMAT: Use proper HTML structure with <h2>, <h3> headings, an engaging opening, full background story, public reaction/context, and a quick wrap-up.

Return your response strictly in JSON format with these exact keys:
1. "title": An engaging, click-worthy headline in English (50-70 characters).
2. "content": The HTML formatted blog post (under 600 words).
3. "image_keyword": A 1-2 word simple English keyword related to this specific news story for dynamic image matching.
"""

# ---------------------------------------------------------
# 4. API Execution with Retry (gemini-3.6-flash)
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
image_keyword = data.get('image_keyword', 'viral news').strip().lower()

# ---------------------------------------------------------
# 5. Dynamic Featured Image Stream
# ---------------------------------------------------------
keyword_clean = requests.utils.quote(image_keyword)
random_sig = random.randint(1000, 9999)

featured_image_url = f"https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=1200&q=80&sig={random_sig}&{keyword_clean}"

image_html = f'''
<div style="text-align: center; margin-bottom: 25px;">
    <img src="{featured_image_url}" alt="{post_title}" style="width:100%; max-width:850px; height:auto; border-radius:12px; box-shadow: 0 4px 15px rgba(0,0,0,0.15); object-fit: cover;"/>
</div>
'''

final_blog_content = image_html + post_content

print(f"Generated Title: {post_title}")
print(f"Image Keywords: {image_keyword}")

# ---------------------------------------------------------
# 6. Blogger OAuth Token Refresh
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
# 7. Publish to Blogger
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
    print("News article successfully published to Blogger!")
else:
    print(f"Error publishing post: {res.status_code} - {res.text}")
