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

def get_dropbox_access_token(app_key, app_secret, refresh_token):
    print("Getting a fresh access token from Dropbox...")
    url = "https://api.dropboxapi.com/oauth2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    resp = requests.post(url, data=data, auth=(app_key, app_secret))
    resp.raise_for_status()
    return resp.json()["access_token"]

def upload_to_dropbox(file_path, dbx_path, access_token):
    print(f"Uploading {file_path} to Dropbox {dbx_path}...")
    url = "https://content.dropboxapi.com/2/files/upload"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Dropbox-API-Arg": json.dumps({
            "path": dbx_path,
            "mode": "overwrite",
            "autorename": False,
            "mute": False,
            "strict_conflict": False
        }),
        "Content-Type": "application/octet-stream"
    }
    
    with open(file_path, "rb") as f:
        file_data = f.read()
        
    resp = requests.post(url, headers=headers, data=file_data)
    if resp.status_code != 200:
        print("Dropbox upload failed with response:", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()

def get_or_create_shared_link(dbx_path, access_token):
    print(f"Creating shared link for {dbx_path}...")
    url = "https://api.dropboxapi.com/2/sharing/create_shared_link_with_settings"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "path": dbx_path,
        "settings": {
            "requested_visibility": "public"
        }
    }
    
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code == 200:
        link_url = resp.json()["url"]
        return link_url.replace("?dl=0", "&raw=1") if "?dl=0" in link_url else link_url + "&raw=1"
    else:
        error_data = resp.json()
        error_summary = error_data.get("error_summary", "")
        if "shared_link_already_exists" in error_summary or resp.status_code == 409:
            print("Shared link already exists. Fetching existing link...")
            url_list = "https://api.dropboxapi.com/2/sharing/list_shared_links"
            payload_list = {
                "path": dbx_path,
                "direct_only": True
            }
            resp_list = requests.post(url_list, headers=headers, json=payload_list)
            resp_list.raise_for_status()
            links = resp_list.json().get("links", [])
            if links:
                link_url = links[0]["url"]
                return link_url.replace("?dl=0", "&raw=1") if "?dl=0" in link_url else link_url + "&raw=1"
        resp.raise_for_status()

def get_current_affairs_index():
    ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    
    # Start Date: July 8, 2026
    start_date = datetime(2026, 7, 8)
    current_date = datetime(ist_now.year, ist_now.month, ist_now.day)
    
    days_diff = (current_date - start_date).days
    if days_diff < 0:
        print("Schedule has not started yet (before July 9th).")
        return None
        
    current_hour = ist_now.hour
    if not (5 <= current_hour < 7):
        print(f"Current hour {current_hour} is not the Morning Slot. Skipping.")
        return None
        
    post_index = days_diff + 1
    if post_index > 22:
        print(f"All 22 current affairs posts completed.")
        return None
        
    return f"post_{post_index:02d}"

def main():
    load_env()
    
    parser = argparse.ArgumentParser(description="Instagram Current Affairs Auto Publisher")
    parser.add_argument("--idx", type=str, help="Override index to run manually (e.g. post_01)")
    args = parser.parse_args()
    
    token = os.environ.get("FACEBOOK_USER_ACCESS_TOKEN") or os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN")
    ig_id = os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    
    if not token or not ig_id:
        print("Error: Missing Access Token or IG ID in environment!", file=sys.stderr)
        sys.exit(1)
        
    if args.idx is not None:
        target_key = args.idx
        print(f"Manual Override: Processing {target_key}")
    else:
        target_key = get_current_affairs_index()
        if target_key is None:
            print("No post scheduled for today. Exiting cleanly.")
            sys.exit(0)
            
        # Anti-bot delay
        delay_sec = random.randint(0, 600)
        print(f"Sleeping for {delay_sec} seconds to prevent bot flags...")
        time.sleep(delay_sec)
        
    db_path = "current_affairs_data.json"
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found!", file=sys.stderr)
        sys.exit(1)
        
    with open(db_path, "r", encoding="utf-8") as f:
        db = json.load(f)
        
    if target_key not in db:
        print(f"Error: {target_key} not found in {db_path}!", file=sys.stderr)
        sys.exit(1)
        
    post_data = db[target_key]
    
    print(f"\n==================== [Publishing {target_key} to Instagram] ====================")
    
    app_key = os.environ.get("DROPBOX_APP_KEY")
    app_secret = os.environ.get("DROPBOX_APP_SECRET")
    refresh_token = os.environ.get("DROPBOX_REFRESH_TOKEN")
    
    if not app_key or not app_secret or not refresh_token:
        print("Error: Missing Dropbox credentials in .env", file=sys.stderr)
        sys.exit(1)
        
    access_token = get_dropbox_access_token(app_key, app_secret, refresh_token)
    
    dbx_video_path = f"/current_affairs/{target_key}_video.mp4"
    dbx_thumb_path = f"/current_affairs/{target_key}_thumb.jpg"
    
    upload_to_dropbox(post_data["video_path"], dbx_video_path, access_token)
    upload_to_dropbox(post_data["thumb_path"], dbx_thumb_path, access_token)
    
    video_url = get_or_create_shared_link(dbx_video_path, access_token)
    thumb_url = get_or_create_shared_link(dbx_thumb_path, access_token)
    
    if not video_url or not thumb_url:
        print("Error: Failed to generate Dropbox links.", file=sys.stderr)
        sys.exit(1)
        
    # 2. Instagram Container API
    print("\n-------------------- [Uploading to Instagram Reels] --------------------")
    url_container = f"https://graph.facebook.com/v20.0/{ig_id}/media"
    payload = {
        "access_token": token,
        "media_type": "REELS",
        "video_url": video_url,
        "cover_url": thumb_url,
        "caption": post_data["caption"],
        "share_to_feed": "true"
    }
    
    try:
        resp_c = requests.post(url_container, data=payload).json()
        if "id" not in resp_c:
            print("Error: Failed to create Instagram container.", resp_c, file=sys.stderr)
            sys.exit(1)
            
        container_id = resp_c["id"]
        print(f"Instagram Container created. ID: {container_id}")
        
        # 3. STRICT POLLING: Wait for Instagram to process the video
        url_status = f"https://graph.facebook.com/v20.0/{container_id}?fields=status_code&access_token={token}"
        print("\nWaiting for Instagram to process the video (Strict Polling)...")
        max_attempts = 45 # 15 minutes
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
            
        # 4. Publish Live
        url_publish = f"https://graph.facebook.com/v20.0/{ig_id}/media_publish"
        payload_pub = {
            "access_token": token,
            "creation_id": container_id
        }
        
        print("\nPublishing media container live on Instagram...")
        resp_pub = requests.post(url_publish, data=payload_pub).json()
        
        if "id" in resp_pub:
            live_media_id = resp_pub["id"]
            print(f"\nSUCCESS! Post is now live on Instagram! Post ID: {live_media_id}")
            
            # 5. The Single Combined Comment
            print("\n-------------------- [Posting Combined Pinned Comment] --------------------")
            combined_comment = f"{post_data['fun_fact']}\n.\n.\n{post_data['cta_question']}\n.\n.\nFollow @erased.record for more daily insights."
            
            comment_url = f"https://graph.facebook.com/v20.0/{live_media_id}/comments"
            comment_payload = {
                "message": combined_comment,
                "access_token": token
            }
            
            comment_resp = requests.post(comment_url, data=comment_payload).json()
            if "id" in comment_resp:
                print(f"SUCCESS! Comment posted on Instagram. Comment ID: {comment_resp['id']}")
            else:
                print(f"Error: Failed to post comment on Instagram: {comment_resp}", file=sys.stderr)
                
        else:
            print(f"\nError: Publishing container failed: {resp_pub}", file=sys.stderr)
            
    except Exception as e:
        print(f"Error during Instagram workflow: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
