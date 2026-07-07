import argparse
import json
import os
import re
import cv2
import numpy as np
import base64
import subprocess
import sys
import urllib.request
import urllib.parse
import requests
from PIL import Image, ImageDraw, ImageFont

# Add scripts directory to path to import modules
sys.path.append(os.path.join(os.path.dirname(__file__), "scripts"))
from renderer import parse_text, layout_paragraph, PALETTE

def load_env(env_path=".env"):
    """
    Load environment variables from the local .env file
    """
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        key, val = line.split("=", 1)
                        os.environ[key.strip()] = val.strip().strip('"').strip("'")

def clean_text(text):
    """
    Cleans markdown highlights and formatting from the text so it reads naturally:
    - [word](color) -> word
    - **bold** -> bold
    """
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    return text

def parse_elevenlabs_alignment(alignment, speed_factor=1.12):
    characters = alignment["characters"]
    starts = alignment["character_start_times_seconds"]
    ends = alignment["character_end_times_seconds"]
    
    words = []
    current_word_chars = []
    word_start = None
    
    for char, start, end in zip(characters, starts, ends):
        if char.isspace():
            if current_word_chars:
                word_str = "".join(current_word_chars)
                words.append({
                    "word": word_str,
                    "start": word_start / speed_factor,
                    "end": ends_prev / speed_factor
                })
                current_word_chars = []
                word_start = None
        else:
            if not current_word_chars:
                word_start = start
            current_word_chars.append(char)
            ends_prev = end
            
    if current_word_chars:
        word_str = "".join(current_word_chars)
        words.append({
            "word": word_str,
            "start": word_start / speed_factor,
            "end": ends_prev / speed_factor
        })
        
    return words

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
    print("Upload completed successfully!")
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
        print(f"Created shared link: {link_url}")
        return link_url
    else:
        # Check if it failed because it already exists
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
                print(f"Found existing shared link: {link_url}")
                return link_url
        
        # If it failed for some other reason, raise
        resp.raise_for_status()

def main():
    load_env()
    
    parser = argparse.ArgumentParser(
        description="ERASED Automation - Dynamic Subtitle Highlight Video Generator"
    )
    parser.add_argument("--input-file", required=True, help="Path to the JSON batch file (e.g. batch_29_40.json)")
    parser.add_argument("--idx", required=True, help="Post index to generate voiceover for (e.g. 29, 29-35, 29,32, or all)")
    parser.add_argument("--start-idx", type=int, default=29, help="Numbering start index of the batch (default: 29)")
    parser.add_argument("--voice-id", default="onwK4e9ZLuTAKqWW03F9", help="ElevenLabs Voice ID (default: Daniel)")
    parser.add_argument("--output-dir", default="outputs", help="Directory where generated assets are saved")
    parser.add_argument("--name", default="erased_post", help="Base name prefix")
    
    args = parser.parse_args()
    
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        print("Error: ELEVENLABS_API_KEY is not set in the .env file!", file=sys.stderr)
        sys.exit(1)
        
    if not os.path.exists(args.input_file):
        print(f"Error: Input file {args.input_file} not found!", file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(args.input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON file: {e}", file=sys.stderr)
        sys.exit(1)
        
    # Resolve indices to process
    idx_str = args.idx.strip().lower()
    target_indices = []
    
    if idx_str == "all":
        target_indices = list(range(args.start_idx, args.start_idx + len(data)))
    elif "-" in idx_str:
        try:
            start_val, end_val = map(int, idx_str.split("-"))
            target_indices = list(range(start_val, end_val + 1))
        except ValueError:
            print("Error: Invalid range format. Use e.g. 29-35", file=sys.stderr)
            sys.exit(1)
    elif "," in idx_str:
        try:
            target_indices = list(map(int, idx_str.split(",")))
        except ValueError:
            print("Error: Invalid comma list format. Use e.g. 29,32,35", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            target_indices = [int(idx_str)]
        except ValueError:
            print("Error: Invalid index format. Use a single number, range (29-35), comma list (29,32) or 'all'", file=sys.stderr)
            sys.exit(1)
            
    print(f"\nResolved indices to process: {target_indices}")
    
    ffmpeg_path = os.path.abspath("ffmpeg.exe")
    if not os.path.exists(ffmpeg_path):
        print("Error: ffmpeg.exe was not found in the workspace root!", file=sys.stderr)
        sys.exit(1)
        
    for i, current_idx in enumerate(target_indices):
        array_offset = current_idx - args.start_idx
        if array_offset < 0 or array_offset >= len(data):
            print(f"\nWarning: Post index {current_idx} is out of bounds for the batch! Skipping.", file=sys.stderr)
            continue
            
        post = data[array_offset]
        raw_body = post.get("body")
        heading = post.get("heading")
        if not raw_body or not heading:
            print(f"\nWarning: Post {current_idx} does not contain complete body/heading! Skipping.", file=sys.stderr)
            continue
            
        narration_text = clean_text(raw_body)
        print(f"\n======================================== [Post {current_idx}] ========================================")
        print(f"Target text for Post {current_idx} narration:")
        print("-" * 50)
        print(narration_text)
        print("-" * 50)
        
        # Add rate limit delay if processing multiple posts
        if i > 0:
            import time
            print("Waiting 4 seconds to respect API rate limits...")
            time.sleep(4.0)
            
        # 1. Fetch Audio + Timestamps from ElevenLabs using optimized turbo model
        print(f"Generating voiceover using Voice ID: {args.voice_id} (eleven_turbo_v2)...")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{args.voice_id}/with-timestamps"
        
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "text": narration_text,
            "model_id": "eleven_turbo_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        
        os.makedirs("scratch", exist_ok=True)
        temp_audio_path = os.path.join("scratch", f"voiceover_{current_idx}.mp3")
        temp_json_path = os.path.join("scratch", f"voiceover_{current_idx}_alignment.json")
        
        if os.path.exists(temp_audio_path) and os.path.exists(temp_json_path):
            print(f"Found cached audio and alignment for Post {current_idx}. Skipping API call to save credits!")
            with open(temp_json_path, "r", encoding="utf-8") as f:
                alignment_data = json.load(f)
        else:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req) as resp_raw:
                    resp = json.loads(resp_raw.read().decode("utf-8"))
                # Save raw audio file
                audio_bytes = base64.b64decode(resp["audio_base64"])
                with open(temp_audio_path, "wb") as f:
                    f.write(audio_bytes)
                # Save alignment data
                alignment_data = resp["alignment"]
                with open(temp_json_path, "w", encoding="utf-8") as f:
                    json.dump(alignment_data, f)
                print(f"Saved raw voiceover audio and alignment to: scratch/")
            except Exception as e:
                print(f"Error generating voiceover for Post {current_idx}: {e}", file=sys.stderr)
                continue
            
        # Parse alignment timings (1.0 speed for mathematically perfect sync during render)
        spoken_words = parse_elevenlabs_alignment(alignment_data, speed_factor=1.0)
        duration = spoken_words[-1]["end"] + 1.0 # 1s buffer at the end
        fps = 30
        total_frames = int(duration * fps)
        
        # 2. Prepare audio (No speed up here, we speed up everything at the end)
        fast_audio_path = os.path.join("scratch", f"voiceover_{current_idx}_fast.mp3")
        if os.path.exists(fast_audio_path):
            try:
                os.remove(fast_audio_path)
            except Exception:
                pass
        cmd_audio = f'"{ffmpeg_path}" -y -i "{temp_audio_path}" -filter:a "volume=2.0" "{fast_audio_path}"'
        subprocess.run(cmd_audio, shell=True, check=True)
        
        # 3. Calculate Layout EXACTLY like renderer.py to sync with pre-rendered card
        fonts = {}
        
        # Calculate Title Height to find Body Start Y
        title_font_size = 120
        while True:
            fonts["anton"] = ImageFont.truetype(os.path.join("fonts", "Anton-Regular.ttf"), title_font_size)
            title_lines = layout_paragraph(heading.upper(), "anton", fonts, 1592)
            title_font_height = int(title_font_size * (108 / 120))
            title_leading = int(title_font_size * (129 / 120))
            h = (len(title_lines) - 1) * title_leading + title_font_height
            if h <= 450 or title_font_size <= 70:
                break
            title_font_size -= 5
            
        title_end_y = 347
        for i, para_lines in enumerate([title_lines]):
            for j, line in enumerate(para_lines):
                if i == 0 and j == len(para_lines) - 1:
                    title_end_y += title_font_height
                else:
                    if j == len(para_lines) - 1:
                        title_end_y += title_font_height
                    else:
                        title_end_y += title_leading

        # Calculate Body Layout
        body_font_size = 68
        raw_paragraphs = raw_body.split("\n\n")
        
        while True:
            fonts["poppins_reg"] = ImageFont.truetype(os.path.join("fonts", "Poppins-Regular.ttf"), body_font_size)
            fonts["poppins_bold"] = ImageFont.truetype(os.path.join("fonts", "Poppins-Bold.ttf"), body_font_size)
            
            body_para_lines = [layout_paragraph(para, "poppins", fonts, 1592) for para in raw_paragraphs if para.strip()]
            
            body_font_height = int(body_font_size * (66 / 68))
            body_leading = int(body_font_size * (94 / 68))
            body_para_gap = int(body_font_size * (62 / 68))
            
            total_body_h = 0
            for i, para in enumerate(body_para_lines):
                para_h = (len(para) - 1) * body_leading + body_font_height
                total_body_h += para_h
                if i > 0:
                    total_body_h += body_para_gap
                    
            body_start_y = title_end_y + 70
            if body_start_y + total_body_h <= 2120 or body_font_size <= 40:
                break
            body_font_size -= 4

        # Build char_timings from alignment_data
        characters = alignment_data['characters']
        starts = alignment_data['character_start_times_seconds']
        ends = alignment_data['character_end_times_seconds']
        char_timings = [{'char': c, 'start': s, 'end': e} for c, s, e in zip(characters, starts, ends)]

        # Map spoken words to layout tokens using Character-to-Character mapping
        char_ptr = 0
        words_layout_data = []
        
        current_y = body_start_y
        for i, para_lines in enumerate(body_para_lines):
            for j, line in enumerate(para_lines):
                current_x = 100
                for token, font, color, width in line:
                    clean_tok = re.sub(r'[^\w]', '', token.lower())
                    
                    x1 = current_x
                    y1 = current_y
                    x2 = current_x + width
                    y2 = current_y + body_font_height
                    
                    word_timing = None
                    if clean_tok:
                        match_idx = 0
                        start_time = None
                        end_time = None
                        temp_ptr = char_ptr
                        
                        while temp_ptr < len(char_timings) and match_idx < len(clean_tok):
                            ct = char_timings[temp_ptr]
                            clean_c = re.sub(r'[^\w]', '', ct['char'].lower())
                            
                            if clean_c:
                                if clean_c == clean_tok[match_idx]:
                                    if match_idx == 0:
                                        start_time = ct['start']
                                    end_time = ct['end']
                                    match_idx += 1
                            temp_ptr += 1
                            
                        if match_idx == len(clean_tok):
                            char_ptr = temp_ptr
                            word_timing = {"start": start_time, "end": end_time}
                            
                    words_layout_data.append({
                        "token": token,
                        "font": font,
                        "color": color,
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2,
                        "ascent": font.getmetrics()[0],
                        "timing": word_timing
                    })
                    current_x += width
                    
                if i == len(body_para_lines) - 1 and j == len(para_lines) - 1:
                    current_y += body_font_height
                else:
                    if j == len(para_lines) - 1:
                        current_y += body_font_height + body_para_gap
                    else:
                        current_y += body_leading

        # 4. Render Video Frames
        temp_video_raw = os.path.join("scratch", f"temp_video_{current_idx}.mp4")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video_writer = cv2.VideoWriter(temp_video_raw, fourcc, fps, (1792, 2400))
        
        # Load the already perfectly rendered content card to use as base canvas
        card_img_path = os.path.join(args.output_dir, f"{args.name}_{current_idx:02d}_card.jpg")
        if os.path.exists(card_img_path):
            base_img = Image.open(card_img_path).convert("RGB")
        else:
            print(f"Error: Card image {card_img_path} not found! Run generate.py first.", file=sys.stderr)
            continue
            
        # Write frames to cv2 Writer
        print("Rendering frames...")
        for frame_idx in range(total_frames):
            t = frame_idx / float(fps)
            frame_img = base_img.copy()
            draw = ImageDraw.Draw(frame_img)
            
            for item in words_layout_data:
                tok = item["token"]
                font = item["font"]
                x1, y1, x2, y2 = item["x1"], item["y1"], item["x2"], item["y2"]
                timing = item["timing"]
                ascent = item["ascent"]
                
                # Dynamic Highlight Sync
                if timing and timing["start"] <= t <= timing["end"]:
                    tok_stripped = tok.rstrip()
                    stripped_width = font.getlength(tok_stripped)
                    x2_highlight = x1 + stripped_width
                    
                    draw.rounded_rectangle(
                        [x1 - 8, y1 - 4, x2_highlight + 8, y2 + 8],
                        radius=12,
                        fill=(254, 243, 199) # soft light amber (#fef3c7)
                    )
                    # Text in bold amber, using baseline anchor ("ls") exactly like renderer.py
                    draw.text((x1, y1 + ascent), tok, font=font, fill=(217, 119, 6), anchor="ls")
                    
            # BGR for OpenCV
            cv_frame = cv2.cvtColor(np.array(frame_img), cv2.COLOR_RGB2BGR)
            video_writer.write(cv_frame)
            
        video_writer.release()
        
        # 5. Merge Video, Sped-up voiceover, and Background music
        video_output = os.path.join(args.output_dir, f"{args.name}_{current_idx:02d}_video.mp4")
        if os.path.exists(video_output):
            try:
                os.remove(video_output)
            except Exception:
                pass
                
        # 5. Merge Audio, Video, and Background Music
        bg_music = "music/audio.mp3"
        if os.path.exists(bg_music):
            # 5. Merge and Speed Up final Video + Audio
            cmd_merge = (
                f'"{ffmpeg_path}" -y -i "{temp_video_raw}" -i "{fast_audio_path}" -i "{bg_music}" '
                f'-filter_complex "[0:v]setpts=PTS/1.12[v];[1:a]volume=1.0,atempo=1.12[a1];[2:a]volume=0.08[a2];[a1][a2]amix=inputs=2:duration=first[a]" '
                f'-map "[v]" -map "[a]" -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest "{video_output}"'
            )
        else:
            print("Warning: music/audio.mp3 not found. Merging only voiceover...")
            cmd_merge = f'"{ffmpeg_path}" -y -i "{temp_video_raw}" -i "{fast_audio_path}" -c:v libx264 -pix_fmt yuv420p -c:a aac "{video_output}"'
            
        try:
            result = subprocess.run(cmd_merge, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                print(f"Success! Perfect-sync highlight video for Post {current_idx} saved at: {os.path.abspath(video_output)}")
            else:
                print(f"FFmpeg Compilation Error for Post {current_idx}: {result.stderr.decode('utf-8', errors='ignore')}", file=sys.stderr)
        except Exception as e:
            print(f"Compilation process failed for Post {current_idx}: {e}", file=sys.stderr)
            
        # Clean up temp files
        try:
            os.remove(temp_video_raw)
            # We NO LONGER delete temp_audio_path and fast_audio_path so they can be cached!
        except Exception:
            pass
            
        # 6. Upload generated assets to Dropbox and create publish configuration
        app_key = os.environ.get("DROPBOX_APP_KEY")
        app_secret = os.environ.get("DROPBOX_APP_SECRET")
        refresh_token = os.environ.get("DROPBOX_REFRESH_TOKEN")
        
        if app_key and app_secret and refresh_token:
            print("\nDropbox configuration found. Uploading generated assets to Dropbox...")
            try:
                # Get access token
                access_token = get_dropbox_access_token(app_key, app_secret, refresh_token)
                
                # Upload video
                dbx_video_path = f"/{args.name}_{current_idx}_video.mp4"
                upload_to_dropbox(video_output, dbx_video_path, access_token)
                video_shared_link = get_or_create_shared_link(dbx_video_path, access_token)
                video_direct_url = video_shared_link.replace("dl=0", "dl=1")
                
                # Upload thumbnail if it exists
                thumb_output = os.path.join(args.output_dir, f"{args.name}_{current_idx}_thumb.jpg")
                thumb_direct_url = ""
                if os.path.exists(thumb_output):
                    dbx_thumb_path = f"/{args.name}_{current_idx}_thumb.jpg"
                    upload_to_dropbox(thumb_output, dbx_thumb_path, access_token)
                    thumb_shared_link = get_or_create_shared_link(dbx_thumb_path, access_token)
                    thumb_direct_url = thumb_shared_link.replace("dl=0", "dl=1")
                else:
                    print(f"Warning: Thumbnail file {thumb_output} not found. Skipping thumbnail upload.")
                
                # Create cleaned caption (with heading uppercase and body hashtags)
                clean_heading = clean_text(heading).upper()
                clean_body = clean_text(raw_body)
                caption = f"{clean_heading}\n\n{clean_body}\n\n#HiddenHistory #TrueHistory #HistoryFacts #HistoryReels #Automation"
                
                # Write publish_config.json
                publish_config = {
                    "post_index": current_idx,
                    "video_url": video_direct_url,
                    "thumb_url": thumb_direct_url,
                    "caption": caption
                }
                
                config_path = "publish_config.json"
                with open(config_path, "w", encoding="utf-8") as cf:
                    json.dump(publish_config, cf, indent=2, ensure_ascii=False)
                print(f"Success! Configuration written successfully to: {os.path.abspath(config_path)}")
                
            except Exception as e:
                print(f"Warning: Dropbox upload or publish config creation failed: {e}", file=sys.stderr)
            
    print("\n========================================")
    print("All perfect-sync voiceover videos compiled successfully!")
    print("========================================")

if __name__ == "__main__":
    main()
