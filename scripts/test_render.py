import os
from renderer import render_content_card, render_thumbnail

if __name__ == "__main__":
    heading_card = "FOR 37 YEARS, THE US [SECRETLY](red) [DECODED](red) SOVIET MESSAGES — AND FOUND [ATOMIC](red) SPIES INSIDE THEIR OWR OWN GOVERNMENT."
    body_card = (
        "From 1943 to 1980, the NSA ran [VENONA](red) — secretly decoding encrypted Soviet intelligence communications. "
        "The project was so classified that President [Truman](orange) wasn’t fully briefed.\n\n"
        "When analysts cracked the codes, they found Soviet spies had penetrated the US [atomic bomb programme](red). "
        "Among those identified: [Julius and Ethel Rosenberg](orange), later executed. The programme was only "
        "declassified in 1995 — 52 years after it began."
    )
    
    heading_thumb = "FOR 37 YEARS, THE US [SECRETLY](red) [DECODED](red) SOVIET MESSAGES — AND FOUND [ATOMIC](red) [SPIES](red) INSIDE THEIR OWN GOVERNMENT."
    
    os.makedirs("outputs", exist_ok=True)
    
    # We test the content card rendering
    render_content_card(heading_card, body_card, os.path.join("outputs", "test_card.jpg"))
    
    # We test the thumbnail rendering. We crop the typewriter photo section from the template first
    # to avoid the text at the bottom of the template image
    from PIL import Image as PILImage
    thumb_tpl = PILImage.open(os.path.join("templates", "thumb_template.jpeg"))
    photo_only = thumb_tpl.crop((0, 0, 1792, 1532))
    temp_photo_path = os.path.join("outputs", "temp_photo.jpg")
    photo_only.save(temp_photo_path)
    
    render_thumbnail(heading_thumb, temp_photo_path, os.path.join("outputs", "test_thumb.jpg"))
    
    print("Test rendering complete! Output images are in the 'outputs' directory.")
