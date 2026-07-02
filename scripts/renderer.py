import os
import re
from PIL import Image, ImageDraw, ImageFont

# Define Color Palette
PALETTE = {
    "default": (1, 1, 1),        # Near black
    "red": (192, 0, 30),         # Crimson Red (#c0001e)
    "orange": (1, 1, 1),         # Black instead of Teal (to keep design clean)
    "teal": (1, 1, 1),           # Black instead of Teal
    "amber": (245, 158, 11),     # Amber (#f59e0b)
    "white": (255, 255, 255),
    "bg": (248, 242, 230)        # Cream Canvas Background
}

def parse_text(text):
    """
    Parses a string with syntax [word](color) or **bold** into runs of (text, style).
    Returns list of tuples: (run_text, {'color': 'red'|'orange'|'default', 'bold': bool})
    """
    text = text.replace("\\", "")
    pattern = re.compile(r'(\[.*?\]\s*\([a-zA-Z]+\))|(\*\*.*?\*\*)')
    parts = pattern.split(text)
    runs = []
    for part in parts:
        if not part:
            continue
        part_clean = re.sub(r'\]\s*\(', '](', part)
        if part_clean.startswith('[') and part_clean.endswith(')'):
            match = re.match(r'\[(.*?)\]\(([a-zA-Z]+)\)', part_clean)
            if match:
                word_text = match.group(1)
                color_name = match.group(2).lower()
                runs.append((word_text, {'color': color_name, 'bold': True}))
        elif part.startswith('**') and part.endswith('**'):
            word_text = part[2:-2]
            runs.append((word_text, {'color': 'default', 'bold': True}))
        else:
            runs.append((part, {'color': 'default', 'bold': False}))
    return runs

def layout_paragraph(text, default_font_family, fonts, max_width):
    """
    Lays out a single paragraph of text (no paragraph breaks).
    Returns a list of lines, where each line is a list of:
      (token_text, font_object, color_tuple, token_width)
    """
    runs = parse_text(text)
    tokens = []
    for run_text, style in runs:
        parts = re.split(r'(\s+)', run_text)
        for part in parts:
            if part:
                tokens.append((part, style))
                
    lines = []
    current_line = []
    current_width = 0
    
    for token, style in tokens:
        is_bold = style.get('bold', False)
        if default_font_family == 'anton':
            font = fonts['anton']
        else:
            font = fonts['poppins_bold'] if is_bold else fonts['poppins_reg']
            
        color_name = style.get('color', 'default')
        if color_name == 'default' and is_bold:
            color_name = 'amber'
        color = PALETTE.get(color_name, PALETTE['default'])
        
        w_len = font.getlength(token)
        
        if current_width + w_len > max_width and current_line:
            lines.append(current_line)
            if token.isspace():
                current_line = []
                current_width = 0
            else:
                current_line = [(token, font, color, w_len)]
                current_width = w_len
        else:
            current_line.append((token, font, color, w_len))
            current_width += w_len
            
    if current_line:
        lines.append(current_line)
        
    return lines

def render_paragraphs(draw, paragraphs_lines, start_x, start_y, leading, paragraph_gap, font_height):
    """
    Draws pre-laid-out paragraphs onto the image canvas.
    """
    current_y = start_y
    for i, para_lines in enumerate(paragraphs_lines):
        for j, line in enumerate(para_lines):
            current_x = start_x
            for token, font, color, width in line:
                ascent, descent = font.getmetrics()
                draw.text((current_x, current_y + ascent), token, font=font, fill=color, anchor="ls")
                current_x += width
            
            if i == len(paragraphs_lines) - 1 and j == len(para_lines) - 1:
                current_y += font_height
            else:
                if j == len(para_lines) - 1:
                    current_y += font_height + paragraph_gap
                else:
                    current_y += leading
    return current_y

def render_content_card(heading, body, output_path):
    """
    Renders a Content Card (1792x2400 pixels).
    """
    img = Image.new("RGB", (1792, 2400), PALETTE["bg"])
    draw = ImageDraw.Draw(img)
    
    fonts = {
        "poppins_reg": ImageFont.truetype(os.path.join("fonts", "Poppins-Regular.ttf"), 68),
        "poppins_bold": ImageFont.truetype(os.path.join("fonts", "Poppins-Bold.ttf"), 68)
    }
    
    header_path = os.path.join("assets", "new_header_mockup.png")
    if os.path.exists(header_path):
        header_img = Image.open(header_path).convert("RGBA")
        img.paste(header_img, (0, 58), header_img)
    else:
        logo_path = os.path.join("assets", "logo.png")
        if os.path.exists(logo_path):
            logo_img = Image.open(logo_path).convert("RGBA")
            logo_w, logo_h = logo_img.size
            logo_x = (1792 - logo_w) // 2
            img.paste(logo_img, (logo_x, 58), logo_img)
        else:
            print("Warning: assets/logo.png not found!")
        
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
        
    title_end_y = render_paragraphs(
        draw, 
        [title_lines], 
        start_x=100, 
        start_y=347, 
        leading=title_leading, 
        paragraph_gap=0, 
        font_height=title_font_height
    )
    
    body_font_size = 68
    body_paragraphs = body.split("\n\n")
    
    while True:
        fonts["poppins_reg"] = ImageFont.truetype(os.path.join("fonts", "Poppins-Regular.ttf"), body_font_size)
        fonts["poppins_bold"] = ImageFont.truetype(os.path.join("fonts", "Poppins-Bold.ttf"), body_font_size)
        
        body_para_lines = [
            layout_paragraph(para, "poppins", fonts, 1592) 
            for para in body_paragraphs if para.strip()
        ]
        
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
        
    render_paragraphs(
        draw,
        body_para_lines,
        start_x=100,
        start_y=body_start_y,
        leading=body_leading,
        paragraph_gap=body_para_gap,
        font_height=body_font_height
    )
    
    footer_path = os.path.join("assets", "card_footer.jpg")
    if os.path.exists(footer_path):
        footer_img = Image.open(footer_path)
        img.paste(footer_img, (0, 2157))
    else:
        print("Warning: assets/card_footer.jpg not found!")
        
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "JPEG")
    print(f"Content Card saved to {output_path}")

def render_thumbnail(heading, photo_path, output_path):
    """
    Renders a Thumbnail Card (1792x2400 pixels).
    """
    img = Image.new("RGB", (1792, 2400), PALETTE["bg"])
    draw = ImageDraw.Draw(img)
    fonts = {}
    
    # 3. Paste and Crop Photo (Y: 0 to 1532)
    if photo_path and os.path.exists(photo_path):
        photo_img = Image.open(photo_path)
        photo_w, photo_h = photo_img.size
        target_w, target_h = 1792, 1532
        
        scale = max(target_w / photo_w, target_h / photo_h)
        new_w = int(photo_w * scale)
        new_h = int(photo_h * scale)
        resized_photo = photo_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        cropped_photo = resized_photo.crop((left, top, left + target_w, top + target_h))
        img.paste(cropped_photo, (0, 0))
    else:
        if photo_path:
            print(f"Warning: Photo path {photo_path} not found!")
        else:
            print("Warning: Photo path is None!")
        # Draw a dark gray placeholder box
        draw.rectangle([(0, 0), (1792, 1532)], fill=(40, 40, 40))
        draw.text((896, 766), "PHOTO PLACEHOLDER", fill=(200, 200, 200), anchor="mm")
        
    title_font_size = 105
    while True:
        fonts["anton"] = ImageFont.truetype(os.path.join("fonts", "Anton-Regular.ttf"), title_font_size)
        title_lines = layout_paragraph(heading.upper(), "anton", fonts, 1615)
        
        title_font_height = int(title_font_size * (94 / 105))
        title_leading = int(title_font_size * (127 / 105))
        h = (len(title_lines) - 1) * title_leading + title_font_height
        
        if h <= 350 or title_font_size <= 60:
            break
        title_font_size -= 5
        
    render_paragraphs(
        draw,
        [title_lines],
        start_x=88,
        start_y=1585,
        leading=title_leading,
        paragraph_gap=0,
        font_height=title_font_height
    )
    
    footer_path = os.path.join("assets", "thumb_footer.jpg")
    if os.path.exists(footer_path):
        footer_img = Image.open(footer_path)
        img.paste(footer_img, (0, 1983))
    else:
        print("Warning: assets/thumb_footer.jpg not found!")
        
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "JPEG")
    print(f"Thumbnail saved to {output_path}")
