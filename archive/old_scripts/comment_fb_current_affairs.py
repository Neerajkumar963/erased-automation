import os
import json
import requests
import time
import sys
from datetime import datetime, timezone, timedelta

def load_env(env_path=".env"):
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        key, val = line.split("=", 1)
                        os.environ[key.strip()] = val.strip().strip('"').strip("'")

def get_current_affairs_index():
    ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    start_date = datetime(2026, 7, 8)
    current_date = datetime(ist_now.year, ist_now.month, ist_now.day)
    
    days_diff = (current_date - start_date).days
    if days_diff < 0:
        return None
        
    current_hour = ist_now.hour
    if not (5 <= current_hour < 7):
        return None
        
    post_index = days_diff + 1
    if post_index > 22:
        return None
        
    return f"post_{post_index:02d}"

def main():
    load_env()
    page_id = os.environ.get("FACEBOOK_PAGE_ID")
    token = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN")
    
    if not page_id or not token:
        print("Error: Missing FACEBOOK_PAGE_ID or FACEBOOK_PAGE_ACCESS_TOKEN!")
        sys.exit(1)
        
    target_key = get_current_affairs_index()
    if not target_key:
        print("No Current Affairs post scheduled for today. Exiting.")
        sys.exit(0)
        
    db_path = "current_affairs_data.json"
    with open(db_path, "r", encoding="utf-8") as f:
        db = json.load(f)
        
    if target_key not in db:
        print(f"Error: {target_key} not in DB.")
        sys.exit(1)
        
    post_data = db[target_key]
    caption_start = post_data["caption"][:20].lower() # First 20 chars to identify
    
    print(f"\n==================== [Watchdog: Commenting on FB Post {target_key}] ====================")
    print(f"Looking for post starting with: '{caption_start}'")
    
    # STRICT POLLING: Check the page feed every 30 seconds for up to 15 minutes
    feed_url = f"https://graph.facebook.com/v20.0/{page_id}/feed?fields=id,message,created_time&access_token={token}&limit=5"
    
    max_attempts = 30 # 15 minutes
    target_post_id = None
    
    print("\nPolling Facebook Page Feed (Strict Polling for 15 mins)...")
    for attempt in range(max_attempts):
        print(f"  [Poll {attempt+1}/{max_attempts}] Fetching latest posts...")
        feed_resp = requests.get(feed_url).json()
        posts = feed_resp.get("data", [])
        
        for post in posts:
            msg = post.get("message", "").lower()
            if msg.startswith(caption_start):
                target_post_id = post["id"]
                print(f"  -> SUCCESS! Found matching post: {target_post_id}")
                break
                
        if target_post_id:
            break
            
        time.sleep(30)
    else:
        print("Error: Timed out waiting for the Facebook post to appear in the feed.")
        sys.exit(1)
        
    # Post the single combined comment
    print("\n-------------------- [Posting Combined Pinned Comment] --------------------")
    combined_comment = f"{post_data['fun_fact']}\n.\n.\n{post_data['cta_question']}\n.\n.\nFollow @erased.record for more daily insights."
    
    comment_url = f"https://graph.facebook.com/v20.0/{target_post_id}/comments"
    payload = {
        "message": combined_comment,
        "access_token": token
    }
    
    comment_resp = requests.post(comment_url, data=payload).json()
    if "id" in comment_resp:
        print(f"SUCCESS! Comment posted on Facebook. Comment ID: {comment_resp['id']}")
    else:
        print(f"Error posting comment: {comment_resp}")

if __name__ == "__main__":
    main()
