import os
from PIL import Image, ImageDraw, ImageFont

def get_font(size):
    # Căi standard pentru Impact pe Windows
    paths = [
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/arialbd.ttf", # Fallback
        "impact.ttf", # Local
    ]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def draw_text_with_outline(draw, text, position, font, text_color, outline_color, outline_width=5):
    x, y = position
    # Desenăm outline-ul prin deplasare (8 direcții)
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx*dx + dy*dy <= outline_width*outline_width:
                draw.text((x+dx, y+dy), text, font=font, fill=outline_color)
    # Desenăm textul principal
    draw.text((x, y), text, font=font, fill=text_color)

def generate_karaoke_frame(width, height, phrase_data, current_time, font_size=80):
    """
    Generează un frame transparent (RGBA) cu subtitrările karaoke.
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = get_font(font_size)
    
    # Coordonata Y pentru subtitrări (center-bottom)
    base_y = 1400
    
    # Calculăm lățimea totală a frazei pentru centrare
    full_text = " ".join([w['word'] for w in phrase_data['words']])
    
    # Folosim getbbox() pentru a calcula dimensiunile (Pillow 10+)
    bbox = draw.textbbox((0, 0), full_text, font=font)
    total_w = bbox[2] - bbox[0]
    start_x = (width - total_w) // 2
    
    # Desenăm cuvintele unul câte unul pentru a ști unde să punem highlight-ul
    current_x = start_x
    for word in phrase_data['words']:
        word_text = word['word'] + " "
        w_bbox = draw.textbbox((0, 0), word_text, font=font)
        w_width = w_bbox[2] - w_bbox[0]
        
        # Verificăm dacă acest cuvânt este cel activ
        if word['start'] <= current_time <= word['end']:
            # Desenăm fundalul MOV (Purple)
            padding = 10
            rect_shape = [
                current_x - padding, 
                base_y - padding, 
                current_x + w_width + padding, 
                base_y + (w_bbox[3] - w_bbox[1]) + padding
            ]
            # Mov aprins stil Hormozi
            draw.rounded_rectangle(rect_shape, radius=15, fill=(160, 32, 240, 255))
            
        # Desenăm textul cu outline
        draw_text_with_outline(draw, word_text, (current_x, base_y), font, (255, 255, 255, 255), (0, 0, 0, 255), outline_width=6)
        
        current_x += w_width
        
    return img

def generate_progress_frame(width, t, duration, height=50):
    """
    Generează frame-ul pentru bara de progres de sus.
    """
    img = Image.new("RGB", (width, height), (64, 64, 64)) # Gri închis (fundal)
    draw = ImageDraw.Draw(img)
    
    progress_w = int((t / duration) * width)
    if progress_w > 0:
        # Roșu intens pentru progres
        draw.rectangle([0, 0, progress_w, height], fill=(255, 0, 0))
        
    return img

def generate_cta_frame(width, height, text, position):
    """
    Generează un label CTA ( Like & Subscribe ).
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = get_font(70) # Un pic mai mic decât karaoke
    
    # Desenăm cu outline negru și text alb
    draw_text_with_outline(draw, text, position, font, (255, 255, 255, 255), (0, 0, 0, 255), outline_width=5)
    
    return img
