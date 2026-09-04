import os
import json
import requests
from google import genai
from google.genai import types

# ---------------------------------------------------------
# ১. এনভায়রনমেন্ট ভেরিয়েবল লোড
# ---------------------------------------------------------
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
BLOG_ID = os.environ.get('BLOGGER_BLOG_ID')
CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')
REFRESH_TOKEN = os.environ.get('REFRESH_TOKEN')

# ---------------------------------------------------------
# ২. Gemini API দিয়ে SEO পোস্ট ও ছবি জেনারেট
# ---------------------------------------------------------
client = genai.Client(api_key=GEMINI_API_KEY)

prompt = """
You are an expert SEO blogger. Create a unique, engaging, highly SEO-optimized blog post on a trending topic in tech, health, lifestyle, or digital marketing.

Return your response strictly in JSON format with these exact keys:
1. "title": A compelling, click-worthy SEO title (50-60 characters).
2. "content": The HTML formatted blog post content. Include:
   - Proper heading hierarchy (<h2>, <h3>)
   - Engaging introduction, well-structured bullet points, and conclusion
   - Relevant keywords naturally integrated for search engines
3. "image_keyword": A 2-3 word English search phrase (e.g. "artificial intelligence laptop", "healthy fitness meal") to fetch a matching high-quality unsplash image.
"""

# আপডেট করা মডেল ভার্সন (gemini-2.5-flash)
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
image_keyword = data.get('image_keyword', 'technology')

# Unsplash ইমেজ লিংক জেনারেট
featured_image_url = f"https://source.unsplash.com/800x450/?{requests.utils.quote(image_keyword)}"
image_html = f'<div style="text-align: center; margin-bottom: 20px;"><img src="{featured_image_url}" alt="{post_title}" style="max-width:100%; height:auto; border-radius:8px;"/></div>'

final_blog_content = image_html + post_content

print(f"Generated Title: {post_title}")

# ---------------------------------------------------------
# ৩. Blogger OAuth Access Token রিফ্রেশ
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
# ৪. Blogger API v3 দিয়ে পোস্ট পাবলিশ
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
    print("SEO Blog post successfully published to Blogger!")
else:
    print(f"Error publishing post: {res.status_code} - {res.text}")
