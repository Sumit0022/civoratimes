import os
import json
import io
import time
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import tweepy

# Load environment variables (for local testing via .env file)
load_dotenv()

# Configuration
DRIVE_QUEUE_FOLDER_ID = os.getenv("DRIVE_QUEUE_FOLDER_ID")
DRIVE_POSTED_FOLDER_ID = os.getenv("DRIVE_POSTED_FOLDER_ID")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

TWITTER_CONSUMER_KEY = os.getenv("TWITTER_CONSUMER_KEY")
TWITTER_CONSUMER_SECRET = os.getenv("TWITTER_CONSUMER_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

def get_drive_service():
    """Authenticate and return the Google Drive service."""
    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON environment variable is not set.")
    
    credentials_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    credentials = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=['https://www.googleapis.com/auth/drive']
    )
    return build('drive', 'v3', credentials=credentials)

def get_next_image_from_queue(drive_service):
    """Finds the first image in the Queue folder."""
    query = f"'{DRIVE_QUEUE_FOLDER_ID}' in parents and mimeType contains 'image/' and trashed=false"
    results = drive_service.files().list(
        q=query,
        orderBy="name",
        fields="files(id, name, description, parents)",
        pageSize=1
    ).execute()
    
    items = results.get('files', [])
    if not items:
        return None
    return items[0]

def find_text_file_for_image(drive_service, base_name):
    """Finds a matching .txt file for the image."""
    text_file_name = f"{base_name}.txt"
    # Search by exact name and parent folder
    query = f"'{DRIVE_QUEUE_FOLDER_ID}' in parents and name = '{text_file_name}' and trashed=false"
    results = drive_service.files().list(
        q=query,
        fields="files(id, name, parents)",
        pageSize=1
    ).execute()
    
    items = results.get('files', [])
    if not items:
        return None
    return items[0]

def download_file_content(drive_service, file_id, file_name):
    """Downloads a file from Google Drive to a local file."""
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.FileIO(file_name, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    return file_name

def read_text_file(file_path):
    """Reads the downloaded text file to get the caption."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read().strip()

def move_file_to_posted(drive_service, file_id, previous_parents):
    """Moves a file from the Queue folder to the Posted folder."""
    previous_parents_str = ",".join(previous_parents)
    drive_service.files().update(
        fileId=file_id,
        addParents=DRIVE_POSTED_FOLDER_ID,
        removeParents=previous_parents_str,
        fields='id, parents'
    ).execute()

def post_to_twitter(image_path, caption):
    """Uploads the image and posts a tweet."""
    # V1.1 API for media upload
    auth = tweepy.OAuth1UserHandler(
        consumer_key=TWITTER_CONSUMER_KEY,
        consumer_secret=TWITTER_CONSUMER_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_TOKEN_SECRET
    )
    api_v1 = tweepy.API(auth)
    
    # V2 API for tweeting
    client = tweepy.Client(
        consumer_key=TWITTER_CONSUMER_KEY,
        consumer_secret=TWITTER_CONSUMER_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_TOKEN_SECRET
    )
    
    print(f"Uploading {image_path} to Twitter...")
    media = api_v1.media_upload(filename=image_path)
    
    print(f"Posting tweet...")
    response = client.create_tweet(text=caption, media_ids=[media.media_id])
    print(f"Tweet successful! Link: https://twitter.com/user/status/{response.data['id']}")

def main():
    try:
        drive_service = get_drive_service()
        
        print("Checking Queue folder for images...")
        image = get_next_image_from_queue(drive_service)
        
        if not image:
            print("No images found in the Queue folder. Exiting.")
            return
            
        image_id = image['id']
        image_name = image['name']
        base_name = os.path.splitext(image_name)[0]
        
        print(f"Found image: {image_name}")
        
        # 1. Look for matching .txt file
        text_file = find_text_file_for_image(drive_service, base_name)
        
        caption = ""
        local_text_filename = None
        
        if text_file:
            print(f"Found matching text file for caption: {text_file['name']}")
            local_text_filename = f"temp_{text_file['name']}"
            download_file_content(drive_service, text_file['id'], local_text_filename)
            caption = read_text_file(local_text_filename)
        else:
            # 2. Fallback to Drive description or filename
            print("No matching .txt file found. Using Drive description or filename.")
            caption = image.get('description', '')
            if not caption:
                caption = base_name
                
        print(f"Final Caption to post: {caption}")
        
        # Download image
        local_image_filename = f"temp_{image_name}"
        download_file_content(drive_service, image_id, local_image_filename)
        
        # Post to Twitter
        post_to_twitter(local_image_filename, caption)
        
        # Move image to Posted folder
        move_file_to_posted(drive_service, image_id, image.get('parents', []))
        print(f"Moved {image_name} to Posted folder.")
        
        # Move text file to Posted folder if it exists
        if text_file:
            move_file_to_posted(drive_service, text_file['id'], text_file.get('parents', []))
            print(f"Moved {text_file['name']} to Posted folder.")
        
        # Clean up local files
        if os.path.exists(local_image_filename):
            os.remove(local_image_filename)
        if local_text_filename and os.path.exists(local_text_filename):
            os.remove(local_text_filename)
            
        print("Process completed successfully.")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
