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
        if char.isspace() or char in ["—", "-", "/"]:
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
        
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp_raw:
                resp = json.loads(resp_raw.read().decode("utf-8"))
            # Save raw audio file
            audio_bytes = base64.b64decode(resp["audio_base64"])
            with open(temp_audio_path, "wb") as f:
                f.write(audio_bytes)
            print(f"Saved raw voiceover audio to: {temp_audio_path}")
        except Exception as e:
            print(f"Error generating voiceover for Post {current_idx}: {e}", file=sys.stderr)
            continue
            
        # Parse alignment timings
        spoken_words = parse_elevenlabs_alignment(resp["alignment"], speed_factor=1.12)
        duration = spoken_words[-1]["end"] + 1.0 # 1s buffer at the end
        fps = 30
        total_frames = int(duration * fps)
        
        # 2. Speed up audio using FFmpeg
        fast_audio_path = os.path.join("scratch", f"voiceover_{current_idx}_fast.mp3")
        if os.path.exists(fast_audio_path):
            try:
                os.remove(fast_audio_path)
            except Exception:
                pass
        cmd_audio = f'"{ffmpeg_path}" -y -i "{temp_audio_path}" -filter:a "volume=2.0,atempo=1.12" "{fast_audio_path}"'
        subprocess.run(cmd_audio, shell=True, check=True)
        
        # 3. Layout text paragraphs using renderer.py layout engine
        fonts = {
            "poppins_reg": ImageFont.truetype(os.path.join("fonts", "Poppins-Regular.ttf"), 68),
            "poppins_bold": ImageFont.truetype(os.path.join("fonts", "Poppins-Bold.ttf"), 68),
            "anton": ImageFont.truetype(os.path.join("fonts", "Anton-Regular.ttf"), 90)
        }
        
        raw_paragraphs = raw_body.split("\n\n")
        max_width = 1592
        
        paragraphs_lines = []
        for para in raw_paragraphs:
            lines = layout_paragraph(para, "poppins", fonts, max_width)
            paragraphs_lines.append(lines)
            
        # Map spoken words to layout tokens
        word_ptr = 0
        words_layout_data = []
        
        start_x = 100
        start_y = 750
        line_height = 105
        paragraph_gap = 40
        font_height = 80
        
        current_y = start_y
        for p_idx, para_lines in enumerate(paragraphs_lines):
            for j, line in enumerate(para_lines):
                current_x = start_x
                for token, font, color, width in line:
                    clean_tok = re.sub(r'[^\w]', '', token.lower())
                    
                    x1 = current_x
                    y1 = current_y
                    x2 = current_x + width
                    y2 = current_y + font_height
                    
                    word_timing = None
                    if clean_tok and word_ptr < len(spoken_words):
                        word_timing = spoken_words[word_ptr]
                        word_ptr += 1
                        
                    words_layout_data.append({
                        "token": token,
                        "font": font,
                        "color": color,
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2,
                        "timing": word_timing
                    })
                    current_x += width
                    
                # Line leading
                if p_idx == len(paragraphs_lines) - 1 and j == len(para_lines) - 1:
                    current_y += font_height
                else:
                    if j == len(para_lines) - 1:
                        current_y += font_height + paragraph_gap
                    else:
                        current_y += line_height
                        
        # 4. Render Video Frames
        temp_video_raw = os.path.join("scratch", f"temp_video_{current_idx}.mp4")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video_writer = cv2.VideoWriter(temp_video_raw, fourcc, fps, (1792, 2400))
        
        # Base canvas setup
        base_img = Image.new("RGB", (1792, 2400), PALETTE["bg"])
        draw_base = ImageDraw.Draw(base_img)
        
        # Paste header if exists
        header_path = os.path.join("assets", "new_header_mockup.png")
        if os.path.exists(header_path):
            header_img = Image.open(header_path).convert("RGBA")
            base_img.paste(header_img, (0, 58), header_img)
            
        # Draw Headline (wrapped and centered)
        headline_words = heading.upper().split()
        hl_lines = []
        current_line = []
        curr_w = 0
        for w in headline_words:
            w_w = fonts["anton"].getlength(w + " ")
            if curr_w + w_w > max_width and current_line:
                hl_lines.append(" ".join(current_line))
                current_line = [w]
                curr_w = w_w
            else:
                current_line.append(w)
                curr_w += w_w
        if current_line:
            hl_lines.append(" ".join(current_line))
            
        hl_y = 250
        for line in hl_lines:
            w_len = fonts["anton"].getlength(line)
            x_pos = (1792 - w_len) // 2
            draw_base.text((x_pos, hl_y), line, font=fonts["anton"], fill=(1, 1, 1))
            hl_y += 110
            
        # Write frames to cv2 Writer
        print("Rendering frames...")
        for frame_idx in range(total_frames):
            t = frame_idx / float(fps)
            frame_img = base_img.copy()
            draw = ImageDraw.Draw(frame_img)
            
            for item in words_layout_data:
                tok = item["token"]
                font = item["font"]
                color = item["color"]
                x1, y1, x2, y2 = item["x1"], item["y1"], item["x2"], item["y2"]
                timing = item["timing"]
                
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
                    # Text in bold amber
                    draw.text((x1, y1), tok, font=font, fill=(217, 119, 6)) # (#d97706)
                else:
                    # Original text color from layout settings
                    draw.text((x1, y1), tok, font=font, fill=color)
                    
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
                
        bg_music = os.path.join("music", "audio.mp3")
        if os.path.exists(bg_music):
            print("Merging video with voiceover and background music track...")
            cmd_merge = (
                f'"{ffmpeg_path}" -y -i "{temp_video_raw}" -i "{fast_audio_path}" -i "{bg_music}" '
                f'-filter_complex "[1:a]volume=1.0[a1];[2:a]volume=0.08[a2];[a1][a2]amix=inputs=2:duration=first[a]" '
                f'-map 0:v -map "[a]" -c:v libx264 -pix_fmt yuv420p "{video_output}"'
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
            os.remove(temp_audio_path)
            os.remove(fast_audio_path)
        except Exception:
            pass
            
    print("\n========================================")
    print("All perfect-sync voiceover videos compiled successfully!")
    print("========================================")

if __name__ == "__main__":
    main()
