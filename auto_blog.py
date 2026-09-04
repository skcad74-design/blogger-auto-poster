import os
import json
import requests
import random
from google import genai
from google.genai import types

# ---------------------------------------------------------
# 1. Load Environment Variables
# ---------------------------------------------------------
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
BLOG_ID = os.environ.get('BLOGGER_BLOG_ID')
CLIENT_ID = os.environ.get('BLOGGER_CLIENT_ID')
CLIENT_SECRET = os.environ.get('BLOGGER_CLIENT_SECRET')
REFRESH_TOKEN = os.environ.get('BLOGGER_REFRESH_TOKEN')

# ---------------------------------------------------------
# 2. Gemini API - Generate English Viral News (BBC/ABP Style)
# ---------------------------------------------------------
client = genai.Client(api_key=GEMINI_API_KEY)

prompt = """
You are a senior international journalist writing for top networks like BBC News, ABP Live, and NDTV. 
Write a detailed, captivating, and high-traffic viral news story covering a major trending event, national/global news, sports breakthrough, entertainment update, or tech milestone.

Strict Rules:
1. LANGUAGE: Write strictly in high-quality ENGLISH.
2. WORD COUNT: Must be between 600 and 1000 words.
3. NO ADS OR EXTERNAL LINKS: Do NOT include any sponsored links, promotional copy, website URLs, or ad text.
4. FORMAT: HTML structure with <h2>, <h3> headings, engaging intro, detailed paragraphs, and key takeaways in bullet points.

Return your response strictly in JSON format with these exact keys:
1. "title": A powerful, click-worthy news headline in English (50-70 characters).
2. "content": The HTML formatted news article (600-1000 words).
3. "image_keyword": A 2-word English search phrase describing the main topic (e.g., "cricket stadium", "tech summit", "space launch") for photo matching.
"""

# CHANGED: Switched to gemini-1.5-flash for stability
response = client.models.generate_content(
    model='gemini-1.5-flash',
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json"
    ),
)

data = json.loads(response.text)
post_title = data['title']
post_content = data['content']
image_keyword = data.get('image_keyword', 'breaking news').strip().lower()

# ---------------------------------------------------------
# 3. HD Real Photo Generation (No API Key Required)
# ---------------------------------------------------------
random_id = random.randint(1, 2000)

featured_image_url = f"https://picsum.photos/seed/{requests.utils.quote(image_keyword)}{random_id}/1200/675"

image_html = f'''
<div style="text-align: center; margin-bottom: 25px;">
    <img src="{featured_image_url}" alt="{post_title}" style="width:100%; max-width:850px; height:auto; border-radius:12px; box-shadow: 0 4px 15px rgba(0,0,0,0.15); object-fit: cover;"/>
</div>
'''

final_blog_content = image_html + post_content

print(f"Generated Headline: {post_title}")
print(f"Content ready in English!")

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
    print("English Viral News Article successfully published to Blogger!")
else:
    print(f"Error publishing post: {res.status_code} - {res.text}")
