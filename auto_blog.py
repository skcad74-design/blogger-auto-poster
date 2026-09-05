import os
import json
import time
import sys
import subprocess
import re

REQUIRED_PACKAGES = {
    "feedparser": "feedparser",
    "bs4": "beautifulsoup4",
    "requests": "requests"
}

for module_name, package_name in REQUIRED_PACKAGES.items():
    try:
        __import__(module_name)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])

import feedparser
import requests
from bs4 import BeautifulSoup

try:
    from google import genai
    from google.genai import types
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "google-genai"])
    from google import genai
    from google.genai import types


# =========================================================
# 1. ENVIRONMENT VARIABLES
# =========================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
BLOG_ID = os.environ.get("BLOGGER_BLOG_ID")
CLIENT_ID = os.environ.get("BLOGGER_CLIENT_ID")
CLIENT_SECRET = os.environ.get("BLOGGER_CLIENT_SECRET")
REFRESH_TOKEN = os.environ.get("BLOGGER_REFRESH_TOKEN")


# =========================================================
# 2. SETTINGS
# =========================================================

NEWS_RSS_URL = "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 20

MODELS_TO_TRY = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
]


# =========================================================
# 3. FETCH RECENT NEWS & DIRECT IMAGE LINK
# =========================================================

def get_latest_recent_news():
    print("Fetching latest top breaking news...")
    feed = feedparser.parse(NEWS_RSS_URL)

    if not feed.entries:
        raise Exception("Could not fetch RSS feed from Times of India.")

    latest_item = feed.entries[0]
    story_title = latest_item.title
    story_url = latest_item.link
    
    print(f"\nFetched Title: {story_title}")
    print(f"URL: {story_url}")

    image_url = None
    article_text = ""

    try:
        art_res = requests.get(story_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        soup = BeautifulSoup(art_res.text, "html.parser")

        # Extract Meta Direct Image (og:image)
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            image_url = og_img["content"]

        paragraphs = soup.find_all("p")
        text_list = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
        article_text = "\n\n".join(text_list[:15])

    except Exception as e:
        print(f"Detail page extraction note: {e}")

    if not article_text:
        article_text = latest_item.get("summary", story_title)

    return {
        "title": story_title,
        "url": story_url,
        "image_url": image_url,
        "article_text": article_text
    }


news_data = get_latest_recent_news()


# =========================================================
# 4. GEMINI CLIENT & REWRITE
# =========================================================

client = genai.Client(api_key=GEMINI_API_KEY)

prompt = f"""
You are an expert news editor and SEO blog writer.
Rewrite this RECENT TOP NEWS story into a comprehensive English blog post.

SOURCE HEADLINE: {news_data['title']}
SOURCE URL: {news_data['url']}
SOURCE DETAILS: {news_data['article_text']}

Requirements:
1. Natural, engaging English suitable for top-ranking SEO articles.
2. Word count: 400 - 600 words.
3. Clean HTML content inside "content" key (use <h2>, <h3>, <p>, <ul>, <li>).
4. Do NOT use markdown code fences.
5. End with source attribution:
   <p><strong>Source:</strong> <a href="{news_data['url']}" target="_blank" rel="nofollow noopener">Times of India</a></p>

Return ONLY valid JSON with keys "title" and "content".
"""

response = None
for model_name in MODELS_TO_TRY:
    print(f"Generating content with model: {model_name}")
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7
                )
            )
            print(f"Success with {model_name}!")
            break
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(15)
    if response:
        break

if not response:
    raise RuntimeError("Content generation failed.")


# =========================================================
# 5. PARSE JSON & BUILD HTML WITH DIRECT IMAGE URL
# =========================================================

raw_text = response.text.strip()
raw_text = re.sub(r"^```json\s*", "", raw_text, flags=re.IGNORECASE)
raw_text = re.sub(r"\s*```$", "", raw_text)

data = json.loads(raw_text)
post_title = data.get("title", news_data["title"])
post_content = data.get("content", "")

# Clean direct image HTML embed for Blogger
image_html = ""
if news_data["image_url"]:
    image_html = f'''
<div style="text-align:center; margin-bottom:25px;">
    <img src="{news_data["image_url"]}" alt="{post_title}" style="width:100%; max-width:850px; height:auto; border-radius:12px; box-shadow:0 4px 15px rgba(0,0,0,0.15);"/>
</div>
'''

final_blog_content = image_html + post_content


# =========================================================
# 6. PUBLISH TO BLOGGER
# =========================================================

TOKEN_URL = "https://oauth2.googleapis.com/token"
token_data = {
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "refresh_token": REFRESH_TOKEN,
    "grant_type": "refresh_token"
}

token_res = requests.post(TOKEN_URL, data=token_data, timeout=REQUEST_TIMEOUT)
access_token = token_res.json().get("access_token")

if not access_token:
    raise RuntimeError(f"OAuth failed: {token_res.text}")

BLOGGER_URL = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts/"
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

payload = {
    "kind": "blogger#post",
    "title": post_title,
    "content": final_blog_content
}

print("\nPublishing to Blogger...")
res = requests.post(BLOGGER_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)

if res.status_code in (200, 201):
    print(f"SUCCESSFULLY POSTED: {post_title}")
else:
    raise RuntimeError(f"Publishing failed: {res.status_code} - {res.text}")
