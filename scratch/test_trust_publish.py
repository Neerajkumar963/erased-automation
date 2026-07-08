import os
import time
import requests
import json
from bs4 import BeautifulSoup

def load_env(env_path=".env"):
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip().strip('"').strip("'")

def get_post_data():
    # Get Video URL
    with open('part5_database.json', 'r', encoding='utf-8') as f:
        db = json.load(f)
        video_url = db['post_01']['dropbox_url']
        
    # Get Caption
    with open(r'formats\hidden_family_tragedies_part5.html', 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
        card = soup.find_all('div', class_='card')[0]
        caption_div = card.find('div', class_='sc')
        for br in caption_div.find_all('br'):
            br.replace_with('\n')
        caption = caption_div.text.strip()
        
    return video_url, caption

def publish_to_instagram(video_url, caption):
    access_token = os.environ.get("FACEBOOK_USER_ACCESS_TOKEN")
    ig_user_id = os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    
    if not access_token or not ig_user_id:
        print("Error: Missing credentials in .env")
        return
        
    print(f"Video URL: {video_url}")
    print(f"Caption Preview: {caption[:50]}...")
    
    print("\n[Step 1] Creating Media Container on Instagram...")
    url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
    payload = {
        'media_type': 'REELS',
        'video_url': video_url,
        'caption': caption,
        'access_token': access_token
    }
    
    res = requests.post(url, data=payload)
    res_data = res.json()
    
    if 'id' not in res_data:
        print(f"Failed to create container: {res_data}")
        return
        
    container_id = res_data['id']
    print(f"Container created successfully! ID: {container_id}")
    
    print("\n[Step 2] Waiting for Instagram to process the video...")
    status_url = f"https://graph.facebook.com/v19.0/{container_id}?fields=status_code&access_token={access_token}"
    
    max_retries = 20
    for i in range(max_retries):
        time.sleep(5) # Wait 5 seconds between checks
        status_res = requests.get(status_url).json()
        status = status_res.get('status_code', 'UNKNOWN')
        print(f"Checking status... [{status}]")
        
        if status == 'FINISHED':
            break
        elif status == 'ERROR':
            print("Instagram failed to process the video. It might be an invalid format or URL.")
            return
            
    print("\n[Step 3] Publishing to Instagram feed...")
    publish_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish"
    pub_payload = {
        'creation_id': container_id,
        'access_token': access_token
    }
    
    pub_res = requests.post(publish_url, data=pub_payload)
    pub_data = pub_res.json()
    
    if 'id' in pub_data:
        print(f"\n✅ SUCCESS! Reel published successfully with ID: {pub_data['id']}")
        print("Please check your Instagram app right now!")
    else:
        print(f"\n❌ Publish Failed: {pub_data}")

if __name__ == "__main__":
    load_env()
    print("Loading Part 5 Post 1 (Nelson Mandela) from Warehouse...")
    try:
        vid, cap = get_post_data()
        publish_to_instagram(vid, cap)
    except Exception as e:
        print(f"Script Error: {e}")
