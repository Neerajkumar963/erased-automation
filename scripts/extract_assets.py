import os
from PIL import Image

def extract_logo(src_path, dest_path):
    print(f"Extracting logo from {src_path}...")
    img = Image.open(src_path).convert("RGBA")
    
    # Bounding box for logo: X: 760 to 1031, Y: 58 to 285
    logo_crop = img.crop((760, 58, 1031, 285))
    
    # We want to replace the cream background #f8f2e6 (248, 242, 230) with transparency
    # We will use color distance to softly apply transparency at edges for anti-aliasing
    bg_r, bg_g, bg_b = 248, 242, 230
    
    datas = logo_crop.getdata()
    new_data = []
    
    for item in datas:
        r, g, b, a = item
        # Calculate Euclidean distance from cream background
        distance = ((r - bg_r) ** 2 + (g - bg_g) ** 2 + (b - bg_b) ** 2) ** 0.5
        
        # Thresholds
        t_low = 15.0  # Fully transparent below this distance
        t_high = 80.0 # Fully opaque above this distance
        
        if distance < t_low:
            new_data.append((0, 0, 0, 0))
        elif distance > t_high:
            new_data.append((r, g, b, 255))
        else:
            # Interpolate alpha between 0 and 255
            ratio = (distance - t_low) / (t_high - t_low)
            alpha = int(255 * ratio)
            # Since the background was cream, we want to shift the color slightly towards black
            # to avoid cream outlines
            new_data.append((r, g, b, alpha))
            
    logo_crop.putdata(new_data)
    logo_crop.save(dest_path, "PNG")
    print(f"Saved transparent logo to {dest_path}")

def extract_footers(card_path, thumb_path, card_dest, thumb_dest):
    print("Extracting footers...")
    
    # Content card footer: Y: 2157 to 2400
    card_img = Image.open(card_path)
    card_footer = card_img.crop((0, 2157, 1792, 2400))
    card_footer.save(card_dest, "JPEG")
    print(f"Saved content card footer to {card_dest}")
    
    # Thumbnail footer: Y: 1983 to 2400
    thumb_img = Image.open(thumb_path)
    thumb_footer = thumb_img.crop((0, 1983, 1792, 2400))
    thumb_footer.save(thumb_dest, "JPEG")
    print(f"Saved thumbnail footer to {thumb_dest}")

if __name__ == "__main__":
    os.makedirs("assets", exist_ok=True)
    card_path = os.path.join("templates", "content_card_template.jpeg")
    thumb_path = os.path.join("templates", "thumb_template.jpeg")
    
    logo_dest = os.path.join("assets", "logo.png")
    card_footer_dest = os.path.join("assets", "card_footer.jpg")
    thumb_footer_dest = os.path.join("assets", "thumb_footer.jpg")
    
    extract_logo(card_path, logo_dest)
    extract_footers(card_path, thumb_path, card_footer_dest, thumb_footer_dest)
    print("Extraction complete!")
