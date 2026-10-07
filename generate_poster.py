import json
from PIL import Image, ImageDraw, ImageFont
import os

def generate_poster():
    # Load JSON
    with open('design.json', 'r') as f:
        data = json.load(f)
        
    width = 1536
    height = 2048
    bg_color = data['color_palette']['background']
    
    # Create base image
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    # Try to load Windows fonts
    try:
        font_title = ImageFont.truetype("georgia.ttf", 120)
        font_subtitle = ImageFont.truetype("arial.ttf", 50)
        font_brand = ImageFont.truetype("arialbd.ttf", 80)
        font_card_title = ImageFont.truetype("arialbd.ttf", 70)
        font_card_pct = ImageFont.truetype("georgia.ttf", 150)
    except:
        # Fallback to default if fonts not found
        font_title = ImageFont.load_default()
        font_subtitle = font_brand = font_card_title = font_card_pct = font_title
        
    # Draw Brand Logo Area
    brand_text = data['brand'].upper()
    draw.text((width//2, 150), brand_text, fill=data['color_palette']['primary_black'], font=font_brand, anchor="mm")
    draw.line([(width//2 - 200, 200), (width//2 + 200, 200)], fill=data['color_palette']['primary_red'], width=4)
    draw.text((width//2, 240), "OPINION POLL", fill=data['color_palette']['primary_black'], font=font_subtitle, anchor="mm")
    
    # Draw Headline
    headline = data['main_headline']['text']
    draw.text((width//2, 450), headline, fill=data['color_palette']['primary_black'], font=font_title, anchor="mm")
    draw.text((width//2, 580), "ASSEMBLY CONSTITUENCY\nUTTAR PRADESH", fill=data['color_palette']['primary_black'], font=font_subtitle, anchor="mm", align="center")
    
    # Draw Poll Cards
    card_width = 400
    card_height = 600
    start_x = 100
    gap = 68 # (1536 - 200 - 1200) / 2
    y_pos = 800
    
    cards = data['poll_cards']['cards']
    for i, card in enumerate(cards):
        x_pos = start_x + i * (card_width + gap)
        
        # Card Background
        card_bg = data['color_palette']['light_gray']
        if i == 0: card_bg = data['color_palette']['soft_cream']
        if i == 1: card_bg = data['color_palette']['soft_pink']
        
        # Draw Rounded Rectangle (simulated with rectangle for simplicity in basic PIL)
        # PIL 8.2+ has rounded_rectangle
        try:
            draw.rounded_rectangle([x_pos, y_pos, x_pos+card_width, y_pos+card_height], radius=30, fill=card_bg, outline=card['border'], width=8)
        except AttributeError:
            draw.rectangle([x_pos, y_pos, x_pos+card_width, y_pos+card_height], fill=card_bg, outline=card['border'], width=8)
            
        # Draw Card Content
        draw.text((x_pos + card_width//2, y_pos + 100), card['name'], fill=data['color_palette']['primary_black'], font=font_card_title, anchor="mm")
        
        # Icon placeholder circle
        draw.ellipse([x_pos + card_width//2 - 60, y_pos + 200, x_pos + card_width//2 + 60, y_pos + 320], fill="white", outline=card['border'], width=4)
        
        draw.text((x_pos + card_width//2, y_pos + 450), card['percentage'], fill=data['color_palette']['primary_black'], font=font_card_pct, anchor="mm")
        draw.text((x_pos + card_width//2, y_pos + 530), "VOTE SHARE", fill=data['color_palette']['neutral_gray'], font=font_subtitle, anchor="mm")

        # Add LEADING badge for SP+
        if card['name'] == 'SP+':
            badge_width = 250
            badge_height = 80
            bx = x_pos + card_width//2 - badge_width//2
            by = y_pos - badge_height//2
            try:
                draw.rounded_rectangle([bx, by, bx+badge_width, by+badge_height], radius=40, fill=data['color_palette']['primary_red'])
            except:
                draw.rectangle([bx, by, bx+badge_width, by+badge_height], fill=data['color_palette']['primary_red'])
            draw.text((bx + badge_width//2, by + badge_height//2), "LEADING", fill="white", font=font_subtitle, anchor="mm")

    # Draw Footer
    draw.line([(100, 1700), (1436, 1700)], fill=data['color_palette']['light_gray'], width=4)
    draw.text((300, 1800), "SURVEY DATE\n21 May 2023", fill=data['color_palette']['primary_black'], font=font_subtitle, align="center")
    draw.text((768, 1800), "SAMPLE SIZE\n3,000", fill=data['color_palette']['primary_black'], font=font_subtitle, align="center", anchor="ma")
    draw.text((1200, 1800), "METHODOLOGY\nPhone & Field", fill=data['color_palette']['primary_black'], font=font_subtitle, align="center")
    
    draw.text((width//2, 1950), "BASED ON CIVORA TIMES SURVEY", fill=data['color_palette']['neutral_gray'], font=font_subtitle, anchor="mm")
    
    # Save Image
    output_path = 'output_poster.png'
    img.save(output_path)
    print(f"Poster successfully generated at {output_path}")

if __name__ == "__main__":
    generate_poster()
