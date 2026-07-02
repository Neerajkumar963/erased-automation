import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.parse

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
    # Replace markdown links: [text](color) -> text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Replace bold indicators: **text** -> text
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    return text

def main():
    load_env()
    
    parser = argparse.ArgumentParser(
        description="ERASED Automation - On-Demand Voiceover Video Generator"
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
    
    for i, current_idx in enumerate(target_indices):
        array_offset = current_idx - args.start_idx
        if array_offset < 0 or array_offset >= len(data):
            print(f"\nWarning: Post index {current_idx} is out of bounds for the batch! Skipping.", file=sys.stderr)
            continue
            
        post = data[array_offset]
        raw_body = post.get("body")
        if not raw_body:
            print(f"\nWarning: Post {current_idx} does not contain a body paragraph! Skipping.", file=sys.stderr)
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
            
        # 1. Fetch Audio from ElevenLabs
        print(f"Generating voiceover using Voice ID: {args.voice_id}...")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{args.voice_id}"
        
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "accept": "audio/mpeg"
        }
        
        payload = {
            "text": narration_text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        
        os.makedirs("scratch", exist_ok=True)
        temp_audio_path = os.path.join("scratch", f"voiceover_{current_idx}.mp3")
        
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                with open(temp_audio_path, "wb") as f:
                    f.write(resp.read())
            print(f"Saved voiceover audio to: {temp_audio_path}")
        except Exception as e:
            print(f"Error generating voiceover for Post {current_idx}: {e}", file=sys.stderr)
            continue
            
        # 2. Check for required assets
        card_image = os.path.join(args.output_dir, f"{args.name}_{current_idx:02d}_card.jpg")
        video_output = os.path.join(args.output_dir, f"{args.name}_{current_idx:02d}_video.mp4")
        ffmpeg_path = os.path.abspath("ffmpeg.exe")
        
        if not os.path.exists(card_image):
            print(f"Error: Content Card image not found at {card_image}! Skipping.", file=sys.stderr)
            continue
            
        if not os.path.exists(ffmpeg_path):
            print("Error: ffmpeg.exe was not found in the workspace root!", file=sys.stderr)
            sys.exit(1)
            
        # 3. Compile the voiceover video using FFmpeg
        print(f"Compiling voiceover video with 2.0x volume boost and 1.12x speed...")
        if os.path.exists(video_output):
            try:
                os.remove(video_output)
            except Exception:
                pass
                
        cmd = f'"{ffmpeg_path}" -y -loop 1 -i "{card_image}" -i "{temp_audio_path}" -c:v libx264 -tune stillimage -c:a aac -b:a 192k -filter:a "volume=2.0,atempo=1.12" -pix_fmt yuv420p -shortest "{video_output}"'
        
        try:
            result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                print(f"Success! Voiceover video for Post {current_idx} saved at: {os.path.abspath(video_output)}")
            else:
                print(f"FFmpeg Compilation Error for Post {current_idx}: {result.stderr.decode('utf-8', errors='ignore')}", file=sys.stderr)
        except Exception as e:
            print(f"Compilation process failed for Post {current_idx}: {e}", file=sys.stderr)
            
    print("\n========================================")
    print("All requested voiceovers compiled successfully!")
    print("========================================")

if __name__ == "__main__":
    main()
