import os
import json
import time
import sys
import subprocess
import base64
import re
from urllib.parse import urljoin

import requests

# =========================================================
# 1. AUTO INSTALL DEPENDENCIES
# =========================================================

REQUIRED_PACKAGES = {
    "feedparser": "feedparser",
    "bs4": "beautifulsoup4",
}

for module_name, package_name in REQUIRED_PACKAGES.items():
    try:
        __import__(module_name)
    except ImportError:
        print(f"Installing {package_name}...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", package_name]
        )

import feedparser
from bs4 import BeautifulSoup

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Installing google-genai...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-U", "google-genai"]
    )
    from google import genai
    from google.genai import types


# =========================================================
# 2. ENVIRONMENT VARIABLES
# =========================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
BLOG_ID = os.environ.get("BLOGGER_BLOG_ID")
CLIENT_ID = os.environ.get("BLOGGER_CLIENT_ID")
CLIENT_SECRET = os.environ.get("BLOGGER_CLIENT_SECRET")
REFRESH_TOKEN = os.environ.get("BLOGGER_REFRESH_TOKEN")

missing = []
if not GEMINI_API_KEY: missing.append("GEMINI_API_KEY")
if not BLOG_ID: missing.append("BLOGGER_BLOG_ID")
if not CLIENT_ID: missing.append("BLOGGER_CLIENT_ID")
if not CLIENT_SECRET: missing.append("BLOGGER_CLIENT_SECRET")
if not REFRESH_TOKEN: missing.append("BLOGGER_REFRESH_TOKEN")

if missing:
    raise RuntimeError("Missing environment variables:\n- " + "\n- ".join(missing))


# =========================================================
# 3. SETTINGS & MODEL LIST
# =========================================================

# Times of India Top Latest News RSS Feed
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
# 4. DOWNLOAD IMAGE & CONVERT TO DATA URI
# =========================================================

def download_image_as_data_uri(image_url):
    try:
        if not image_url:
            return None

        response = requests.get(image_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "image/jpeg")
        if not content_type.startswith("image/"):
            content_type = "image/jpeg"

        encoded = base64.b64encode(response.content).decode("utf-8")
        return f"data:{content_type};base64,{encoded}"

    except Exception as e:
        print(f"Image download failed: {e}")
        return None


# =========================================================
# 5. FETCH LATEST RECENT NEWS (TIMES OF INDIA)
# =========================================================

def get_latest_recent_news():
    print("Fetching latest top breaking news...")
    feed = feedparser.parse(NEWS_RSS_URL)

    if not feed.entries:
        raise Exception("Could not fetch RSS feed from Times of India.")

    # Grab the very first (most recent) item
    latest_item = feed.entries[0]
    story_title = latest_item.title
    story_url = latest_item.link
    
    print(f"\nFetched Latest Title: {story_title}")
    print(f"URL: {story_url}")

    # Scrape article page for direct details and High-Res Photo
    image_url = None
    article_text = ""

    try:
        art_res = requests.get(story_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        soup = BeautifulSoup(art_res.text, "html.parser")

        # Extract Meta Image (og:image)
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            image_url = og_img["content"]

        # Extract Article Body Text
        paragraphs = soup.find_all("p")
        text_list = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
        article_text = "\n\n".join(text_list[:15])

    except Exception as e:
        print(f"Detail page extraction note: {e}")

    if not article_text:
        article_text = latest_item.get("summary", story_title)

    # Download image to base64
    image_data_uri = download_image_as_data_uri(image_url) if image_url else None

    return {
        "title": story_title,
        "url": story_url,
        "image_data_uri": image_data_uri,
        "article_text": article_text
    }


news_data = get_latest_recent_news()


# =========================================================
# 6. GEMINI CLIENT & PROMPT
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
5. Include a strong intro, key highlights, background details, and conclusion.
6. End with source attribution:
   <p><strong>Source:</strong> <a href="{news_data['url']}" target="_blank" rel="nofollow noopener">Times of India</a></p>

Return ONLY valid JSON with keys "title" and "content".
"""


# =========================================================
# 7. GENERATE CONTENT
# =========================================================

response = None
for model_name in MODELS_TO_TRY:
    print(f"\nGenerating content with Gemini model: {model_name}")
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
    raise RuntimeError("Content generation failed for all models.")


# =========================================================
# 8. PARSE RESPONSE & PREPARE POST
# =========================================================

raw_text = response.text.strip()
raw_text = re.sub(r"^```json\s*", "", raw_text, flags=re.IGNORECASE)
raw_text = re.sub(r"\s*```$", "", raw_text)

data = json.loads(raw_text)
post_title = data.get("title", news_data["title"])
post_content = data.get("content", "")

# Add featured photo at the top of the post
image_html = ""
if news_data["image_data_uri"]:
    image_html = f'''
<div style="text-align:center; margin-bottom:25px;">
    <img src="{news_data["image_data_uri"]}" alt="{post_title}" style="width:100%; max-width:850px; height:auto; border-radius:12px; box-shadow:0 4px 15px rgba(0,0,0,0.15);"/>
</div>
'''

final_blog_content = image_html + post_content


# =========================================================
# 9. PUBLISH TO BLOGGER
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
