import os
import time
import requests
import json
from datetime import datetime, timezone, timedelta

def load_env(env_path=".env"):
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip().strip('"').strip("'")

def get_queue_for_current_time():
    ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    hour = ist_now.hour
    
    print(f"Current IST Time: {ist_now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if hour == 5: return "current_affairs"
    if hour == 11: return "family_tragedies"
    if hour == 13: return "us_history"
    if hour == 19: return "family_tragedies"
    if hour == 22: return "us_history"
    
    return None

def publish_to_instagram(video_url, caption):
    access_token = os.environ.get("FACEBOOK_USER_ACCESS_TOKEN")
    ig_user_id = os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    
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
        return None
        
    container_id = res_data['id']
    print(f"Container ID: {container_id}")
    
    print("\n[Step 2] Waiting for Instagram to process the video...")
    status_url = f"https://graph.facebook.com/v19.0/{container_id}?fields=status_code&access_token={access_token}"
    
    for _ in range(20):
        time.sleep(5)
        status = requests.get(status_url).json().get('status_code', 'UNKNOWN')
        print(f"Checking status... [{status}]")
        if status == 'FINISHED':
            break
        elif status == 'ERROR':
            print("Instagram failed to process the video.")
            return None
            
    print("\n[Step 3] Publishing to Instagram feed...")
    pub_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish"
    pub_res = requests.post(pub_url, data={'creation_id': container_id, 'access_token': access_token})
    pub_data = pub_res.json()
    
    if 'id' in pub_data:
        print(f"Success! Reel published ID: {pub_data['id']}")
        return pub_data['id']
    else:
        print(f"Publish Failed: {pub_data}")
        return None

def post_comment(media_id, text):
    print("\n[Step 4] Posting the Pinned Comment...")
    access_token = os.environ.get("FACEBOOK_USER_ACCESS_TOKEN")
    url = f"https://graph.facebook.com/v19.0/{media_id}/comments"
    payload = {
        'message': text,
        'access_token': access_token
    }
    res = requests.post(url, data=payload)
    data = res.json()
    if 'id' in data:
        print(f"Success! Comment posted ID: {data['id']}")
        return True
    else:
        print(f"Comment Failed: {data}")
        return False

def main():
    load_env()
    
    queue_name = get_queue_for_current_time()
    if not queue_name:
        print("No post scheduled for this hour. Exiting cleanly.")
        return
        
    print(f"Target Queue for this hour: {queue_name}")
    
    db_path = "master_monthly_schedule.json"
    with open(db_path, "r", encoding="utf-8") as f:
        db = json.load(f)
        
    queue = db.get("queues", {}).get(queue_name, [])
    if not queue:
        print(f"WARNING: Queue '{queue_name}' is empty! Need to generate more content.")
        return
        
    # POP the first item
    post = queue.pop(0)
    print(f"Popped item from {queue_name} queue.")
    
    media_id = publish_to_instagram(post['dropbox_url'], post['caption'])
    
    if media_id:
        if post.get('pinned_comment'):
            time.sleep(5) # Wait for propagation
            post_comment(media_id, post['pinned_comment'])
            
        # Only save back to DB if publish was successful, so we don't lose the video on failure!
        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=4)
        print("Database updated. Item consumed successfully.")
    else:
        print("Publish failed. Item has NOT been consumed from the queue.")

if __name__ == "__main__":
    main()
