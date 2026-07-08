import os
import json
from bs4 import BeautifulSoup

def extract_from_html(html_path):
    posts = []
    if not os.path.exists(html_path):
        return posts
        
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
        
    for card in soup.find_all('div', class_='card'):
        caption_div = card.find('div', class_='sc')
        pinned_div = card.find('div', class_='pinned_comment')
        
        caption = ""
        if caption_div:
            for br in caption_div.find_all('br'): br.replace_with('\n')
            caption = caption_div.text.strip()
            
        pinned_comment = ""
        if pinned_div:
            for br in pinned_div.find_all('br'): br.replace_with('\n')
            pinned_comment = pinned_div.text.strip()
            
        posts.append({
            "caption": caption,
            "pinned_comment": pinned_comment
        })
    return posts

def migrate():
    master_db = {
        "queues": {
            "current_affairs": [],
            "family_tragedies": [],
            "us_history": []
        }
    }
    
    # --- Current Affairs ---
    ca_path = "archive/old_databases/current_affairs_data.json"
    if os.path.exists(ca_path):
        with open(ca_path, 'r', encoding='utf-8') as f:
            ca_data = json.load(f)
            # CA JSON has keys like post_1, post_2
            # But the URLs are in scheduled_posts.json? No, CA uses tmpfiles dynamically.
            # Wait, the user said they will upload them to Dropbox now for the new architecture.
            # For now, let's just populate what we can.
            for key, val in ca_data.items():
                master_db['queues']['current_affairs'].append({
                    "dropbox_url": "TODO_UPLOAD_TO_DROPBOX",
                    "caption": "Current Affairs Update",
                    "pinned_comment": f"{val['fun_fact']}\n.\n.\n{val['cta_question']}\n.\n.\nFollow @erased.record"
                })

    # --- Family Tragedies (Part 4) ---
    p4_links = "archive/old_databases/part4_video_links.json"
    if os.path.exists(p4_links):
        with open(p4_links, 'r', encoding='utf-8') as f:
            links_data = json.load(f)
            
        html_data = extract_from_html(r"formats\hidden_family_tragedies_part4.html")
        
        for i, (key, url) in enumerate(links_data.items()):
            if i < len(html_data):
                master_db['queues']['family_tragedies'].append({
                    "dropbox_url": url,
                    "caption": html_data[i]['caption'],
                    "pinned_comment": html_data[i]['pinned_comment']
                })

    # --- US History (Part 5) ---
    p5_links = "archive/old_databases/part5_database.json"
    if os.path.exists(p5_links):
        with open(p5_links, 'r', encoding='utf-8') as f:
            links_data = json.load(f)
            
        html_data = extract_from_html(r"formats\hidden_family_tragedies_part5.html")
        
        for i, (key, val) in enumerate(links_data.items()):
            if i < len(html_data):
                master_db['queues']['us_history'].append({
                    "dropbox_url": val['dropbox_url'],
                    "caption": html_data[i]['caption'],
                    "pinned_comment": html_data[i]['pinned_comment']
                })
                
    with open("master_monthly_schedule.json", "w", encoding="utf-8") as f:
        json.dump(master_db, f, indent=4)
        
    print(f"Created Master DB with:")
    print(f"- {len(master_db['queues']['current_affairs'])} Current Affairs")
    print(f"- {len(master_db['queues']['family_tragedies'])} Family Tragedies")
    print(f"- {len(master_db['queues']['us_history'])} US History")

if __name__ == "__main__":
    migrate()
