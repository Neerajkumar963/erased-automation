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

def upload_to_tmpfiles(file_path):
    print(f"Uploading {file_path} to tmpfiles.org...")
    url = "https://tmpfiles.org/api/v1/upload"
    try:
        with open(file_path, "rb") as f:
            files = {"file": f}
            resp = requests.post(url, files=files).json()
            if resp.get("status") == "success":
                link = resp["data"]["url"]
                dl_link = link.replace("https://tmpfiles.org/", "https://tmpfiles.org/dl/")
                return dl_link
    except Exception as e:
        print(f"Error uploading {file_path}: {e}", file=sys.stderr)
    return None

def get_scheduled_post_index():
    # Current time in IST (UTC+5:30)
    ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    current_date_str = ist_now.strftime("%Y-%m-%d")
    current_hour = ist_now.hour
    
    print(f"Current Date/Time in IST: {ist_now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    start_date = datetime(2026, 7, 12)
    current_date = datetime(ist_now.year, ist_now.month, ist_now.day)
    
    days_diff = (current_date - start_date).days
    if days_diff < 0:
        print("Schedule has not started yet (before July 12th).")
        return None
        
    # Slot detection (IST hour blocks)
    # Slot 1: Morning (around 5:30 AM). Accept range: hour 5 to 7
    # Slot 2: Afternoon (around 1:30 PM). Accept range: hour 13 to 15
    # Slot 3: Night (around 10:30 PM). Accept range: hour 22 to 23
    if 5 <= current_hour < 7:
        slot = 0
        slot_name = "Morning (Slot 1)"
    elif 13 <= current_hour < 15:
        slot = 1
        slot_name = "Afternoon (Slot 2)"
    elif 22 <= current_hour <= 23:
        slot = 2
        slot_name = "Night (Slot 3)"
    else:
        print(f"Current hour {current_hour} is not in any scheduled slot window.")
        return None
        
    post_index = 22 + (days_diff * 3) + slot
    print(f"Detected Slot: {slot_name}, Days since start: {days_diff}. Calculated index: {post_index}")
    
    if post_index > 40:
        print(f"Calculated post index {post_index} is greater than 40. All posts completed.")
        return None
        
    return post_index

def main():
    load_env()
    
    parser = argparse.ArgumentParser(description="Instagram Reels Auto Publisher")
    parser.add_argument("--idx", type=int, help="Override index to run manually")
    args = parser.parse_args()
    
    token = os.environ.get("FACEBOOK_USER_ACCESS_TOKEN") or os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN")
    ig_id = os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    
    if not token or not ig_id:
        print("Error: Missing FACEBOOK_USER_ACCESS_TOKEN or INSTAGRAM_BUSINESS_ACCOUNT_ID in environment!", file=sys.stderr)
        sys.exit(1)
        
    # Get index
    if args.idx is not None:
        target_idx = args.idx
        print(f"Manual Override: Processing Post {target_idx}")
    else:
        target_idx = get_scheduled_post_index()
        # TEMPORARY TEST OVERRIDE FOR JULY 3rd
        if target_idx is None:
            print("TEMPORARY TEST OVERRIDE: Defaulting to Post 22 for July 3rd test.")
            target_idx = 22
            
        # Set delay to 0 for quick verification during testing
        delay_sec = 0
        print(f"Test mode: Skipping random delay...")
        
    # Load assets from scheduled_posts.json
    db_path = "scheduled_posts.json"
    if os.path.exists(db_path):
        print(f"Loading post data from {db_path}...")
        with open(db_path, "r", encoding="utf-8") as f:
            scheduled_db = json.load(f)
            
        target_key = str(target_idx)
        if target_key not in scheduled_db:
            print(f"Error: Post index {target_idx} not found in {db_path}!", file=sys.stderr)
            sys.exit(1)
            
        post_data = scheduled_db[target_key]
        video_url = post_data["video_url"]
        thumb_url = post_data["thumb_url"]
        caption = post_data["caption"]
        
    else:
        # Fallback to publish_config.json or legacy hardcoded
        print(f"Warning: {db_path} not found. Checking fallback config...")
        config_path = "publish_config.json"
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            video_url = config_data["video_url"]
            thumb_url = config_data["thumb_url"]
            caption = config_data["caption"]
        else:
            print("Error: No scheduled database or configuration file found!", file=sys.stderr)
            sys.exit(1)
            
    print(f"\n==================== [Publishing Post {target_idx} to Instagram] ====================")
    print(f"Video URL: {video_url}")
    print(f"Thumb URL: {thumb_url}")
    
    # -------------------- INSTAGRAM PUBLISHING --------------------
    print("\n-------------------- [Publishing to Instagram Reels] --------------------")
    url_container = f"https://graph.facebook.com/v20.0/{ig_id}/media"
    payload = {
        "access_token": token,
        "media_type": "REELS",
        "video_url": video_url,
        "cover_url": thumb_url,
        "caption": caption,
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
        
        # Poll container status (max 15 minutes = 45 attempts * 20s)
        url_status = f"https://graph.facebook.com/v20.0/{container_id}?fields=status_code&access_token={token}"
        print("\nWaiting for Instagram to process the video (polling status_code)...")
        max_attempts = 45
        for attempt in range(max_attempts):
            time.sleep(20)
            status_resp = requests.get(url_status).json()
            status_code = status_resp.get("status_code", "UNKNOWN")
            print(f"Attempt {attempt+1}/{max_attempts}: status_code = {status_code}")
            
            if status_code == "FINISHED":
                print("Video processing finished by Instagram!")
                break
            elif status_code == "ERROR":
                print(f"Error: Instagram returned error status: {status_resp}", file=sys.stderr)
                sys.exit(1)
        else:
            print("Error: Video processing timed out on Instagram servers.", file=sys.stderr)
            sys.exit(1)
            
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
            print(f"\nSUCCESS! Post is now live on Instagram! Post ID: {resp_pub['id']}")
        else:
            print(f"\nError: Publishing container failed: {resp_pub}", file=sys.stderr)
            
    except Exception as e:
        print(f"Error during Instagram workflow: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
