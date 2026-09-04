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
# 2. Gemini API - Post Generation
# ---------------------------------------------------------
client = genai.Client(api_key=GEMINI_API_KEY)

prompt = """
You are a professional lifestyle journalist and expert blogger.
Write a highly engaging, viral, and SEO-optimized blog article focusing on one of the following niches:
- Relationships & Couple Wellness
- Gym, Bodybuilding & Fitness Routines
- Makeup, Beauty & Skincare Trends
- Fashion & Personal Style Guides
- Healthy Lifestyle & Mindful Living

Rules:
1. LANGUAGE: Write strictly in fluent, high-quality ENGLISH.
2. WORD COUNT: Must be detailed and strictly between 600 and 1000 words.
3. NO ADS OR EXTERNAL LINKS: Do NOT include any promotional text, website URLs, or affiliate links in the text content.
4. FORMAT: Use proper HTML structure with <h2>, <h3> headings, an engaging intro, actionable tips, bullet points, and a concluding thought.

Return your response strictly in JSON format with these exact keys:
1. "title": A catchy, click-worthy headline in English (50-70 characters).
2. "content": The HTML formatted blog post (600-1000 words).
3. "image_keyword": A 1-2 word simple English keyword (e.g. "fitness", "makeup", "couple", "fashion", "workout") for photo matching.
"""

# FIXED: Updated model string to gemini-3.6-flash
response = client.models.generate_content(
    model='gemini-3.6-flash',
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json"
    ),
)

data = json.loads(response.text)
post_title = data['title']
post_content = data['content']
image_keyword = data.get('image_keyword', 'lifestyle').strip().lower()

# ---------------------------------------------------------
# 3. High-Quality Dynamic HD Image Stream
# ---------------------------------------------------------
keyword_clean = requests.utils.quote(image_keyword)
random_sig = random.randint(1000, 9999)

featured_image_url = f"https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=1200&q=80&sig={random_sig}&{keyword_clean}"

image_html = f'''
<div style="text-align: center; margin-bottom: 25px;">
    <img src="{featured_image_url}" alt="{post_title}" style="width:100%; max-width:850px; height:auto; border-radius:12px; box-shadow: 0 4px 15px rgba(0,0,0,0.15); object-fit: cover;"/>
</div>
'''

final_blog_content = image_html + post_content

print(f"Generated Title: {post_title}")
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
    print("Article successfully published to Blogger!")
else:
    print(f"Error publishing post: {res.status_code} - {res.text}")
