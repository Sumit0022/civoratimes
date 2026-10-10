import os
import time
import requests
import feedparser
from datetime import datetime
import json
from PIL import Image, ImageDraw
import tweepy

# Import the drawing logic
from generate_news_poster import draw_adaptive_multicolor_text, padded_box, FONT_PATH, TEMPLATE_PATH

HISTORY_FILE = "posted_news.txt"
TITLES_FILE = "posted_titles.txt"

import urllib.parse
import re

# 11 Independent/Left-leaning credible sources
sites_g1 = "site:thewire.in OR site:newslaundry.com OR site:scroll.in OR site:nationalheraldindia.com"
sites_g2 = "site:thequint.com OR site:caravanmagazine.in OR site:article-14.com OR site:maktoobmedia.com"
sites_g3 = "site:thenewsminute.com OR site:altnews.in OR site:deccanherald.com"

q1 = f"(Delhi OR New Delhi OR CJP OR protest OR police) ({sites_g1}) when:3h"
q2 = f"(Delhi OR New Delhi OR CJP OR protest OR police) ({sites_g2}) when:3h"
q3 = f"(Delhi OR New Delhi OR CJP OR protest OR police) ({sites_g3}) when:3h"

FEEDS = [
    f"https://news.google.com/rss/search?q={urllib.parse.quote(q1)}&hl=en-IN&gl=IN&ceid=IN:en",
    f"https://news.google.com/rss/search?q={urllib.parse.quote(q2)}&hl=en-IN&gl=IN&ceid=IN:en",
    f"https://news.google.com/rss/search?q={urllib.parse.quote(q3)}&hl=en-IN&gl=IN&ceid=IN:en"
]

API_KEY = os.environ.get("GEMINI_API_KEY")

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())

def save_to_history(news_id):
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        f.write(news_id + "\n")

def load_titles():
    if not os.path.exists(TITLES_FILE):
        return []
    with open(TITLES_FILE, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def save_title(title):
    with open(TITLES_FILE, 'a', encoding='utf-8') as f:
        f.write(title.replace('\n', ' ') + "\n")

def is_similar(t1, t2):
    stop = {'the', 'in', 'of', 'and', 'to', 'a', 'is', 'for', 'on', 'by', 'at', 'with', 'from', 'as', 'are', 'scroll', 'wire', 'quint', 'newslaundry'}
    w1 = set(w.lower() for w in re.findall(r'\w+', t1)) - stop
    w2 = set(w.lower() for w in re.findall(r'\w+', t2)) - stop
    if not w1 or not w2:
        return False
    intersection = w1.intersection(w2)
    return (len(intersection) / min(len(w1), len(w2))) > 0.55

def generate_ai_content(raw_headline):
    prompt = f"""You are a news editor for 'Civora Times', focusing on Indian politics and breaking emergencies. I will give you a news headline about the current Delhi protest/emergency and CJP. 
You must generate SIX things:
1. "tagline": A catchy, punchy, and extremely bold tagline for the poster (MAXIMUM 15 words). Do not use quotes or emojis.
2. "summary": Provide a detailed 4-5 line comprehensive brief about the situation. Capture the tension, force deployment, CJP updates, EXPLICITLY mention who is being detained or arrested (names, groups, or numbers), and exact ground details. DO NOT use explicit labels. Write it as a flowing, highly engaging news update.
3. "is_breaking": Set to true as this is an ongoing emergency.
4. "hashtags": Generate EXACTLY 2 highly searchable, generic hashtags (e.g., #DelhiProtest, #CJP). DO NOT use brand tags.
5. "highlight_phrase": Identify the 2-4 most impactful words from the tagline to be highlighted in red. This MUST be an exact substring of the tagline.
6. "skip": A boolean (true or false). Set to true ONLY if the headline is vague, an opinion piece, or lacks concrete on-ground facts about the Delhi protests/CJP. Set to false if it contains hard news and facts.

Respond ONLY with a valid JSON object in this format:
{{
    "tagline": "SHORT HEADLINE HERE",
    "summary": "Massive forces have been deployed at the borders... (4-5 lines of detailed text)",
    "is_breaking": true,
    "hashtags": "#DelhiProtest #CJP",
    "highlight_phrase": "HEADLINE HERE",
    "skip": false
}}

Headline: {raw_headline}"""

    MODELS = [
        "gemini-3.6-flash",
        "gemini-2.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.7-flash",
        "gemini-3.8-flash",
        "gemini-flash-latest",
        "gemini-3.5-flash-lite",
        "gemini-2.5-pro"
    ]
    
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    for model_name in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={API_KEY}"
        print(f"Trying AI model: {model_name}...")
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 429:
                print(f"Model {model_name} quota exhausted. Trying next model...")
                continue
                
            if response.status_code == 503:
                print(f"Model {model_name} overloaded (503). Trying next model...")
                continue
                
            response.raise_for_status()
            result = response.json()
            text = result['candidates'][0]['content']['parts'][0]['text'].strip()
            
            # Robust JSON extraction
            import re
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                text = json_match.group(0)
                
            content = json.loads(text)
            return (
                content.get("tagline", raw_headline).replace('"', '').replace("'", ""), 
                content.get("summary", raw_headline), 
                content.get("is_breaking", False),
                content.get("hashtags", "#CivoraTimes #News #India"),
                content.get("highlight_phrase", ""),
                content.get("skip", False)
            )
            
        except Exception as e:
            print(f"Error with model {model_name}: {e}")
            continue
            
    # Fallback to original headline if ALL models completely fail
    print("All AI models failed or exhausted quota. Using fallback.")
    return raw_headline, raw_headline, False, "#CivoraTimes #News #India", "", False

def fetch_fresh_news(history, posted_titles):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking RSS feeds...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    fresh_items = []
    
    for url in FEEDS:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            feed = feedparser.parse(r.text)
            if feed.entries:
                for entry in feed.entries[:5]:
                    news_id = entry.link
                    if news_id not in history:
                        raw_title = entry.title.split(" - ")[0]
                        
                        # Semantic deduplication check
                        is_duplicate = False
                        for old_title in posted_titles[-50:]:  # Check last 50 titles
                            if is_similar(raw_title, old_title):
                                is_duplicate = True
                                print(f"Skipping duplicate event: '{raw_title}' is too similar to '{old_title}'")
                                history.add(news_id)
                                save_to_history(news_id)
                                break
                                
                        if not is_duplicate:
                            print(f"Found new news candidate: {raw_title}")
                            fresh_items.append({
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
    
    headline = news['tagline'].upper()
    img_copy = base_img.copy()
    draw = ImageDraw.Draw(img_copy)
    
    words = headline.split()
    highlight_indices = []
    
    highlight_phrase = news.get('highlight_phrase', '').upper().strip()
    if highlight_phrase:
        import string
        def clean_word(w):
            return w.strip(string.punctuation)
            
        hw = highlight_phrase.split()
        for i in range(len(words) - len(hw) + 1):
            match = True
            for j in range(len(hw)):
                if clean_word(words[i+j]) != clean_word(hw[j]):
                    match = False
                    break
            if match:
                highlight_indices = list(range(i, i+len(hw)))
                break
                
    # Fallback to the longest word if phrase matching fails
    if not highlight_indices and words:
        longest_word = max(words, key=len)
        highlight_indices = [words.index(longest_word)]
    
    draw_adaptive_multicolor_text(
        draw=draw, 
        text=headline,
        bounding_box=padded_box, 
        font_path=FONT_PATH, 
        max_font_size=350, 
        highlight_indices=highlight_indices
    )
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_filename = f"LiveNews_{timestamp}.png"
    img_copy.save(out_filename)
    
    breaking_prefix = "🚨 BREAKING NEWS 🚨\n\n" if news.get('is_breaking') else ""
    caption_text = f"{breaking_prefix}{news['summary']}\n\n{news['hashtags']}"
    
    return out_filename, caption_text

def send_to_telegram(image_path, caption):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("Telegram credentials not found. Skipping Telegram message.")
        return False
        
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        with open(image_path, 'rb') as photo:
            payload = {'chat_id': chat_id, 'caption': caption}
            response = requests.post(url, data=payload, files={'photo': photo})
            if response.status_code == 200:
                print("Successfully sent poster to Telegram!")
                return True
            else:
                print(f"Telegram API Error: {response.text}")
                return False
    except Exception as e:
        print(f"Error sending to Telegram: {e}")
        return False

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
        
        media_ids = []
        if image_path:
            print("Uploading media to X...")
            if image_path.lower().endswith('.mp4'):
                media = api_v1.media_upload(image_path, media_category="tweet_video", chunked=True)
                print("Video uploaded. Checking processing status...")
                import time
                processing_info = getattr(media, 'processing_info', None)
                while processing_info and processing_info.get('state') in ['pending', 'in_progress']:
                    wait_time = processing_info.get('check_after_secs', 5)
                    print(f"Waiting {wait_time} seconds for video processing...")
                    time.sleep(wait_time)
                    
                    try:
                        media_status = api_v1.get_media_upload_status(media.media_id)
                        processing_info = getattr(media_status, 'processing_info', None)
                    except Exception as e:
                        print(f"Status check error: {e}. Just waiting 15s and hoping for the best.")
                        time.sleep(15)
                        break
                        
                if processing_info and processing_info.get('state') == 'failed':
                    print("Twitter video processing failed!")
                    return False, "Twitter backend failed to process this video. The file might be too large or unsupported on the Free API tier."
                
                media_ids = [media.media_id]
            else:
                media = api_v1.media_upload(image_path)
                media_ids = [media.media_id]
            
        print("Posting tweet...")
        
        # client.create_tweet wants media_ids as a list or omitted
        kwargs = {"text": caption}
        if media_ids:
            kwargs["media_ids"] = media_ids
            
        response = client.create_tweet(**kwargs)
        print(f"Successfully posted! Tweet ID: {response.data['id']}")
        return True, ""
    except Exception as e:
        print(f"Error posting to X: {e}")
        return False, str(e)

def main():
    if os.path.exists("telegram_posted.flag"):
        print("Telegram manual post took priority this cycle. Skipping RSS feeds to avoid spam.")
        os.remove("telegram_posted.flag")
        return

    history = load_history()
    posted_titles = load_titles()
    fresh_news = fetch_fresh_news(history, posted_titles)
    
    if not fresh_news:
        print("No new news found.")
        return
        
    for news in fresh_news:
        print(f"Processing AI for: {news['original_title']}")
        tagline, summary, is_breaking, hashtags, highlight_phrase, should_skip = generate_ai_content(news['original_title'])
        
        if should_skip:
            print("AI marked this news as vague/irrelevant. Skipping.")
            continue
            
        news['tagline'] = tagline
        news['summary'] = summary
        news['is_breaking'] = is_breaking
        news['hashtags'] = hashtags
        news['highlight_phrase'] = highlight_phrase
        
        img_path, caption = create_poster(news)
        if img_path:
            success_tw, error_msg = post_to_twitter(img_path, caption)
            send_to_telegram(img_path, caption)
            
            if success_tw:
                save_to_history(news['link'])
                save_title(news['original_title'])
                print("Posted one news item. Exiting to wait for next cron run.")
                break
    
    print("Emergency news run complete.")

if __name__ == "__main__":
    main()
