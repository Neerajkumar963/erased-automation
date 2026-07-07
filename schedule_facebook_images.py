import os
import time
import requests
import glob
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

def load_env(env_path=".env"):
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        key, val = line.split("=", 1)
                        os.environ[key.strip()] = val.strip().strip('"').strip("'")

def get_caption_from_html(html_path, post_index):
    # post_index is 1-based (4 to 13)
    # card index is post_index - 1
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    
    cards = soup.find_all('div', class_='card')
    card = cards[post_index - 1]
    
    caption_div = card.find('div', class_='sc')
    
    # Replace <br> with \n
    for br in caption_div.find_all('br'):
        br.replace_with('\n')
        
    caption = caption_div.text.strip()
    return caption

def main():
    load_env()
    page_id = os.environ.get("FACEBOOK_PAGE_ID")
    token = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN")
    
    if not page_id or not token:
        print("Missing FACEBOOK_PAGE_ID or FACEBOOK_PAGE_ACCESS_TOKEN in .env!")
        return

    html_path = "formats/hidden_family_tragedies_part3.html"
    images_dir = r"C:\Users\neera\OneDrive\Desktop\family tregieides format\output"
    
    # Starting timestamp: July 8, 2026, 11:00 AM IST
    # IST is UTC+5:30. 11:00 AM IST = 5:30 AM UTC
    base_date = datetime(2026, 7, 8, 5, 30, tzinfo=timezone.utc)
    
    url = f"https://graph.facebook.com/v20.0/{page_id}/photos"
    
    print("==================================================")
    print("Scheduling Family Tragedies (Posts 4-13) to Facebook")
    print("==================================================\n")
    
    for i in range(4, 14):
        # Calculate publish time: + (i - 4) days
        publish_dt = base_date + timedelta(days=(i - 4))
        publish_ts = int(publish_dt.timestamp())
        
        # Find image file
        search_pattern = os.path.join(images_dir, f"post_{i:02d}_*.png")
        matches = glob.glob(search_pattern)
        if not matches:
            print(f"Error: Could not find image for Post {i} matching pattern {search_pattern}")
            continue
            
        img_path = matches[0]
        
        # Get caption
        caption = get_caption_from_html(html_path, i)
        
        ist_dt = publish_dt.astimezone(timezone(timedelta(hours=5, minutes=30)))
        print(f"Post {i} ({os.path.basename(img_path)})")
        print(f"  Schedule Time: {ist_dt.strftime('%Y-%m-%d %H:%M:%S')} IST")
        print(f"  Caption Start: {caption[:70]}...")
        
        # 1. Upload the photo (Unpublished)
        photo_url = f"https://graph.facebook.com/v20.0/{page_id}/photos"
        photo_data = {
            "published": "false",
            "access_token": token
        }
        
        try:
            with open(img_path, 'rb') as f:
                files = {"source": f}
                photo_resp = requests.post(photo_url, data=photo_data, files=files).json()
                
            if "id" not in photo_resp:
                print(f"  -> ERROR uploading photo: {photo_resp}\n")
                continue
                
            photo_id = photo_resp["id"]
            
            # 2. Create the Scheduled Feed Post
            feed_url = f"https://graph.facebook.com/v20.0/{page_id}/feed"
            feed_data = {
                "published": "false",
                "scheduled_publish_time": publish_ts,
                "message": caption,
                "attached_media": f'[{{"media_fbid":"{photo_id}"}}]',
                "access_token": token
            }
            
            feed_resp = requests.post(feed_url, data=feed_data).json()
            
            if "id" in feed_resp:
                print(f"  -> SUCCESS! Scheduled Feed Post ID: {feed_resp['id']}\n")
            else:
                print(f"  -> ERROR scheduling feed post: {feed_resp}\n")
                
        except Exception as e:
            print(f"  -> CRITICAL UPLOAD ERROR: {e}\n")
            
        if i < 13:
            time.sleep(15) # Wait between posts to respect Facebook API limits

    print("All posts processed!")

if __name__ == '__main__':
    main()
