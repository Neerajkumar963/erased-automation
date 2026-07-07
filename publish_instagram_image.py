import requests
import json
import time
import os
import sys
import argparse
import random
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

def get_scheduled_post_index():
    # Current time in IST (UTC+5:30)
    ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    current_hour = ist_now.hour
    
    print(f"Current Date/Time in IST: {ist_now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    start_date = datetime(2026, 7, 8)
    current_date = datetime(ist_now.year, ist_now.month, ist_now.day)
    
    days_diff = (current_date - start_date).days
    if days_diff < 0:
        print("Schedule has not started yet (before July 8th).")
        return None
        
    # We only expect this to run at 11 AM IST (05:30 UTC)
    # Give a wide acceptance range around hour 11 just in case of delays
    if not (10 <= current_hour <= 12):
        print(f"Current hour {current_hour} is not in the 11 AM IST window. Exiting cleanly.")
        return None
        
    # Day 0 (July 8) -> Post 4
    # Day 1 (July 9) -> Post 5
    post_index = 4 + days_diff
    print(f"Days since start: {days_diff}. Calculated Image Post index: {post_index}")
    
    if post_index > 13:
        print(f"Calculated post index {post_index} is greater than 13. All posts completed.")
        return None
        
    return post_index

def main():
    load_env()
    
    parser = argparse.ArgumentParser(description="Instagram Image Auto Publisher")
    parser.add_argument("--idx", type=int, help="Override index to run manually")
    args = parser.parse_args()
    
    token = os.environ.get("FACEBOOK_USER_ACCESS_TOKEN") or os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN")
    ig_id = os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    
    if not token or not ig_id:
        print("Error: Missing Access Token or INSTAGRAM_BUSINESS_ACCOUNT_ID in environment!", file=sys.stderr)
        sys.exit(1)
        
    # Get index
    if args.idx is not None:
        target_idx = args.idx
        print(f"Manual Override: Processing Post {target_idx}")
    else:
        target_idx = get_scheduled_post_index()
        if target_idx is None:
            print("No post scheduled for this slot. Exiting cleanly.")
            sys.exit(0)
            
        # Apply anti-bot random delay (0 to 300 seconds)
        delay_sec = random.randint(0, 300)
        print(f"Sleeping for {delay_sec} seconds to prevent bot flags...")
        time.sleep(delay_sec)
        
    # Load assets from scheduled_images.json
    db_path = "scheduled_images.json"
    if os.path.exists(db_path):
        print(f"Loading post data from {db_path}...")
        with open(db_path, "r", encoding="utf-8") as f:
            scheduled_db = json.load(f)
            
        target_key = str(target_idx)
        if target_key not in scheduled_db:
            print(f"Error: Post index {target_idx} not found in {db_path}!", file=sys.stderr)
            sys.exit(1)
            
        post_data = scheduled_db[target_key]
        image_url = post_data["image_url"]
        caption = post_data["caption"]
        
    else:
        print(f"Error: {db_path} not found!", file=sys.stderr)
        sys.exit(1)
            
    print(f"\n==================== [Publishing Image Post {target_idx} to Instagram] ====================")
    print(f"Image URL: {image_url}")
    
    # -------------------- INSTAGRAM PUBLISHING --------------------
    print("\n-------------------- [Publishing to Instagram Feed] --------------------")
    url_container = f"https://graph.facebook.com/v20.0/{ig_id}/media"
    payload = {
        "access_token": token,
        "image_url": image_url,
        "caption": caption
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
        
        # Images usually process instantly, but adding a short safety delay
        time.sleep(5)
            
        # Publish the media container live
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
            print(f"\nSUCCESS! Image Post is now live on Instagram! Post ID: {resp_pub['id']}")
        else:
            print(f"\nError: Publishing container failed: {resp_pub}", file=sys.stderr)
            
    except Exception as e:
        print(f"Error during Instagram workflow: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
