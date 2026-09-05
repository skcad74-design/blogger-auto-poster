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

if not GEMINI_API_KEY:
    missing.append("GEMINI_API_KEY")

if not BLOG_ID:
    missing.append("BLOGGER_BLOG_ID")

if not CLIENT_ID:
    missing.append("BLOGGER_CLIENT_ID")

if not CLIENT_SECRET:
    missing.append("BLOGGER_CLIENT_SECRET")

if not REFRESH_TOKEN:
    missing.append("BLOGGER_REFRESH_TOKEN")

if missing:
    raise RuntimeError(
        "Missing environment variables:\n- "
        + "\n- ".join(missing)
    )


# =========================================================
# 3. SETTINGS
# =========================================================

NEWS_URL = "https://www.news18.com/viral/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_TIMEOUT = 20

# Current Gemini models.
# Google currently lists Gemini 3.7 Flash, 3.6 Flash,
# 3.5 Flash and 3.5 Flash-Lite as available models.
MODELS_TO_TRY = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
]


# =========================================================
# 4. CLEAN TEXT
# =========================================================

def clean_text(text):
    if not text:
        return ""

    text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# =========================================================
# 5. DOWNLOAD IMAGE
# =========================================================

def download_image_as_data_uri(image_url):
    """
    Downloads image and converts it to a data URI.
    """

    try:
        if not image_url:
            return None

        image_url = urljoin(NEWS_URL, image_url)

        response = requests.get(
            image_url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

        content_type = response.headers.get(
            "Content-Type",
            "image/jpeg"
        )

        if not content_type.startswith("image/"):
            content_type = "image/jpeg"

        encoded = base64.b64encode(response.content).decode("utf-8")

        return f"data:{content_type};base64,{encoded}"

    except Exception as e:
        print(f"Image download failed: {e}")
        return None


# =========================================================
# 6. FETCH NEWS18 STORY
# =========================================================

def get_news18_story():

    try:
        print("Opening News18 Viral page...")

        response = requests.get(
            NEWS_URL,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        candidates = []

        # -------------------------------------------------
        # Find article links
        # -------------------------------------------------

        for link in soup.find_all("a", href=True):

            href = link.get("href")

            title = (
                link.get("title")
                or link.get_text(" ", strip=True)
            )

            title = clean_text(title)

            if not href or not title:
                continue

            href = urljoin(NEWS_URL, href)

            if "news18.com" not in href:
                continue

            # Ignore navigation links
            if len(title) < 30:
                continue

            candidates.append({
                "title": title,
                "url": href
            })

        # Remove duplicates
        unique = []

        seen = set()

        for item in candidates:

            if item["url"] in seen:
                continue

            seen.add(item["url"])
            unique.append(item)

        if not unique:
            raise Exception(
                "Could not find a News18 article."
            )

        # First valid candidate
        story_url = unique[0]["url"]
        story_title = unique[0]["title"]

        print("Found article:")
        print(story_title)
        print(story_url)

        # -------------------------------------------------
        # Open article page
        # -------------------------------------------------

        article_response = requests.get(
            story_url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT
        )

        article_response.raise_for_status()

        article_soup = BeautifulSoup(
            article_response.text,
            "html.parser"
        )

        # -------------------------------------------------
        # Get canonical title
        # -------------------------------------------------

        og_title = article_soup.find(
            "meta",
            property="og:title"
        )

        if og_title and og_title.get("content"):
            story_title = clean_text(
                og_title["content"]
            )

        # -------------------------------------------------
        # Get image
        # -------------------------------------------------

        image_url = None

        og_image = article_soup.find(
            "meta",
            property="og:image"
        )

        if og_image:
            image_url = og_image.get("content")

        if not image_url:

            twitter_image = article_soup.find(
                "meta",
                attrs={"name": "twitter:image"}
            )

            if twitter_image:
                image_url = twitter_image.get("content")

        if not image_url:

            first_image = article_soup.find("img")

            if first_image:
                image_url = (
                    first_image.get("src")
                    or first_image.get("data-src")
                    or first_image.get("data-original")
                )

        image_data_uri = download_image_as_data_uri(
            image_url
        )

        # -------------------------------------------------
        # Get article text
        # -------------------------------------------------

        article_text_parts = []

        # Try article tag first
        article_tag = article_soup.find("article")

        if article_tag:

            paragraphs = article_tag.find_all("p")

            for p in paragraphs:

                text = clean_text(p.get_text(" "))

                if len(text) > 40:
                    article_text_parts.append(text)

        # Fallback: all paragraphs
        if not article_text_parts:

            for p in article_soup.find_all("p"):

                text = clean_text(p.get_text(" "))

                if len(text) > 40:
                    article_text_parts.append(text)

        article_text = "\n\n".join(
            article_text_parts[:40]
        )

        if len(article_text) < 200:

            print(
                "Warning: Article text could not be "
                "fully extracted."
            )

            article_text = (
                f"Headline: {story_title}\n"
                f"Source URL: {story_url}"
            )

        return {
            "title": story_title,
            "url": story_url,
            "image_data_uri": image_data_uri,
            "article_text": article_text
        }

    except Exception as e:

        print(
            f"News18 extraction failed: {e}"
        )

        return {
            "title": "Latest Viral News",
            "url": NEWS_URL,
            "image_data_uri": None,
            "article_text": (
                "Latest viral news from News18."
            )
        }


# =========================================================
# 7. GET NEWS
# =========================================================

news_data = get_news18_story()

print("\n========================================")
print("NEWS TITLE")
print("========================================")
print(news_data["title"])

print("\n========================================")
print("SOURCE")
print("========================================")
print(news_data["url"])


# =========================================================
# 8. GEMINI CLIENT
# =========================================================

client = genai.Client(
    api_key=GEMINI_API_KEY
)


# =========================================================
# 9. PROMPT
# =========================================================

prompt = f"""
You are an experienced viral news reporter and SEO blog writer.

Rewrite the following News18 story into an ORIGINAL,
fact-focused English blog article.

IMPORTANT:
- Do NOT copy sentences word-for-word.
- Do NOT invent facts.
- Do NOT invent quotes.
- Clearly attribute information to News18 where appropriate.
- Keep the article natural and readable.
- The article should be useful for Google Search readers.
- Avoid clickbait claims that are not supported by the source.

SOURCE HEADLINE:
{news_data["title"]}

SOURCE URL:
{news_data["url"]}

SOURCE ARTICLE TEXT:
{news_data["article_text"]}

Requirements:

1. Language:
Natural fluent English.

2. Length:
400-600 words.

3. HTML:
Return clean HTML only inside the "content" field.

Use:
<h2>
<h3>
<p>
<ul>
<li>

Do NOT use:
<html>
<head>
<body>
Markdown code fences.

4. SEO title:
Create an engaging SEO-friendly title.
Keep it approximately 50-65 characters when possible.

5. Content:
Include:
- A strong introduction
- Important facts
- What happened
- Why it became viral
- Relevant context
- A short conclusion

6. Source:
At the end of the article include:

<p>
<strong>Source:</strong>
<a href="{news_data["url"]}" target="_blank" rel="nofollow noopener">
News18
</a>
</p>

Return ONLY valid JSON.

Exact JSON structure:

{{
    "title": "SEO title here",
    "content": "<h2>...</h2><p>...</p>"
}}
"""


# =========================================================
# 10. GEMINI GENERATION
# =========================================================

response = None

for model_name in MODELS_TO_TRY:

    print(
        f"\nTrying Gemini model: {model_name}"
    )

    for attempt in range(5):

        try:

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7,
                    max_output_tokens=5000
                )
            )

            print(
                f"Success: {model_name}"
            )

            break

        except Exception as e:

            error_msg = str(e)

            print(
                f"Attempt {attempt + 1} failed:"
            )

            print(error_msg)

            error_upper = error_msg.upper()

            if (
                "429" in error_msg
                or "RESOURCE_EXHAUSTED" in error_upper
                or "503" in error_msg
                or "UNAVAILABLE" in error_upper
            ):

                wait_time = 30 * (
                    attempt + 1
                )

                print(
                    f"Retrying after {wait_time} seconds..."
                )

                time.sleep(wait_time)

            elif (
                "404" in error_msg
                or "NOT_FOUND" in error_upper
            ):

                print(
                    "Model unavailable. "
                    "Trying next model..."
                )

                break

            else:

                time.sleep(10)

    if response:
        break


if not response:

    raise RuntimeError(
        "Gemini content generation failed "
        "for all available models."
    )


# =========================================================
# 11. PARSE GEMINI JSON
# =========================================================

try:

    raw_text = response.text.strip()

    # Remove accidental markdown fences
    raw_text = re.sub(
        r"^```json\s*",
        "",
        raw_text,
        flags=re.IGNORECASE
    )

    raw_text = re.sub(
        r"\s*```$",
        "",
        raw_text
    )

    data = json.loads(raw_text)

except Exception as e:

    print("\nGemini returned:")
    print(response.text)

    raise RuntimeError(
        f"Could not parse Gemini JSON: {e}"
    )


post_title = data.get("title", "").strip()
post_content = data.get("content", "").strip()

if not post_title:
    raise RuntimeError(
        "Gemini did not return a post title."
    )

if not post_content:
    raise RuntimeError(
        "Gemini did not return post content."
    )


# =========================================================
# 12. IMAGE HTML
# =========================================================

if news_data["image_data_uri"]:

    image_html = f"""
<div style="text-align:center;margin-bottom:25px;">
    <img
        src="{news_data["image_data_uri"]}"
        alt="{post_title}"
        style="
            width:100%;
            max-width:850px;
            height:auto;
            border-radius:12px;
            box-shadow:0 4px 15px rgba(0,0,0,0.15);
        "
    />
</div>
"""

else:

    image_html = ""


final_blog_content = (
    image_html
    + post_content
)


# =========================================================
# 13. GOOGLE OAUTH TOKEN REFRESH
# =========================================================

TOKEN_URL = (
    "https://oauth2.googleapis.com/token"
)

token_data = {
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "refresh_token": REFRESH_TOKEN,
    "grant_type": "refresh_token"
}

print("\nRefreshing Blogger OAuth token...")

token_res = requests.post(
    TOKEN_URL,
    data=token_data,
    timeout=REQUEST_TIMEOUT
)

try:
    token_json = token_res.json()
except Exception:
    raise RuntimeError(
        "Google OAuth returned invalid JSON:\n"
        + token_res.text
    )


if "access_token" not in token_json:

    raise RuntimeError(
        "OAuth token refresh failed:\n"
        + json.dumps(
            token_json,
            indent=2
        )
    )


access_token = token_json["access_token"]

print("OAuth token successfully refreshed.")


# =========================================================
# 14. BLOGGER API
# =========================================================

BLOGGER_URL = (
    "https://www.googleapis.com/blogger/v3/blogs/"
    f"{BLOG_ID}/posts/"
)


headers = {
    "Authorization": (
        f"Bearer {access_token}"
    ),
    "Content-Type": "application/json"
}


payload = {
    "kind": "blogger#post",
    "title": post_title,
    "content": final_blog_content
}


# =========================================================
# 15. PUBLISH TO BLOGGER
# =========================================================

print("\nPublishing to Blogger...")

res = requests.post(
    BLOGGER_URL,
    headers=headers,
    json=payload,
    timeout=REQUEST_TIMEOUT
)


if res.status_code in (200, 201):

    try:
        result = res.json()
    except Exception:
        result = {}

    print("\n========================================")
    print("SUCCESS")
    print("========================================")

    print(
        f"Title: {post_title}"
    )

    if result.get("url"):
        print(
            f"URL: {result['url']}"
        )

    print(
        f"HTTP Status: {res.status_code}"
    )

else:

    print("\n========================================")
    print("BLOGGER PUBLISH FAILED")
    print("========================================")

    print(
        f"Status: {res.status_code}"
    )

    print(
        res.text
    )

    raise RuntimeError(
        "Blogger API publishing failed."
    )
