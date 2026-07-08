import requests
import json
import time
import os
import sys
import argparse
import random
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

def load_env(env_path=".env"):
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip().strip('"').strip("'")

def get_caption_from_html(html_path, post_index):
    # post_index is 0-based for list indexing
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    
    cards = soup.find_all('div', class_='card')
    if post_index >= len(cards):
        return None
        
    card = cards[post_index]
    caption_div = card.find('div', class_='sc')
    for br in caption_div.find_all('br'):
        br.replace_with('\n')
    hook_caption = caption_div.text.strip()
    
    pinned_div = card.find('div', class_='pinned_comment')
    pinned_text = ""
    if pinned_div:
        for br in pinned_div.find_all('br'):
            br.replace_with('\n')
        pinned_text = pinned_div.text.strip()
        
    return hook_caption, pinned_text

def get_scheduled_post_index():
    ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    current_hour = ist_now.hour
    
    print(f"Current Date/Time in IST: {ist_now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Start date is July 7 (Today) because 7:30 PM today is the first slot
    start_date = datetime(2026, 7, 7)
    current_date = datetime(ist_now.year, ist_now.month, ist_now.day)
    
    days_diff = (current_date - start_date).days
    if days_diff < 0:
        print("Schedule has not started yet (before July 7th).")
        return None
        
    # We only expect this to run at 7:30 PM IST (14:00 UTC)
    if not (18 <= current_hour <= 20):
        print(f"Current hour {current_hour} is not in the 7:30 PM IST window. Exiting cleanly.")
        return None
        
    # Day 0 (July 7) -> Post index 0 (Post 1)
    post_index = days_diff
    print(f"Days since start: {days_diff}. Calculated Part 5 Reel index: {post_index}")
    
    if post_index > 13:
        print(f"Calculated post index {post_index} is greater than 13. All 14 posts completed.")
        return None
        
    return post_index

def main():
    load_env()
    
    parser = argparse.ArgumentParser(description="Instagram Part 5 Reel Publisher")
    parser.add_argument("--idx", type=int, help="Override index to run manually")
    args = parser.parse_args()
    
    token = os.environ.get("FACEBOOK_USER_ACCESS_TOKEN") or os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN")
    ig_id = os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    
    if not token or not ig_id:
        print("Error: Missing Access Token or INSTAGRAM_BUSINESS_ACCOUNT_ID in environment!", file=sys.stderr)
        sys.exit(1)
        
    if args.idx is not None:
        target_idx = args.idx
        print(f"Manual Override: Processing Part 5 Post index {target_idx}")
    else:
        target_idx = get_scheduled_post_index()
        if target_idx is None:
            print("No post scheduled for this slot. Exiting cleanly.")
            sys.exit(0)
            
        delay_sec = random.randint(0, 300)
        print(f"Sleeping for {delay_sec} seconds to prevent bot flags...")
        time.sleep(delay_sec)
        
    db_path = "part5_video_links.json"
    html_path = "formats/hidden_family_tragedies_part5.html"
    
    if os.path.exists(db_path):
        print(f"Loading video URLs from {db_path}...")
        with open(db_path, "r", encoding="utf-8") as f:
            links_db = json.load(f)
    else:
        print(f"Error: {db_path} not found!", file=sys.stderr)
        sys.exit(1)
        
    video_keys = sorted(list(links_db.keys()))
    if target_idx >= len(video_keys):
        print(f"Error: Index {target_idx} is out of bounds for the {len(video_keys)} videos found.", file=sys.stderr)
        sys.exit(1)
        
    target_key = video_keys[target_idx]
    video_url = links_db[target_key]
    caption, pinned_comment_text = get_caption_from_html(html_path, target_idx)
    
    if not caption:
        print(f"Error: Could not extract caption for index {target_idx} from {html_path}", file=sys.stderr)
        sys.exit(1)
        
    print(f"\n==================== [Publishing Part 5 Reel {target_idx+1} to Instagram] ====================")
    print(f"Video URL: {video_url}")
    print(f"Caption Preview: {caption[:100]}...")
    
    print("\n-------------------- [Publishing to Instagram Reels] --------------------")
    url_container = f"https://graph.facebook.com/v20.0/{ig_id}/media"
    payload = {
        "access_token": token,
        "video_url": video_url,
        "caption": caption,
        "media_type": "REELS",
        "share_to_feed": "true"
    }
    
    try:
        resp_c = requests.post(url_container, data=payload).json()
        print("Instagram Container API Response:")
        print(json.dumps(resp_c, indent=2))
        
        if "id" not in resp_c:
            print("Error: Failed to create Instagram container.", file=sys.stderr)
            sys.exit(1)
            
        container_id = resp_c["id"]
        print(f"Instagram Container created successfully. ID: {container_id}")
        
        print("Waiting for video processing on Instagram servers (polling status)...")
        status_url = f"https://graph.facebook.com/v20.0/{container_id}?fields=status_code&access_token={token}"
        
        is_ready = False
        for attempt in range(30): # Wait up to 5 minutes
            try:
                status_resp = requests.get(status_url).json()
                status_code = status_resp.get("status_code", "UNKNOWN")
                print(f"  [Attempt {attempt+1}] Container status: {status_code}")
                
                if status_code.upper() == "FINISHED":
                    is_ready = True
                    break
                elif status_code.upper() == "ERROR":
                    print(f"Error: Instagram failed to process the video container. Response: {status_resp}", file=sys.stderr)
                    sys.exit(1)
            except Exception as e:
                print(f"  Warning: Status check failed: {e}")
                
            time.sleep(10)
            
        if not is_ready:
            print("Error: Container processing timed out after 5 minutes.", file=sys.stderr)
            sys.exit(1)
            
        url_publish = f"https://graph.facebook.com/v20.0/{ig_id}/media_publish"
        payload_pub = {
            "access_token": token,
            "creation_id": container_id
        }
        
        print("\nPublishing media container live on Instagram...")
        resp_pub = requests.post(url_publish, data=payload_pub).json()
        print("Publish API Response:")
        print(json.dumps(resp_pub, indent=2))
        
        if "id" in resp_pub:
            media_id = resp_pub['id']
            print(f"\nSUCCESS! Reel is now live on Instagram! Post ID: {media_id}")
            
            # --- ADDING COMMENT ---
            print("\n-------------------- [Adding Pinned Comment] --------------------")
            url_comment = f"https://graph.facebook.com/v20.0/{media_id}/comments"
            payload_comment = {
                "access_token": token,
                "message": pinned_comment_text
            }
            
            try:
                resp_comment = requests.post(url_comment, data=payload_comment).json()
                if "id" in resp_comment:
                    print(f"SUCCESS! Comment added successfully! Comment ID: {resp_comment['id']}")
                    print("Note: The Instagram API does not support pinning comments. Pinning must be done manually via the app.")
                else:
                    print(f"Error: Failed to add comment: {resp_comment}", file=sys.stderr)
            except Exception as e:
                print(f"Error while adding comment: {e}", file=sys.stderr)
                
        else:
            print(f"\nError: Publishing container failed: {resp_pub}", file=sys.stderr)
            
    except Exception as e:
        print(f"Error during Instagram workflow: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
