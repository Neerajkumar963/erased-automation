import os
import json
import re
from bs4 import BeautifulSoup

def clean_text(text):
    if not text:
        return ""
    # Replace multiple spaces/newlines
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def parse_html_to_json(html_path, json_path):
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
        
    posts = []
    cards = soup.find_all(class_='card')
    
    print(f"Found {len(cards)} posts in HTML. Starting extraction...")
    
    for idx, card in enumerate(cards):
        # 1. Posting time
        ctime_div = card.find(class_='ctime')
        post_time = clean_text(ctime_div.text).replace('⏰', '').strip() if ctime_div else ""
        
        # 2. Topic
        topic_div = card.find(class_='topic')
        topic = clean_text(topic_div.text) if topic_div else ""
        
        # 3. Era
        era_div = card.find(class_='era')
        era = clean_text(era_div.text) if era_div else ""
        
        # 4. Photo Prompt
        photo_prompt_div = card.find(class_='mock-photo-txt')
        photo_prompt = clean_text(photo_prompt_div.text) if photo_prompt_div else ""
        
        # 5. Heading (Caption on Card)
        heading_div = card.find(class_='mock-cap-txt')
        heading = clean_text(heading_div.text) if heading_div else ""
        
        # 6. Photo note
        photo_note_div = card.find(class_='photonote')
        photo_note = clean_text(photo_note_div.text).replace('⚠️', '').strip() if photo_note_div else ""
        
        # 7. Confirmed fact
        confirmed_div = card.find(class_='fb-confirmed')
        confirmed_text = ""
        if confirmed_div:
            # Strip the label label "✅ Confirmed"
            lbl = confirmed_div.find(class_='fb-lbl')
            lbl_txt = lbl.text if lbl else "✅ Confirmed"
            confirmed_text = clean_text(confirmed_div.text.replace(lbl_txt, '')).strip()
            
        # 8. Disputed theory
        disputed_div = card.find(class_='fb-disputed')
        disputed_text = ""
        if disputed_div:
            # Strip the label "❓ Disputed / Theory"
            lbl = disputed_div.find(class_='fb-lbl')
            lbl_txt = lbl.text if lbl else "❓ Disputed / Theory"
            disputed_text = clean_text(disputed_div.text.replace(lbl_txt, '')).strip()
            
        # 9. Ready Caption
        caption_div = card.find(class_='sc')
        caption_raw = ""
        if caption_div:
            # Convert <br> tags to newlines to preserve formatting
            for br in caption_div.find_all('br'):
                br.replace_with('\n')
            caption_raw = caption_div.get_text()
            
            # Format strong tags into markdown **bold**
            for strong in caption_div.find_all('strong'):
                strong_txt = strong.get_text()
                caption_raw = caption_raw.replace(strong_txt, f"**{strong_txt}**")
            
            # Clean lines and normalize
            lines = [line.strip() for line in caption_raw.split('\n')]
            caption_raw = '\n\n'.join([line for line in lines if line])
            
        # 10. Hashtags
        hashtags_div = card.find(class_='stg')
        hashtags = clean_text(hashtags_div.text) if hashtags_div else ""
        
        post_data = {
            "post_index": idx + 1,
            "time": post_time,
            "topic": topic,
            "era": era,
            "photo_prompt": photo_prompt,
            "heading": heading,
            "photo_note": photo_note,
            "confirmed": confirmed_text,
            "disputed": disputed_text,
            "caption": caption_raw,
            "hashtags": hashtags
        }
        posts.append(post_data)
        
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)
        
    print(f"Saved {len(posts)} posts to {json_path}")

if __name__ == "__main__":
    html_file = "unsolved_mysteries_week.html"
    json_file = "unsolved_mysteries/unsolved_mysteries.json"
    parse_html_to_json(html_file, json_file)
