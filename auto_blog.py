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
3. "image_keyword": A clear 2-3 word English visual subject (e.g. "futuristic smartphone on desk", "fresh healthy salad bowl") to generate a photo.
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
image_keyword = data.get('image_keyword', 'modern technology desk')

# ---------------------------------------------------------
# ৩. Ultra-HD High Quality AI Photo Generation
# ---------------------------------------------------------
# HD ও রিয়েলিস্টিক প্রম্পট এনহ্যান্সমেন্ট
hd_prompt = f"4k resolution, ultra detailed, realistic photography, professional studio lighting, 8k render, {image_keyword}"
encoded_prompt = requests.utils.quote(hd_prompt)

# Pollinations AI (HD Resolution: 1200x675 with high detail parameters)
featured_image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1200&height=675&nologo=true&enhance=true"

image_html = f'<div style="text-align: center; margin-bottom: 20px;"><img src="{featured_image_url}" alt="{post_title}" style="max-width:100%; height:auto; border-radius:10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);"/></div>'

final_blog_content = image_html + post_content

print(f"Generated Title: {post_title}")

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
    print("SEO Blog post with HD photo successfully published to Blogger!")
else:
    print(f"Error publishing post: {res.status_code} - {res.text}")
