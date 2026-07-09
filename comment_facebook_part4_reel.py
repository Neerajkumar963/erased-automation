import os
import json
import requests
import time
import sys
from bs4 import BeautifulSoup
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

def get_todays_target():
    ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    start_date = datetime(2026, 7, 9)
    current_date = datetime(ist_now.year, ist_now.month, ist_now.day)
    
    days_diff = (current_date - start_date).days
    if days_diff < 0 or days_diff > 11:
        return None, None
        
    target_index = days_diff + 2 # offset by 2 because 0 and 1 were July 7 and 8
    target_index_str = str(target_index)
    
    with open('archive/old_databases/facebook_part4_scheduled_ids.json', 'r', encoding='utf-8') as f:
        fb_db = json.load(f)
        
    if target_index_str not in fb_db:
        return None, None
        
    fb_data = fb_db[target_index_str]
    filename = fb_data.get('filename') # e.g. post_03_charles_darwin.mp4
    video_id = fb_data.get('video_id')
    
    return filename, video_id

def extract_comment_from_html(filename):
    # e.g. post_03_charles_darwin.mp4 -> post_03_charles_darwin
    post_id_html = filename.replace('.mp4', '')
    
    with open('formats/hidden_family_tragedies_part4.html', 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
        
    post_div = soup.find('div', id=post_id_html)
    if not post_div:
        return None
        
    story_div = post_div.find('div', class_='story')
    fun_fact_div = post_div.find('div', class_='fun-fact')
    cta_div = post_div.find('div', class_='cta')
    
    if not story_div or not fun_fact_div or not cta_div:
        return None
        
    # Replace <br> with \n
    for br in story_div.find_all('br'):
        br.replace_with('\n')
        
    story = story_div.get_text().strip()
    fun_fact = fun_fact_div.get_text(strip=True).replace("Fun Fact:", "Fun Fact:")
    cta = cta_div.get_text(strip=True)
    
    combined_comment = f"{story}\n.\n.\n{fun_fact}\n.\n.\n{cta}\nAnd Follow @erased.record for more hidden histories!"
    return combined_comment

def main():
    load_env()
    token = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN")
    
    if not token:
        print("Error: Missing FACEBOOK_PAGE_ACCESS_TOKEN!")
        sys.exit(1)
        
    filename, video_id = get_todays_target()
    if not filename or not video_id:
        print("No Part 4 Reel scheduled for today or index out of bounds. Exiting.")
        sys.exit(0)
        
    pinned_comment = extract_comment_from_html(filename)
    if not pinned_comment:
        print(f"Error: Could not extract pinned comment from HTML for {filename}.")
        sys.exit(1)
        
    print(f"\n==================== [Watchdog: FB Part 4 Reel '{filename}'] ====================")
    print(f"Target Video ID: {video_id}")
    
    # Poll API for status
    status_url = f"https://graph.facebook.com/v20.0/{video_id}?fields=status,published&access_token={token}"
    
    max_attempts = 30 # 15 minutes max
    is_published = False
    
    print("\nPolling Facebook API to verify video is published...")
    for attempt in range(max_attempts):
        print(f"  [Poll {attempt+1}/{max_attempts}] Checking status...")
        resp = requests.get(status_url).json()
        
        # Check if published
        if resp.get("published") == True:
            is_published = True
            print(f"  -> SUCCESS! Video is now PUBLISHED on Facebook.")
            break
            
        time.sleep(30)
    else:
        print("Error: Timed out. Video never became 'published' within 15 minutes.")
        sys.exit(1)
        
    # Post the comment
    print("\n-------------------- [Posting Combined Pinned Comment] --------------------")
    comment_url = f"https://graph.facebook.com/v20.0/{video_id}/comments"
    payload = {
        "message": pinned_comment,
        "access_token": token
    }
    
    comment_resp = requests.post(comment_url, data=payload).json()
    if "id" in comment_resp:
        print(f"SUCCESS! Comment posted on Facebook. Comment ID: {comment_resp['id']}")
    else:
        print(f"Error posting comment: {comment_resp}")

if __name__ == "__main__":
    main()
