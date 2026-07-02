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

def publish_to_facebook_page(video_url, caption):
    page_id = os.environ.get("FACEBOOK_PAGE_ID")
    token = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN")
    if not page_id or not token:
        print("Warning: Missing FACEBOOK_PAGE_ID or FACEBOOK_PAGE_ACCESS_TOKEN in env! Skipping Facebook publish.")
        return
        
    print("\n-------------------- [Publishing to Facebook Page Reels] --------------------")
    
    # Step 1: Start upload session
    url_start = f"https://graph.facebook.com/v20.0/{page_id}/video_reels"
    payload_start = {
        "upload_phase": "start",
        "access_token": token
    }
    try:
        resp_start = requests.post(url_start, data=payload_start).json()
        print("Facebook Start Session Response:", json.dumps(resp_start, indent=2))
        if "video_id" not in resp_start:
            print("Error: Failed to initialize Facebook video upload session.")
            return
        video_id = resp_start["video_id"]
        
        # Step 2: Upload file from public URL (Dropbox direct link)
        url_upload = f"https://rupload.facebook.com/video-reels-upload/{video_id}"
        headers_upload = {
            "Authorization": f"OAuth {token}",
            "file_url": video_url
        }
        print("Uploading video URL to Facebook Page...")
        resp_upload = requests.post(url_upload, headers=headers_upload).json()
        print("Facebook Upload Response:", json.dumps(resp_upload, indent=2))
        if not resp_upload.get("success", False):
            print("Error: Facebook upload failed.")
            return
            
        # Step 3: Finish and Publish
        url_finish = f"https://graph.facebook.com/v20.0/{page_id}/video_reels"
        payload_finish = {
            "upload_phase": "finish",
            "access_token": token,
            "video_id": video_id,
            "video_state": "PUBLISHED",
            "description": caption
        }
        print("Publishing Reel on Facebook Page...")
        resp_finish = requests.post(url_finish, data=payload_finish).json()
        print("Facebook Publish Response:", json.dumps(resp_finish, indent=2))
        if resp_finish.get("success", False) or "video_id" in resp_finish:
            print(f"SUCCESS! Post is now live on Facebook Page! Video ID: {video_id}")
        else:
            print(f"Error: Publishing on Facebook Page failed: {resp_finish}")
            
    except Exception as e:
        print(f"Error during Facebook Page upload/publish: {e}")

def main():
    load_env()
    
    parser = argparse.ArgumentParser(description="Instagram & Facebook Reels Auto Publisher")
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
        if target_idx is None:
            print("No post scheduled for this slot. Exiting cleanly.")
            sys.exit(0)
            
        # Apply anti-bot random delay (0 to 600 seconds)
        delay_sec = random.randint(0, 600)
        print(f"Sleeping for {delay_sec} seconds to prevent bot flags...")
        time.sleep(delay_sec)
        
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
            
    print(f"\n==================== [Publishing Post {target_idx}] ====================")
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
        
    # -------------------- FACEBOOK PUBLISHING --------------------
    try:
        publish_to_facebook_page(video_url, caption)
    except Exception as e:
        print(f"Error during Facebook workflow: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
