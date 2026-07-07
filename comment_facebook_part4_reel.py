import os
import sys
import json
import time
import requests
import argparse
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
    # post_index is 0-based
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    
    cards = soup.find_all('div', class_='card')
    if post_index >= len(cards):
        return None
        
    card = cards[post_index]
    caption_div = card.find('div', class_='sc')
    
    for br in caption_div.find_all('br'):
        br.replace_with('\n')
        
    return caption_div.text.strip()

def get_scheduled_post_index():
    ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    current_hour = ist_now.hour
    
    print(f"Current Date/Time in IST: {ist_now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    start_date = datetime(2026, 7, 7)
    current_date = datetime(ist_now.year, ist_now.month, ist_now.day)
    
    days_diff = (current_date - start_date).days
    if days_diff < 0:
        print("Schedule has not started yet (before July 7th).")
        return None
        
    if not (18 <= current_hour <= 20):
        print(f"Current hour {current_hour} is not in the 7:30 PM IST window. Exiting cleanly.")
        return None
        
    post_index = days_diff
    print(f"Days since start: {days_diff}. Calculated Part 4 Reel index: {post_index}")
    
    if post_index > 13:
        print(f"Calculated post index {post_index} is greater than 13. All 14 posts completed.")
        return None
        
    return post_index

def main():
    load_env()
    
    parser = argparse.ArgumentParser(description="Facebook Part 4 Reel Commenter")
    parser.add_argument("--idx", type=int, help="Override index to run manually")
    args = parser.parse_args()
    
    token = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN")
    
    if not token:
        print("Error: Missing FACEBOOK_PAGE_ACCESS_TOKEN in environment!", file=sys.stderr)
        sys.exit(1)
        
    if args.idx is not None:
        target_idx = args.idx
        print(f"Manual Override: Processing Part 4 Post index {target_idx}")
    else:
        target_idx = get_scheduled_post_index()
        if target_idx is None:
            print("No post scheduled for this slot. Exiting cleanly.")
            sys.exit(0)
            
    db_path = "facebook_part4_scheduled_ids.json"
    html_path = "formats/hidden_family_tragedies_part4.html"
    
    if os.path.exists(db_path):
        print(f"Loading Facebook scheduled IDs from {db_path}...")
        with open(db_path, "r", encoding="utf-8") as f:
            scheduled_db = json.load(f)
    else:
        print(f"Error: {db_path} not found!", file=sys.stderr)
        sys.exit(1)
        
    target_key = str(target_idx)
    if target_key not in scheduled_db:
        print(f"Error: Index {target_key} not found in scheduled DB.", file=sys.stderr)
        sys.exit(1)
        
    video_id = scheduled_db[target_key]["video_id"]
    caption = get_caption_from_html(html_path, target_idx)
    
    if not caption:
        print(f"Error: Could not extract caption for index {target_idx} from {html_path}", file=sys.stderr)
        sys.exit(1)
        
    print(f"\n==================== [Auto-Commenting on Facebook Reel {target_idx+1}] ====================")
    print(f"Facebook Video ID: {video_id}")
    print(f"Caption Preview: {caption[:100]}...")
    
    # Wait an initial 2 minutes to allow 7:30 PM cron to cross into 7:32 PM, ensuring Facebook has triggered the publish
    print("Waiting 2 minutes initially to ensure Facebook has transitioned the video to PUBLISHED status...")
    time.sleep(120)
    
    url_comment = f"https://graph.facebook.com/v20.0/{video_id}/comments"
    payload_comment = {
        "access_token": token,
        "message": caption
    }
    
    max_attempts = 30
    for attempt in range(1, max_attempts + 1):
        print(f"\n[Attempt {attempt}/{max_attempts}] Trying to add comment to video {video_id}...")
        
        try:
            resp_comment = requests.post(url_comment, data=payload_comment).json()
            if "id" in resp_comment:
                print(f"SUCCESS! Comment added successfully! Comment ID: {resp_comment['id']}")
                break
            else:
                error_msg = resp_comment.get("error", {}).get("message", str(resp_comment))
                print(f"API Error (might not be published yet): {error_msg}")
        except Exception as e:
            print(f"Exception while adding comment: {e}")
            
        if attempt < max_attempts:
            print("Retrying in 60 seconds...")
            time.sleep(60)
        else:
            print("Failed to add comment after maximum attempts. Exiting.", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
