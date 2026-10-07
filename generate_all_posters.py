import os
import openpyxl
from PIL import Image, ImageDraw, ImageFont, ImageFilter

TEMPLATE_BJP = r"C:\Users\DELL\Desktop\format\BJP.png"
TEMPLATE_SP = r"C:\Users\DELL\Desktop\format\SP.png"
TEMPLATE_OTHERS = r"C:\Users\DELL\Desktop\format\Others.png"
OUTPUT_DIR = r"C:\Users\DELL\Desktop\Civoratimes\bot\posters"

EXCEL_FILE = r"C:\Users\DELL\Desktop\Civoratimes\bot\UP_2027_Survey.xlsx"
wb = openpyxl.load_workbook(EXCEL_FILE)
ws = wb.active

FONT_NAME_PATH = "georgiab.ttf"
FONT_PCT_PATH = "arialbd.ttf"

COLOR_BLACK = "#111111"
COLOR_BJP_PCT = "#E85D00"
COLOR_SP_PCT = "#C51D25"
COLOR_OTHERS_PCT = "#555555"

# User's perfect coordinates
name_box = [104, 318, 1028, 422]
pct_bjp_box = [144, 964, 361, 1055]
pct_sp_box = [483, 964, 705, 1055]
pct_others_box = [801, 964, 1015, 1055]

CONFIG = {
    'NDA': {
        'template': TEMPLATE_BJP,
        'name_box': name_box,
        'pct_bjp_box': pct_bjp_box,
        'pct_sp_box': pct_sp_box,
        'pct_others_box': pct_others_box,
        'name_max_font': 90,
        'pct_max_font': 70
    },
    'INDIA': {
        'template': TEMPLATE_SP,
        'name_box': name_box,
        'pct_bjp_box': pct_bjp_box,
        'pct_sp_box': pct_sp_box,
        'pct_others_box': pct_others_box,
        'name_max_font': 90,
        'pct_max_font': 70
    },
    'OTHERS': {
        'template': TEMPLATE_OTHERS,
        'name_box': name_box,
        'pct_bjp_box': pct_bjp_box,
        'pct_sp_box': pct_sp_box,
        'pct_others_box': pct_others_box,
        'name_max_font': 90,
        'pct_max_font': 70
    }
}

def draw_faded_background(img, bounding_box):
    x1, y1, x2, y2 = bounding_box
    overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    # 70% opacity white fill (around 180 out of 255)
    # We add a slight padding inwards so the blur bleeds nicely out
    pad_x, pad_y = 60, 15
    overlay_draw.rectangle([x1+pad_x, y1+pad_y, x2-pad_x, y2-pad_y], fill=(255, 255, 255, 200))
    
    # Gaussian blur radius 30 gives a very nice soft fade
    blurred = overlay.filter(ImageFilter.GaussianBlur(radius=30))
    
    # Paste using alpha compositing
    img.paste(blurred, (0, 0), blurred)

def draw_adaptive_text(draw, text, bounding_box, font_path, max_font_size, text_color):
    x1, y1, x2, y2 = bounding_box
    max_width = x2 - x1
    max_height = y2 - y1
    center_x = (x1 + x2) // 2
    center_y = (y1 + y2) // 2
    
    font_size = max_font_size
    
    try:
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()
        draw.text((center_x, center_y), text, font=font, fill=text_color, anchor="mm")
        return

    while font_size > 10:
        bbox = draw.textbbox((0, 0), text, font=font, anchor="mm")
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        if text_width <= max_width and text_height <= max_height:
            break
            
        font_size -= 2
        font = ImageFont.truetype(font_path, font_size)
        
    draw.text((center_x, center_y), text, font=font, fill=text_color, anchor="mm")

# Generate only 3 samples for approval
nda_row, india_row, others_row = None, None, None
for row in range(2, ws.max_row+1):
    w = ws.cell(row, 13).value
    if w == 'NDA' and not nda_row: nda_row = row
    if w == 'INDIA' and not india_row: india_row = row
    if w == 'OTHERS' and not others_row: others_row = row
    if nda_row and india_row and others_row: break

for row, winner in [(nda_row, 'NDA'), (india_row, 'INDIA'), (others_row, 'OTHERS')]:
    if not row: continue
    constituency = str(ws.cell(row, 2).value).upper() + " ?"
    
    bjp_pct = ws.cell(row, 12).value or 0
    sp_pct = ws.cell(row, 11).value or 0
    others_pct = ws.cell(row, 15).value or 0
    
    bjp_str = f"{bjp_pct:.1f}%"
    sp_str = f"{sp_pct:.1f}%"
    others_str = f"{others_pct:.1f}%"
    
    conf = CONFIG[winner]
    template_path = conf['template']
    
    try:
        img = Image.open(template_path).convert("RGBA")
        draw_faded_background(img, conf['name_box'])
        
        img = img.convert("RGB")
        draw = ImageDraw.Draw(img)
        
        draw_adaptive_text(draw, constituency, conf['name_box'], FONT_NAME_PATH, conf['name_max_font'], COLOR_BLACK)
        draw_adaptive_text(draw, bjp_str, conf['pct_bjp_box'], FONT_PCT_PATH, conf['pct_max_font'], COLOR_BJP_PCT)
        draw_adaptive_text(draw, sp_str, conf['pct_sp_box'], FONT_PCT_PATH, conf['pct_max_font'], COLOR_SP_PCT)
        draw_adaptive_text(draw, others_str, conf['pct_others_box'], FONT_PCT_PATH, conf['pct_max_font'], COLOR_OTHERS_PCT)
        
        out_path = os.path.join(OUTPUT_DIR, f"SAMPLE_FADE_{winner}.png")
        img.save(out_path)
    except Exception as e:
        print(f"Error {winner}: {e}")
