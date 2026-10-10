import os
import requests
import re
import json

from github_newsroom import generate_ai_content, post_to_twitter, create_poster

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
OFFSET_FILE = "telegram_offset.txt"

def get_last_offset():
    if os.path.exists(OFFSET_FILE):
        with open(OFFSET_FILE, "r") as f:
            return int(f.read().strip())
    return 0

def set_last_offset(offset):
    with open(OFFSET_FILE, "w") as f:
        f.write(str(offset))

def send_msg(text):
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text})

def get_vxtwitter_data(tweet_url):
    match = re.search(r'(?:twitter\.com|x\.com)/([^/]+/status/\d+)', tweet_url)
    if not match:
        return None
    api_url = f"https://api.vxtwitter.com/{match.group(1)}"
    try:
        resp = requests.get(api_url, timeout=15).json()
        return resp
    except:
        return None

def process_telegram_links():
    if not BOT_TOKEN:
        print("No Telegram token, skipping.")
        return

    offset = get_last_offset() + 1
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=10"
    try:
        resp = requests.get(url).json()
        if not resp.get("ok"):
            return
        updates = resp.get("result", [])
    except:
        return

    if not updates:
        return

    highest_offset = get_last_offset()
    
    for update in updates:
        update_id = update["update_id"]
        if update_id > highest_offset:
            highest_offset = update_id

        message = update.get("message", {})
        text = message.get("text", "")
        
        urls = re.findall(r'(https?://(?:www\.)?(?:twitter\.com|x\.com)/[^\s]+)', text)
        if urls:
            for tweet_url in urls:
                send_msg(f"⏳ Found X link! Fetching tweet data...")
                tweet_data = get_vxtwitter_data(tweet_url)
                if not tweet_data:
                    send_msg(f"❌ Error: Could not read tweet from {tweet_url}")
                    continue
                
                tweet_text = tweet_data.get("text", "")
                author = tweet_data.get("user_name", "")
                media_urls = tweet_data.get("mediaURLs", [])
                
                send_msg("🧠 Sending to AI for News Brief generation...")
                # We construct a prompt-friendly raw headline
                ai_input = f"Official Notice/Statement by {author}: {tweet_text[:300]}"
                tagline, summary, is_breaking, hashtags, highlight_phrase, should_skip = generate_ai_content(ai_input)
                
                if should_skip:
                    send_msg("⚠️ AI skipped this tweet (marked as vague or irrelevant to current filters).")
                    continue
                    
                breaking_prefix = "🚨 BREAKING NEWS 🚨\n\n" if is_breaking else ""
                caption = f"{breaking_prefix}{summary}\n\n{hashtags}"
                
                img_path = None
                if media_urls:
                    media_url = media_urls[0]
                    if media_url.endswith('.mp4'):
                        img_path = "tweet_video.mp4"
                        try:
                            with open(img_path, 'wb') as f:
                                f.write(requests.get(media_url, timeout=30).content)
                        except:
                            img_path = None
                    elif media_url.endswith(('.png', '.jpg', '.jpeg')):
                        img_path = "tweet_media.jpg"
                        try:
                            with open(img_path, 'wb') as f:
                                f.write(requests.get(media_url, timeout=15).content)
                        except:
                            img_path = None
                    else:
                        # Check media_extended just in case
                        media_ext = tweet_data.get("media_extended", [])
                        if media_ext and media_ext[0].get("url", "").endswith('.mp4'):
                            img_path = "tweet_video.mp4"
                            try:
                                with open(img_path, 'wb') as f:
                                    f.write(requests.get(media_ext[0]["url"], timeout=30).content)
                            except:
                                img_path = None
                
                if not img_path:
                    # Fallback to creating our classic red/black poster if no image or it's a video
                    news_dict = {
                        'tagline': tagline,
                        'summary': summary,
                        'is_breaking': is_breaking,
                        'hashtags': hashtags,
                        'highlight_phrase': highlight_phrase
                    }
                    img_path, _ = create_poster(news_dict)

                if img_path:
                    send_msg("📤 Uploading to X (Twitter)...")
                    success, error_msg = post_to_twitter(img_path, caption)
                    if success:
                        send_msg(f"✅ Successfully posted to your X account!\n\nCaption used:\n{caption}")
                    else:
                        send_msg(f"❌ Failed to post to X.\nError: {error_msg}")
                else:
                    send_msg("❌ Error creating poster or downloading media.")
        elif text and not text.startswith('/'):
            send_msg("📝 Manual text detected! Generating AI News Brief & Poster...")
            ai_input = f"Manual Breaking News Report: {text}"
            tagline, summary, is_breaking, hashtags, highlight_phrase, should_skip = generate_ai_content(ai_input)
            
            if should_skip:
                send_msg("⚠️ AI skipped this text (marked as vague or irrelevant).")
                continue
                
            breaking_prefix = "🚨 BREAKING NEWS 🚨\n\n" if is_breaking else ""
            caption = f"{breaking_prefix}{summary}\n\n{hashtags}"
            
            news_dict = {
                'tagline': tagline,
                'summary': summary,
                'is_breaking': is_breaking,
                'hashtags': hashtags,
                'highlight_phrase': highlight_phrase
            }
            img_path, _ = create_poster(news_dict)

            if img_path:
                send_msg("📤 Uploading poster to X (Twitter)...")
                success, error_msg = post_to_twitter(img_path, caption)
                if success:
                    send_msg(f"✅ Successfully posted manual news to X!\n\nCaption used:\n{caption}")
                else:
                    send_msg(f"❌ Failed to post manual news to X.\nError: {error_msg}")
            else:
                send_msg("❌ Error creating poster for manual news.")
                
    set_last_offset(highest_offset)

if __name__ == "__main__":
    print("Checking Telegram for X links and manual text...")
    process_telegram_links()
