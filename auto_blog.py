import os
import json
import requests
import random
from google import genai
from google.genai import types

# ---------------------------------------------------------
# ১. এনভায়রনমেন্ট ভেরিয়েবল লোড
# ---------------------------------------------------------
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
BLOG_ID = os.environ.get('BLOGGER_BLOG_ID')
CLIENT_ID = os.environ.get('BLOGGER_CLIENT_ID')
CLIENT_SECRET = os.environ.get('BLOGGER_CLIENT_SECRET')
REFRESH_TOKEN = os.environ.get('BLOGGER_REFRESH_TOKEN')

# ---------------------------------------------------------
# ২. Gemini API দিয়ে SEO পোস্ট জেনারেট
# ---------------------------------------------------------
client = genai.Client(api_key=GEMINI_API_KEY)

prompt = """
You are an expert SEO blogger. Create a unique, engaging, highly SEO-optimized blog post on a trending topic in Tech, Health, Lifestyle, or Digital Marketing.

Return your response strictly in JSON format with these exact keys:
1. "title": A compelling, click-worthy SEO title (50-60 characters).
2. "content": The HTML formatted blog post content. Include proper heading hierarchy (<h2>, <h3>), engaging introduction, bullet points, and conclusion.
3. "image_keyword": A simple 1-2 word topic keyword (e.g., "laptop", "fitness", "coffee", "marketing") to match the post theme.
"""

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
image_keyword = data.get('image_keyword', 'technology').strip().lower()

# ---------------------------------------------------------
# ৩. API ছাড়া সরাসরি Real HD Photo Fetch (No API Key Required)
# ---------------------------------------------------------
# র্যান্ডম সীড ব্যবহার করা হয়েছে যাতে প্রতি পোস্টে একদম নতুন এইচডি ছবি আসে
random_id = random.randint(1, 1000)

# 1200x675 রেজোলিউশনের হাই ডিফিনিশন রিয়েল ফটো ইউআরএল
featured_image_url = f"https://picsum.photos/seed/{requests.utils.quote(image_keyword)}{random_id}/1200/675"

image_html = f'''
<div style="text-align: center; margin-bottom: 25px;">
    <img src="{featured_image_url}" alt="{post_title}" style="width:100%; max-width:850px; height:auto; border-radius:12px; box-shadow: 0 4px 15px rgba(0,0,0,0.15); object-fit: cover;"/>
</div>
'''

final_blog_content = image_html + post_content

print(f"Generated Title: {post_title}")
print(f"Image Link: {featured_image_url}")

# ---------------------------------------------------------
# ৪. Blogger OAuth Access Token রিফ্রেশ
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
# ৫. Blogger API v3 দিয়ে পোস্ট পাবলিশ
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
    print("SEO Blog post with Real HD photo successfully published to Blogger!")
else:
    print(f"Error publishing post: {res.status_code} - {res.text}")
