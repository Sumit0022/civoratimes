import os
from PIL import Image, ImageDraw, ImageFont
import string

TEMPLATE_PATH = "news_template.png"
FONT_PATH = "Montserrat-ExtraBold.ttf" 

COLOR_TEXT = "#020202"
COLOR_CIVORA_RED = "#F90403"

# Original coordinates
main_tagline_box = [80, 280, 944, 850]

# Apply uniform padding from all 4 sides (cut in half from 60 to 30)
PADDING = 30
padded_box = [
    main_tagline_box[0] + PADDING,
    main_tagline_box[1] + PADDING,
    main_tagline_box[2] - PADDING,
    main_tagline_box[3] - PADDING
]

def draw_adaptive_multicolor_text(draw, text, bounding_box, font_path, max_font_size, highlight_indices=None):
    if highlight_indices is None:
        highlight_indices = [0]
    x1, y1, x2, y2 = bounding_box
    max_width = x2 - x1
    max_height = y2 - y1
    center_x = (x1 + x2) // 2
    center_y = (y1 + y2) // 2
    
    font_size = max_font_size
    best_wrapped_lines = []
    best_font = None
    best_line_height = 0
    
    words = text.split()
    
    # Filter highlight indices to make sure they are within bounds
    highlight_indices = [i for i in highlight_indices if i < len(words)]
        
    while font_size > 10:
        try:
            font = ImageFont.truetype(font_path, font_size)
        except:
            font = ImageFont.load_default()
            
        # 1. Pixel-perfect word wrapping
        wrapped_lines = []
        current_line = []
        
        for word in words:
            test_line = " ".join(current_line + [word])
            w = font.getlength(test_line)
            if w <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    wrapped_lines.append(current_line)
                    current_line = [word]
                else:
                    wrapped_lines.append([word])
                    current_line = []
        if current_line:
            wrapped_lines.append(current_line)
            
        # 2. Check if total height fits
        # We need the height of one line.
        # getmetrics()[0] + getmetrics()[1] gives ascent + descent roughly. Or use getbbox("A")[3]
        line_height = font.getbbox("ABCDEFGHIJKLMNOPQRSTUVWXYZ")[3]
        line_spacing = int(font_size * 0.3)
        total_text_height = (len(wrapped_lines) * line_height) + ((len(wrapped_lines) - 1) * line_spacing)
        
        # Check for widest line (in case a single word was forced)
        widest_line_width = max([font.getlength(" ".join(line)) for line in wrapped_lines]) if wrapped_lines else 0
        
        if total_text_height <= max_height and widest_line_width <= max_width:
            # Check for orphan words
            last_line = wrapped_lines[-1]
            if len(wrapped_lines) > 1 and len(last_line) == 1 and len(last_line[0]) < 6:
                font_size -= 2
                continue
                
            best_wrapped_lines = wrapped_lines
            best_font = font
            best_line_height = line_height
            break
            
        font_size -= 2

    if not best_wrapped_lines:
        return

    line_spacing = int(font_size * 0.3)
    total_height = (len(best_wrapped_lines) * best_line_height) + ((len(best_wrapped_lines) - 1) * line_spacing)
    
    # Calculate starting Y to center vertically
    current_y = center_y - (total_height // 2)
    
    space_width = best_font.getlength(" ")
    
    word_counter = 0
    # Draw word by word for multi-color
    for line in best_wrapped_lines:
        # Calculate width of this specific line
        line_str = " ".join(line)
        line_width = best_font.getlength(line_str)
        
        # Starting X for this line to center horizontally
        current_x = center_x - (line_width / 2)
        
        for word in line:
            # Determine color
            color = COLOR_CIVORA_RED if word_counter in highlight_indices else COLOR_TEXT
            
            # Draw the word
            draw.text((current_x, current_y), word, font=best_font, fill=color)
            
            # Move X forward
            current_x += best_font.getlength(word) + space_width
            word_counter += 1
            
        current_y += best_line_height + line_spacing


def main():
    if not os.path.exists(TEMPLATE_PATH):
        print(f"Error: Template image '{TEMPLATE_PATH}' not found in the directory!")
        return
        
    img = Image.open(TEMPLATE_PATH).convert("RGBA")
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    bg.paste(img, (0, 0), img)
    img = bg.convert("RGB")
    
    sample_headlines = [
        ("BIG BREAKING: SUPREME COURT STRIKES DOWN ELECTORAL BONDS AHEAD OF ELECTIONS.", [3, 4, 5]), # "SUPREME COURT STRIKES"
        ("GOVERNMENT ANNOUNCES NEW SUBSIDY SCHEME FOR FARMERS.", [3, 4]), # "SUBSIDY SCHEME"
        ("THE RESERVE BANK OF INDIA KEEPS REPO RATE UNCHANGED AT 6.5 PERCENT AMIDST GLOBAL ECONOMIC UNCERTAINTY.", [7, 8]) # "UNCHANGED AT"
    ]
    
    for i, (headline, highlight_idx_list) in enumerate(sample_headlines):
        img_copy = img.copy()
        draw_copy = ImageDraw.Draw(img_copy)
        
        draw_adaptive_multicolor_text(
            draw=draw_copy, 
            text=headline,
            bounding_box=padded_box, 
            font_path=FONT_PATH, 
            max_font_size=150, 
            highlight_indices=highlight_idx_list
        )
        
        out_name = f"test_poster_v3_{i+1}.png"
        img_copy.save(out_name)
        print(f"Successfully generated: {out_name}")

if __name__ == "__main__":
    main()
