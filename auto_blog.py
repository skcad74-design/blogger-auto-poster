import os
import json
import requests
import random
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
# 2. Gemini API - News18 Viral Style Article Generation
# ---------------------------------------------------------
client = genai.Client(api_key=GEMINI_API_KEY)

prompt = """
Act as an editor for News18 Viral Trends. 
Find a highly engaging, crazy, shocking, or heartwarming viral story currently trending in India or globally (similar to News18 Viral Trends coverage).
Write a brand new, highly detailed, and original news report on this viral event.

Strict Directives:
1. WORD COUNT: Must be detailed and strictly between 600 and 1000 words.
2. LANGUAGE: Write in fluent, catchy, high-quality ENGLISH.
3. NO COPY/ADS/LINKS: Do NOT include any third-party links, promotional copy, external URLs, or website credits.
4. FORMAT: HTML body structure with <h2>, <h3> section headers, an eye-catching headline, engaging narrative, and bulleted key facts.

Return your response strictly in JSON format with these exact keys:
1. "title": A viral News18-style clicky headline in English (50-70 characters).
2. "content": The HTML formatted original news story (600-1000 words).
3. "image_keyword": A 1-2 word English keyword matching the core story (e.g., "viral video", "puppy rescue", "stunt rider", "wedding dance") for the featured image.
"""

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json"
    ),
)

data = json.loads(response.text)
post_title = data['title']
post_content = data['content']
image_keyword = data.get('image_keyword', 'viral trend').strip().lower()

# ---------------------------------------------------------
# 3. High-Quality Dynamic HD Image Insertion
# ---------------------------------------------------------
keyword_clean = requests.utils.quote(image_keyword)
random_sig = random.randint(1000, 9999)

# HD Unsplash Dynamic Stream (Clean and high resolution)
featured_image_url = f"https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=1200&q=80&sig={random_sig}&{keyword_clean}"

image_html = f'''
<div style="text-align: center; margin-bottom: 25px;">
    <img src="{featured_image_url}" alt="{post_title}" style="width:100%; max-width:850px; height:auto; border-radius:12px; box-shadow: 0 4px 15px rgba(0,0,0,0.15); object-fit: cover;"/>
</div>
'''

final_blog_content = image_html + post_content

print(f"Generated News Headline: {post_title}")
print(f"Keywords: {image_keyword}")

# ---------------------------------------------------------
# 4. Blogger OAuth Access Token Refresh
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
# 5. Publish Post via Blogger API v3
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
    print("News18-Style Viral News successfully generated and published!")
else:
    print(f"Error publishing post: {res.status_code} - {res.text}")
