import argparse
import json
import os
import sys

# Add scripts directory to path to import modules
sys.path.append(os.path.join(os.path.dirname(__file__), "scripts"))

from image_generator import generate_image
from renderer import render_content_card, render_thumbnail

def load_env(env_path=".env"):
    """
    Manually load environment variables from a local .env file
    to avoid third-party dependencies like python-dotenv.
    """
    if os.path.exists(env_path):
        print(f"Loading environment variables from {env_path}...")
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        key, val = line.split("=", 1)
                        # Clean key and value from quotes
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        os.environ[key] = val

def parse_txt_file(file_path):
    """
    Parses a plain text file structured as:
    headline
    Some Headline Here
    
    content
    Some body text here...
    
    Returns a list of dicts: [{'heading': '...', 'body': '...'}]
    """
    posts = []
    current_post = {}
    current_mode = None  # can be 'headline' or 'content'
    
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    for line in lines:
        cleaned_line = line.strip()
        if cleaned_line.lower() == "headline":
            # If we already have a heading in current_post, save it and start new
            if "heading" in current_post:
                posts.append(current_post)
                current_post = {}
            current_mode = "headline"
            continue
        elif cleaned_line.lower() == "content":
            current_mode = "content"
            continue
            
        # Accumulate lines
        if current_mode == "headline":
            if cleaned_line:
                if "heading" not in current_post:
                    current_post["heading"] = cleaned_line
                else:
                    current_post["heading"] += " " + cleaned_line
        elif current_mode == "content":
            if line.strip():  # preserve spacing but skip purely empty trailing lines
                if "body" not in current_post:
                    current_post["body"] = line.rstrip()
                else:
                    current_post["body"] += "\n" + line.rstrip()
                    
    if current_post and "heading" in current_post:
        posts.append(current_post)
        
    # Clean up excess newlines or spacing from parsed texts
    for post in posts:
        if "heading" in post:
            post["heading"] = " ".join(post["heading"].split())
        if "body" in post:
            post["body"] = post["body"].strip()
            
    return posts

def process_single_post(heading, body, photo_prompt, photo_path, output_dir, name, suffix=""):
    """
    Processes a single post: highlights keywords, generates the prompt,
    creates the content card, fetches/generates the thumbnail image,
    and renders the final thumbnail.
    """
    # Auto-highlight if no formatting markup is present in the text
    has_highlights = "[" in heading or "**" in heading or (body and ("[" in body or "**" in body))
    highlighted = False
    if not has_highlights:
        print(f"\n--- Automatically highlighting important keywords for post {suffix} ---")
        from auto_highlighter import auto_highlight
        heading, body = auto_highlight(heading, body)
        highlighted = True

    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Generate Content Card
    card_output = os.path.join(output_dir, f"{name}{suffix}_card.jpg")
    print(f"\n--- Generating Content Card {suffix} ---")
    render_content_card(heading, body, card_output)
    
    # 2. Handle Thumbnail Photo
    thumb_photo_path = photo_path
    if not thumb_photo_path:
        expected_raw_path = os.path.join(output_dir, f"{name}{suffix}_raw_photo.jpg")
        expected_raw_png = os.path.join(output_dir, f"{name}{suffix}_raw_photo.png")
        if os.path.exists(expected_raw_path):
            print(f"Found existing raw photo at {expected_raw_path}, using it directly.")
            thumb_photo_path = expected_raw_path
        elif os.path.exists(expected_raw_png):
            print(f"Found existing raw photo at {expected_raw_png}, using it directly.")
            thumb_photo_path = expected_raw_png

    if not thumb_photo_path and not photo_prompt:
        if highlighted:
            import time
            print("Waiting 4 seconds to prevent Gemini rate limits between calls...")
            time.sleep(4.0)
        print(f"\n--- Automatically generating photo prompt from content {suffix} ---")
        from prompt_generator import generate_photo_prompt
        photo_prompt = generate_photo_prompt(heading, body)
        
    if not thumb_photo_path and photo_prompt:
        import time
        print("Waiting 4 seconds before AI Image Generation to respect rate limits...")
        time.sleep(4.0)
        temp_prompt_photo = os.path.join(output_dir, f"temp_prompt_photo{suffix}.jpg")
        print(f"\n--- Generating AI Photo for Thumbnail {suffix} ---")
        success = generate_image(photo_prompt, temp_prompt_photo)
        if success:
            thumb_photo_path = temp_prompt_photo
        else:
            print("Warning: Image generation failed! A gray placeholder will be used.", file=sys.stderr)
            
    # 3. Generate Thumbnail
    thumb_output = os.path.join(output_dir, f"{name}{suffix}_thumb.jpg")
    print(f"\n--- Generating Thumbnail {suffix} ---")
    render_thumbnail(heading, thumb_photo_path, thumb_output)
    
    # 4. Generate 5-second Video from Content Card (30 fps * 5s = 150 frames)
    video_output = os.path.join(output_dir, f"{name}{suffix}_video.mp4")
    print(f"\n--- Generating 5-second Video {suffix} ---")
    try:
        import cv2
        img_cv = cv2.imread(card_output)
        if img_cv is not None:
            height, width, layers = img_cv.shape
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            video = cv2.VideoWriter(video_output, fourcc, 30, (width, height))
            for _ in range(150):
                video.write(img_cv)
            video.release()
            
            # Check if background music/audio is available to merge
            audio_path = os.path.join("music", "old_audio.mp3")
            ffmpeg_path = os.path.abspath("ffmpeg.exe")
            
            if os.path.exists(audio_path) and os.path.exists(ffmpeg_path):
                print(f"Merging background audio: {audio_path}")
                temp_silent = video_output.replace(".mp4", "_silent.mp4")
                try:
                    if os.path.exists(temp_silent):
                        os.remove(temp_silent)
                    os.rename(video_output, temp_silent)
                    
                    import subprocess
                    cmd = f'"{ffmpeg_path}" -y -i "{temp_silent}" -i "{audio_path}" -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest "{video_output}"'
                    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if result.returncode == 0:
                        print(f"Video with audio saved to: {os.path.abspath(video_output)}")
                        if os.path.exists(temp_silent):
                            os.remove(temp_silent)
                    else:
                        print(f"Warning: FFmpeg audio merge failed. Keeping silent video.", file=sys.stderr)
                        if os.path.exists(video_output):
                            os.remove(video_output)
                        os.rename(temp_silent, video_output)
                except Exception as audio_err:
                    print(f"Warning: Failed to add audio track: {audio_err}. Keeping silent video.", file=sys.stderr)
                    if os.path.exists(temp_silent) and not os.path.exists(video_output):
                        os.rename(temp_silent, video_output)
            else:
                print(f"Video saved to (silent): {os.path.abspath(video_output)}")
        else:
            print(f"Error: Could not read content card image at {card_output} for video generation.", file=sys.stderr)
    except Exception as e:
        print(f"Error generating video: {e}", file=sys.stderr)
    
    # Clean up temporary prompt photo if generated
    temp_target = os.path.join(output_dir, f"temp_prompt_photo{suffix}.jpg")
    if thumb_photo_path == temp_target and os.path.exists(thumb_photo_path):
        try:
            raw_photo_dest = os.path.join(output_dir, f"{name}{suffix}_raw_photo.jpg")
            os.replace(thumb_photo_path, raw_photo_dest)
            print(f"Raw generated photo saved to: {raw_photo_dest}")
        except Exception:
            pass
            
    print(f"\nPost {suffix} generated successfully!")
    print(f"Content Card: {os.path.abspath(card_output)}")
    print(f"Thumbnail:    {os.path.abspath(thumb_output)}")
    if os.path.exists(video_output):
        print(f"Video (5s):   {os.path.abspath(video_output)}")

def get_next_post_index(output_dir, base_name):
    if not os.path.exists(output_dir):
        return 1
    max_idx = 0
    import re
    pattern = re.compile(rf"^{re.escape(base_name)}_(\d+)_card\.jpg$", re.IGNORECASE)
    for filename in os.listdir(output_dir):
        match = pattern.match(filename)
        if match:
            try:
                idx = int(match.group(1))
                if idx > max_idx:
                    max_idx = idx
            except ValueError:
                pass
    return max_idx + 1

def main():
    load_env()
    
    parser = argparse.ArgumentParser(
        description="ERASED Automation - Automated Content Card & Thumbnail Generator"
    )
    
    parser.add_argument("--heading", help="Heading text")
    parser.add_argument("--body", help="Body text")
    parser.add_argument("--photo-prompt", help="AI Image Generation prompt")
    parser.add_argument("--photo-path", help="Optional path to a local photo")
    parser.add_argument("--input-file", help="Path to an input file (TXT or JSON)")
    parser.add_argument("--output-dir", default="outputs", help="Directory where generated assets should be saved")
    parser.add_argument("--name", default="erased_post", help="Base name prefix")
    
    parser.add_argument("--start-idx", type=int, help="Force start numbering from this index")
    
    args = parser.parse_args()
    
    if args.input_file:
        if not os.path.exists(args.input_file):
            print(f"Error: Input file {args.input_file} not found!", file=sys.stderr)
            sys.exit(1)
        try:
            if args.input_file.endswith(".txt"):
                data = parse_txt_file(args.input_file)
            else:
                with open(args.input_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            if isinstance(data, list):
                print(f"\nBatch mode detected! Processing {len(data)} posts from {args.input_file}...")
                if args.start_idx is not None:
                    start_idx = args.start_idx
                    print(f"Forced Start Index: Starting next post numbering from: {start_idx:02d}")
                else:
                    start_idx = get_next_post_index(args.output_dir, args.name)
                    if start_idx > 1:
                        print(f"Auto-Resume: Found existing posts. Starting next post numbering from: {start_idx:02d}")
                
                for i, item in enumerate(data):
                    idx = start_idx + i
                    item_heading = item.get("heading")
                    item_body = item.get("body")
                    item_prompt = item.get("photo_prompt") or args.photo_prompt
                    item_path = item.get("photo_path") or args.photo_path
                    
                    if not item_heading:
                        print(f"Skipping index {idx}: heading is missing.", file=sys.stderr)
                        continue
                        
                    suffix = f"_{idx:02d}"
                    print(f"\n======================================== [Post {idx}/{start_idx + len(data) - 1}] ========================================")
                    if i > 0:
                        import time
                        print("Waiting 4 seconds to prevent API rate limiting...")
                        time.sleep(4.0)
                        
                    process_single_post(item_heading, item_body, item_prompt, item_path, args.output_dir, args.name, suffix)
                print("\n========================================")
                print("All batch posts generated successfully!")
                print("========================================")
                return
            else:
                heading = data.get("heading", args.heading)
                body = data.get("body", args.body)
                photo_prompt = data.get("photo_prompt", args.photo_prompt)
                photo_path = data.get("photo_path", args.photo_path)
        except Exception as e:
            print(f"Error parsing input file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        heading = args.heading
        body = args.body
        photo_prompt = args.photo_prompt
        photo_path = args.photo_path
            
    if not heading and not args.input_file:
        print("--- ERASED Automated Post Generator ---")
        heading = input("Enter Title/Heading:\n> ").strip()
        body = input("\nEnter Body Paragraphs:\n> ").replace("\\n", "\n").strip()
        photo_path = input("\nEnter local photo path (optional):\n> ").strip()
        if not photo_path:
            photo_prompt = input("\nEnter AI Photo Prompt:\n> ").strip()
            
    if not heading:
        print("Error: Heading/Title is required!", file=sys.stderr)
        sys.exit(1)
        
    print("\n======================================== [Single Post] ========================================")
    process_single_post(heading, body, photo_prompt, photo_path, args.output_dir, args.name, "")
    print("========================================")

if __name__ == "__main__":
    main()
