import os
import time
import requests
import feedparser
from datetime import datetime
from PIL import Image, ImageDraw
import tweepy

# Import the drawing logic
from generate_news_poster import draw_adaptive_multicolor_text, padded_box, FONT_PATH, TEMPLATE_PATH
import google.generativeai as genai

HISTORY_FILE = "posted_news.txt"

FEEDS = [
    'https://news.google.com/rss/search?q=site:thewire.in+OR+site:newslaundry.com+OR+site:nationalheraldindia.com+when:1h&hl=en-IN&gl=IN&ceid=IN:en'
]

# Setup APIs from environment variables (fallback to hardcoded for Gemini just in case)
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", "AIzaSyBRhLie01nIf58UctegmVYwY28zGelg1Y4"))
model = genai.GenerativeModel('gemini-flash-latest')

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())

def save_to_history(news_id):
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        f.write(news_id + "\n")

def generate_ai_tagline(raw_headline):
    prompt = f"You are a news editor. Rewrite this news headline into a short, punchy, aggressive 'Breaking News' style tagline (MAXIMUM 8 words). Do not use any quotes or emojis. Keep it extremely bold and readable.\nHeadline: {raw_headline}"
    try:
        response = model.generate_content(prompt)
        return response.text.strip().replace('"', '').replace("'", "")
    except Exception as e:
        print(f"AI Error: {e}")
        return raw_headline

def fetch_fresh_news(history):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking RSS feeds...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    fresh_items = []
    
    for url in FEEDS:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            feed = feedparser.parse(r.text)
            if feed.entries:
                for entry in feed.entries[:3]:
                    news_id = entry.link
                    if news_id not in history:
                        raw_title = entry.title.split(" - ")[0]
                        print(f"Found new news: {raw_title}")
                        ai_tagline = generate_ai_tagline(raw_title)
                        fresh_items.append({
                            'title': ai_tagline,
                            'original_title': raw_title,
                            'link': entry.link,
                            'source': url.split('.')[1].upper()
                        })
        except Exception as e:
            print(f"Error fetching {url}: {e}")
    return fresh_items

def create_poster(news):
    if not os.path.exists(TEMPLATE_PATH):
        print(f"Error: Template image not found!")
        return None, None

    base_img = Image.open(TEMPLATE_PATH).convert("RGBA")
    bg = Image.new("RGBA", base_img.size, (255, 255, 255, 255))
    bg.paste(base_img, (0, 0), base_img)
    base_img = bg.convert("RGB")
    
    headline = news['title'].upper()
    img_copy = base_img.copy()
    draw = ImageDraw.Draw(img_copy)
    
    words = headline.split()
    longest_word = max(words, key=len) if words else ""
    key_idx = words.index(longest_word) if words else 0
    
    draw_adaptive_multicolor_text(
        draw=draw, 
        text=headline,
        bounding_box=padded_box, 
        font_path=FONT_PATH, 
        max_font_size=150, 
        key_word_index=key_idx
    )
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_filename = f"LiveNews_{timestamp}.png"
    img_copy.save(out_filename)
    
    caption_text = f"🚨 BREAKING NEWS 🚨\n\n{news['original_title']}.\n\nRead more at: {news['link']}\n\n#CivoraTimes #News #BreakingNews #India"
    
    return out_filename, caption_text

def post_to_twitter(image_path, caption):
    try:
        auth = tweepy.OAuth1UserHandler(
            consumer_key=os.environ.get("TWITTER_CONSUMER_KEY"),
            consumer_secret=os.environ.get("TWITTER_CONSUMER_SECRET"),
            access_token=os.environ.get("TWITTER_ACCESS_TOKEN"),
            access_token_secret=os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")
        )
        api_v1 = tweepy.API(auth)
        
        client = tweepy.Client(
            consumer_key=os.environ.get("TWITTER_CONSUMER_KEY"),
            consumer_secret=os.environ.get("TWITTER_CONSUMER_SECRET"),
            access_token=os.environ.get("TWITTER_ACCESS_TOKEN"),
            access_token_secret=os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")
        )
        
        print("Uploading media to X...")
        media = api_v1.media_upload(image_path)
        print("Posting tweet...")
        response = client.create_tweet(text=caption, media_ids=[media.media_id])
        print(f"Successfully posted! Tweet ID: {response.data['id']}")
        return True
    except Exception as e:
        print(f"Error posting to X: {e}")
        return False

def main():
    history = load_history()
    fresh_news = fetch_fresh_news(history)
    
    if not fresh_news:
        print("No new news found.")
        return
        
    # We only process ONE news item per run so we don't spam Twitter
    for news in fresh_news:
        img_path, caption = create_poster(news)
        if img_path:
            # Uncomment this to enable actual posting
            success = post_to_twitter(img_path, caption)
            if success:
                save_to_history(news['link'])
                print("Posted one news item. Exiting to wait for next cron run.")
                break

if __name__ == "__main__":
    main()
