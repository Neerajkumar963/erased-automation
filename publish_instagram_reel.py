import requests
import json
import time
import os
import sys

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

def main():
    # Read variables from environment (will be set by GitHub Secrets)
    token = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN")
    ig_id = os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    
    if not token or not ig_id:
        print("Error: Missing FACEBOOK_PAGE_ACCESS_TOKEN or INSTAGRAM_BUSINESS_ACCOUNT_ID in environment!", file=sys.stderr)
        sys.exit(1)
        
    video_path = "outputs/erased_post_21_video.mp4"
    thumb_path = "outputs/erased_post_21_thumb.jpg"
    
    # 1. Upload files to temporary hosting
    video_url = upload_to_tmpfiles(video_path)
    thumb_url = upload_to_tmpfiles(thumb_path)
    
    if not video_url or not thumb_url:
        print("Error: Temporary hosting upload failed.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Uploaded Video URL:     {video_url}")
    print(f"Uploaded Thumbnail URL: {thumb_url}")
    
    caption = (
        "In the 1970s, Nestle marketed infant formula in developing countries with sales reps "
        "dressed as nurses and free hospital samples — in regions where formula prepared with "
        "contaminated water caused infant illness and death.\n\n"
        "The WHO International Code of Marketing of Breast-milk Substitutes was created in 1981 "
        "specifically in response. Nestle was the only company to vote against it.\n\n"
        "Investigations through the 2010s and 2020s have continued to find Code violations by "
        "infant formula companies worldwide.\n\n"
        "Source: WHO IBFAN Code monitoring reports, original Nestle boycott documentation. Follow.\n\n"
        "#Nestle #BabyFormula #HiddenHistory #CorporateFraud #TrueHistory #ConsumerSafety #WHO"
    )
    
    # 2. Create Instagram media container (Immediate publish container)
    url_container = f"https://graph.facebook.com/v20.0/{ig_id}/media"
    payload = {
        "access_token": token,
        "media_type": "REELS",
        "video_url": video_url,
        "cover_url": thumb_url,
        "caption": caption,
        "share_to_feed": "true"
    }
    
    print("\nCreating Instagram Media Container...")
    try:
        resp_c = requests.post(url_container, data=payload).json()
        print("Container API Response:")
        print(json.dumps(resp_c, indent=2))
        
        if "id" not in resp_c:
            print("Error: Failed to create container.", file=sys.stderr)
            sys.exit(1)
            
        container_id = resp_c["id"]
        print(f"Container created successfully. ID: {container_id}")
        
        # 3. Poll container status
        url_status = f"https://graph.facebook.com/v20.0/{container_id}?fields=status_code&access_token={token}"
        
        print("\nWaiting for Instagram to process the video (polling status_code)...")
        max_attempts = 30
        for attempt in range(max_attempts):
            time.sleep(10)
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
            
        # 4. Publish the media container live
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
            print(f"\nSUCCESS! Post is now live on Instagram!")
            print(f"Instagram Post ID: {resp_pub['id']}")
        else:
            print(f"\nError: Publishing container failed: {resp_pub}", file=sys.stderr)
            
    except Exception as e:
        print(f"Error during Instagram workflow: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
