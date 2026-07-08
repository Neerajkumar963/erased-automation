import os
import json
import requests
import time
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

def schedule_reel(page_id, token, post_data, target_timestamp, index_key):
    print(f"\n==================== [Scheduling {index_key} on Facebook Page] ====================")
    
    local_video_path = post_data["video_path"]
    local_thumb_path = post_data["thumb_path"]
    caption = post_data["caption"]
    
    if not os.path.exists(local_video_path):
        print(f"Error: Local video file not found at {local_video_path}.")
        return False
        
    # 1. Start upload session
    url_start = f"https://graph.facebook.com/v20.0/{page_id}/video_reels"
    payload_start = {
        "upload_phase": "start",
        "access_token": token
    }
    
    resp_start = requests.post(url_start, data=payload_start).json()
    if "video_id" not in resp_start:
        print(f"Error: Failed to start upload session. Response: {resp_start}")
        return False
        
    video_id = resp_start["video_id"]
    upload_url = resp_start.get("upload_url", f"https://rupload.facebook.com/video-reels/{video_id}")
    print(f"Session started. Video ID: {video_id}")
    
    # 2. Upload video directly using binary data
    file_size = os.path.getsize(local_video_path)
    headers_upload = {
        "Authorization": f"OAuth {token}",
        "offset": "0",
        "file_size": str(file_size)
    }
    print(f"Uploading local video binary ({file_size/(1024*1024):.2f} MB) directly to Facebook...")
    with open(local_video_path, "rb") as f_vid:
        resp_upload = requests.post(upload_url, headers=headers_upload, data=f_vid).json()
        
    if not resp_upload.get("success", False) and "video_id" not in resp_upload and not isinstance(resp_upload, list):
        print(f"Error: Facebook upload call failed. Response: {resp_upload}")
        return False
        
    # 3. Finish and Schedule
    url_finish = f"https://graph.facebook.com/v20.0/{page_id}/video_reels"
    payload_finish = {
        "upload_phase": "finish",
        "access_token": token,
        "video_id": video_id,
        "video_state": "SCHEDULED",
        "scheduled_publish_time": target_timestamp,
        "description": caption
    }
    
    target_ist_str = datetime.fromtimestamp(target_timestamp, timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d %H:%M:%S")
    print(f"Sending publish finish request for IST time: {target_ist_str}...")
    
    resp_finish = requests.post(url_finish, data=payload_finish).json()
    if not (resp_finish.get("success", False) or "video_id" in resp_finish):
        print(f"Error: Finalizing schedule failed: {resp_finish}")
        return False
        
    # 3.5 STRICT POLLING: Poll for Video Status before uploading thumbnail
    print(f"Waiting for Facebook to finish processing the video before uploading thumbnail (Strict Polling)...")
    status_url = f"https://graph.facebook.com/v20.0/{video_id}?fields=status&access_token={token}"
    max_attempts = 30 # Up to 5 minutes
    for attempt in range(max_attempts):
        status_resp = requests.get(status_url).json()
        vid_status = status_resp.get("status", {}).get("video_status", "unknown")
        print(f"  [Poll {attempt+1}/{max_attempts}] Video status is '{vid_status}'")
        if vid_status.lower() == "ready":
            print("  Video is READY!")
            break
        time.sleep(10)
    else:
        print("  Error: Video processing did not finish in time. Exiting to prevent blind thumbnail upload.")
        return False
        
    # 4. Upload thumbnail properly via /{video_id}/thumbnails
    if os.path.exists(local_thumb_path):
        print(f"Uploading local thumbnail {local_thumb_path}...")
        with open(local_thumb_path, "rb") as f_thumb:
            thumb_upload_resp = requests.post(
                f"https://graph.facebook.com/v20.0/{video_id}/thumbnails",
                params={"access_token": token, "is_preferred": "true"},
                files={"source": ("thumbnail.jpg", f_thumb, "image/jpeg")}
            ).json()
            if thumb_upload_resp.get("success"):
                print("  Thumbnail uploaded successfully!")
            else:
                print(f"  Error uploading thumbnail: {thumb_upload_resp}")
    else:
        print(f"  Error: Thumbnail not found at {local_thumb_path}.")
        
    return True

def main():
    load_env()
    page_id = os.environ.get("FACEBOOK_PAGE_ID")
    token = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN")
    
    if not page_id or not token:
        print("Missing FACEBOOK_PAGE_ID or FACEBOOK_PAGE_ACCESS_TOKEN!")
        return
        
    with open("current_affairs_data.json", "r", encoding="utf-8") as f:
        db = json.load(f)
        
    ist = timezone(timedelta(hours=5, minutes=30))
    start_date = datetime(2026, 7, 8) # Start July 8th
    
    success_count = 0
    for i in range(22):
        key = f"post_{i+1:02d}"
        if key not in db:
            continue
            
        target_date = start_date + timedelta(days=i)
        target_time = target_date.replace(hour=5, minute=30, second=0, microsecond=0, tzinfo=ist)
        target_timestamp = int(target_time.timestamp())
        
        success = schedule_reel(page_id, token, db[key], target_timestamp, key)
        if success:
            success_count += 1
            
        time.sleep(5) # Delay between posts
        
    print(f"\nSuccessfully scheduled {success_count} / 22 Current Affairs posts on Facebook.")

if __name__ == "__main__":
    main()
