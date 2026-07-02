import os
import urllib.request
import urllib.parse

# Define the list of posts, their primary real URLs, and AI generation fallbacks
POSTS_IMAGES = [
    # Day 1
    {
        "filename": "day_1_a.jpg",
        "primary_url": "https://upload.wikimedia.org/wikipedia/commons/c/c3/John_F._Kennedy%2C_White_House_color_photo_portrait.jpg",
        "ai_prompt": "1963 official color photo portrait of john f kennedy in the oval office"
    },
    {
        "filename": "day_1_b.jpg",
        "primary_url": "https://upload.wikimedia.org/wikipedia/commons/e/ea/CE399.jpg",
        "ai_prompt": "trajectory diagram of the single bullet theory from the warren commission report"
    },
    # Day 2
    {
        "filename": "day_2_a.jpg",
        "primary_url": "https://upload.wikimedia.org/wikipedia/commons/e/e0/Allen_Dulles_portrait.jpg",
        "ai_prompt": "1960s formal cia black and white portrait of Allen Dulles director of CIA"
    },
    {
        "filename": "day_2_b.jpg",
        "primary_url": None,
        "ai_prompt": "unclassified stamp on a secret government dossier file, dark archives room, vintage aesthetic, cinematic lighting"
    },
    # Day 3
    {
        "filename": "day_3_a.jpg",
        "primary_url": None,
        "ai_prompt": "courtroom witness stand under a shaft of light, empty seats, somber, dramatic shadows, professional courtroom photography"
    },
    {
        "filename": "day_3_b.jpg",
        "primary_url": None,
        "ai_prompt": "vintage autobiography book lying open on a rough wooden table, dimly lit study, dramatic side lighting, documentary photography"
    },
    # Day 4
    {
        "filename": "day_4_a.jpg",
        "primary_url": None,
        "ai_prompt": "close up of a dark wooden judicial gavel resting on a soundblock, shallow depth of field, moody courtroom background, cinematic"
    },
    {
        "filename": "day_4_b.jpg",
        "primary_url": None,
        "ai_prompt": "empty wet concrete underpass tunnel in Paris at night, haunting glow, long shadows, grainy surveillance documentary photo style"
    },
    # Day 5
    {
        "filename": "day_5_a.jpg",
        "primary_url": None,
        "ai_prompt": "close up of a handwritten letter in blue ink on aged paper, intimate macro shot, soft warm shadows, cinematic"
    },
    {
        "filename": "day_5_b.jpg",
        "primary_url": None,
        "ai_prompt": "vintage 1950s hollywood dressing room table, illuminated vanity mirror, an old perfume bottle, soft warm glow, nostalgic cinema style"
    },
    # Day 6
    {
        "filename": "day_6_a.jpg",
        "primary_url": "https://upload.wikimedia.org/wikipedia/commons/2/22/Lorraine_Motel%2C_Memphis%2C_TN.jpg",
        "ai_prompt": "the historic lorraine motel in memphis tennessee, documentary photography"
    },
    {
        "filename": "day_6_b.jpg",
        "primary_url": "https://upload.wikimedia.org/wikipedia/commons/a/ae/Amelia_Earhart_standing_in_front_of_Lockheed_Electra%2C_1937.jpg",
        "ai_prompt": "amelia earhart standing in front of lockheed electra airplane 1937, vintage photo"
    },
    # Day 7
    {
        "filename": "day_7_a.jpg",
        "primary_url": None,
        "ai_prompt": "classified stamp on folders, red marker underlines, vintage desk magnifying glass, noir detective style"
    },
    {
        "filename": "day_7_b.jpg",
        "primary_url": None,
        "ai_prompt": "a complex cork board investigation wall, pinned photos, connected by red strings, historical files, moody lighting, detective office"
    }
]

def download_image(url, output_path):
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req) as response, open(output_path, 'wb') as out_file:
        out_file.write(response.read())

def main():
    output_dir = "unsolved_mysteries/outputs"
    os.makedirs(output_dir, exist_ok=True)
    
    print("Starting download process for all 14 images...")
    
    for item in POSTS_IMAGES:
        filename = item["filename"]
        primary_url = item["primary_url"]
        ai_prompt = item["ai_prompt"]
        
        target_path = os.path.join(output_dir, filename)
        
        # Try downloading real photo first if URL is defined
        success = False
        if primary_url:
            print(f"\n[{filename}] Attempting to download real photo from: {primary_url}")
            try:
                download_image(primary_url, target_path)
                print(f"[{filename}] Successfully downloaded real photo!")
                success = True
            except Exception as e:
                print(f"[{filename}] Failed to download real photo: {e}")
                print(f"[{filename}] Falling back to AI Generation...")
        
        # Generate with Pollinations.ai if primary failed or was undefined
        if not success:
            encoded_prompt = urllib.parse.quote(ai_prompt)
            # We request 1080x972 directly via query parameters
            pollinations_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=972"
            print(f"[{filename}] Generating AI photo via Pollinations.ai with prompt: '{ai_prompt}'")
            try:
                download_image(pollinations_url, target_path)
                print(f"[{filename}] Successfully generated AI photo!")
                success = True
            except Exception as e:
                print(f"[{filename}] Critical error generating AI photo: {e}")
                
    print("\nAll 14 images processed. Check unsolved_mysteries/outputs/ folder!")

if __name__ == "__main__":
    main()
