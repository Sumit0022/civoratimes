#!/usr/bin/env python3
"""
Social Media Auto-Poster from Google Drive to X.com and Instagram
=================================================================
Automates fetching the next image from a Google Drive queue folder,
posting it to X (Twitter) and/or Instagram with a caption, and moving
it to a 'Posted' archive folder.
"""

import os
import sys
import json
import time
import tempfile
import requests

# Google Drive API
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Twitter / X API
try:
    import tweepy
except ImportError:
    tweepy = None


def get_drive_service():
    """Authenticates and returns the Google Drive API service using a Service Account."""
    sa_json_raw = os.getenv("GDRIVE_SERVICE_ACCOUNT_JSON")
    if not sa_json_raw:
        raise ValueError("Missing environment variable: GDRIVE_SERVICE_ACCOUNT_JSON")

    try:
        sa_info = json.loads(sa_json_raw)
    except json.JSONDecodeError as err:
        raise ValueError(f"Invalid JSON in GDRIVE_SERVICE_ACCOUNT_JSON: {err}")

    credentials = service_account.Credentials.from_service_account_info(
        sa_info, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=credentials)


def find_next_post_item(service, folder_id):
    """
    Finds the oldest unprocessed image file in the queue folder.
    Also checks if a matching caption (.txt) file exists with the same base name.
    """
    query = f"'{folder_id}' in parents and mimeType contains 'image/' and trashed = false"
    results = service.files().list(
        q=query,
        orderBy="createdTime asc",
        fields="files(id, name, mimeType, createdTime)",
        pageSize=10
    ).execute()
    files = results.get("files", [])
    if not files:
        print("[INFO] No images found in Google Drive queue folder.")
        return None, None, None

    image_file = files[0]
    base_name = os.path.splitext(image_file["name"])[0]

    # Look for matching caption text file
    caption_query = (
        f"'{folder_id}' in parents and name = '{base_name}.txt' "
        f"and mimeType = 'text/plain' and trashed = false"
    )
    caption_results = service.files().list(
        q=caption_query,
        fields="files(id, name)"
    ).execute()
    caption_files = caption_results.get("files", [])

    caption_file = caption_files[0] if caption_files else None
    return image_file, caption_file, base_name


def download_drive_file(service, file_id, destination_path):
    """Downloads a file from Google Drive to local disk."""
    request = service.files().get_media(fileId=file_id)
    with open(destination_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()


def read_drive_text(service, file_id):
    """Reads content of a text file from Google Drive."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = tmp.name
    try:
        download_drive_file(service, file_id, tmp_path)
        with open(tmp_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def move_file_in_drive(service, file_id, source_folder_id, target_folder_id):
    """Moves a file from one folder to another in Google Drive."""
    service.files().update(
        fileId=file_id,
        addParents=target_folder_id,
        removeParents=source_folder_id,
        fields="id, parents"
    ).execute()
    print(f"[OK] Moved file {file_id} to archive folder.")


# -------------------------------------------------------------
# X.com (Twitter) Posting
# -------------------------------------------------------------
def post_to_x(image_path, caption):
    """Posts an image and caption to X.com using Twitter API v1.1 and v2."""
    api_key = os.getenv("TWITTER_API_KEY")
    api_secret = os.getenv("TWITTER_API_SECRET")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    access_secret = os.getenv("TWITTER_ACCESS_SECRET")

    if not all([api_key, api_secret, access_token, access_secret]):
        print("[SKIP] X (Twitter) credentials not fully configured.")
        return False

    if not tweepy:
        print("[ERROR] Tweepy package not installed.")
        return False

    print("[INFO] Uploading image and posting tweet to X...")
    # v1.1 auth for media upload
    auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
    api_v1 = tweepy.API(auth)

    media = api_v1.media_upload(filename=image_path)
    print(f"[OK] Media uploaded to X. Media ID: {media.media_id_string}")

    # v2 client for creating tweet
    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret
    )
    # Twitter tweet length limit is 280 chars
    tweet_text = caption if len(caption) <= 280 else caption[:277] + "..."
    response = client.create_tweet(text=tweet_text, media_ids=[media.media_id_string])
    print(f"[SUCCESS] Tweet posted to X.com! Tweet ID: {response.data['id']}")
    return True


# -------------------------------------------------------------
# Instagram Graph API Posting
# -------------------------------------------------------------
def upload_image_to_public_host(image_path):
    """
    Instagram Graph API requires a publicly accessible image URL.
    Option A: Uses Cloudinary if CLOUDINARY_CLOUD_NAME & upload preset are provided.
    Option B: Uses Imgur anonymous API if IMGUR_CLIENT_ID is provided.
    Option C: Direct fallback if a PUBLIC_IMAGE_BASE_URL is configured.
    """
    imgur_client_id = os.getenv("IMGUR_CLIENT_ID")
    if imgur_client_id:
        headers = {"Authorization": f"Client-ID {imgur_client_id}"}
        with open(image_path, "rb") as img:
            res = requests.post(
                "https://api.imgur.com/3/image",
                headers=headers,
                files={"image": img},
                timeout=30
            )
        if res.status_code == 200:
            link = res.json()["data"]["link"]
            print(f"[OK] Image hosted on Imgur: {link}")
            return link

    cloudinary_cloud = os.getenv("CLOUDINARY_CLOUD_NAME")
    cloudinary_preset = os.getenv("CLOUDINARY_UPLOAD_PRESET")
    if cloudinary_cloud and cloudinary_preset:
        upload_url = f"https://api.cloudinary.com/v1_1/{cloudinary_cloud}/image/upload"
        with open(image_path, "rb") as img:
            res = requests.post(
                upload_url,
                data={"upload_preset": cloudinary_preset},
                files={"file": img},
                timeout=30
            )
        if res.status_code == 200:
            link = res.json()["secure_url"]
            print(f"[OK] Image hosted on Cloudinary: {link}")
            return link

    return None


def post_to_instagram(public_image_url, caption):
    """Posts an image with caption to Instagram Professional via Meta Graph API."""
    ig_user_id = os.getenv("INSTAGRAM_USER_ID")
    access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")

    if not ig_user_id or not access_token:
        print("[SKIP] Instagram credentials not configured.")
        return False

    if not public_image_url:
        print("[SKIP] Public image URL not available for Instagram posting.")
        return False

    print("[INFO] Creating Instagram media container...")
    # Step 1: Create media container
    create_url = f"https://graph.facebook.com/v20.0/{ig_user_id}/media"
    payload = {
        "image_url": public_image_url,
        "caption": caption,
        "access_token": access_token
    }
    res = requests.post(create_url, data=payload, timeout=30)
    data = res.json()
    if "id" not in data:
        print(f"[ERROR] Instagram container creation failed: {data}")
        return False

    creation_id = data["id"]
    print(f"[OK] Instagram container created: {creation_id}. Checking readiness...")

    # Wait for container processing (usually 5-10 seconds)
    for _ in range(6):
        time.sleep(5)
        status_url = f"https://graph.facebook.com/v20.0/{creation_id}?fields=status_code&access_token={access_token}"
        status_res = requests.get(status_url, timeout=15).json()
        status_code = status_res.get("status_code")
        if status_code == "FINISHED":
            break
        elif status_code == "ERROR":
            print(f"[ERROR] Media container failed processing: {status_res}")
            return False

    # Step 2: Publish media container
    print("[INFO] Publishing media to Instagram feed...")
    publish_url = f"https://graph.facebook.com/v20.0/{ig_user_id}/media_publish"
    pub_payload = {
        "creation_id": creation_id,
        "access_token": access_token
    }
    pub_res = requests.post(publish_url, data=pub_payload, timeout=30).json()
    if "id" in pub_res:
        print(f"[SUCCESS] Post published to Instagram! Post ID: {pub_res['id']}")
        return True
    else:
        print(f"[ERROR] Failed to publish Instagram post: {pub_res}")
        return False


# -------------------------------------------------------------
# Main Execution Orchestrator
# -------------------------------------------------------------
def main():
    print("--- Starting Social Media Auto-Poster ---")
    queue_folder_id = os.getenv("GDRIVE_QUEUE_FOLDER_ID")
    posted_folder_id = os.getenv("GDRIVE_POSTED_FOLDER_ID")
    default_caption = os.getenv("DEFAULT_CAPTION", "New update! #daily #update")

    if not queue_folder_id:
        print("[FATAL] GDRIVE_QUEUE_FOLDER_ID is required.")
        sys.exit(1)

    drive_service = get_drive_service()
    image_file, caption_file, base_name = find_next_post_item(drive_service, queue_folder_id)

    if not image_file:
        print("[INFO] Queue is empty. Nothing to post today.")
        sys.exit(0)

    print(f"[INFO] Next item to post: {image_file['name']} (ID: {image_file['id']})")

    # Read caption from .txt if present, else use default
    if caption_file:
        caption = read_drive_text(drive_service, caption_file["id"])
        print(f"[INFO] Found matching caption file '{caption_file['name']}'.")
    else:
        caption = default_caption
        print(f"[INFO] No custom caption file found. Using default caption.")

    # Download image to local temp folder
    ext = os.path.splitext(image_file["name"])[1] or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_img:
        local_img_path = tmp_img.name

    try:
        download_drive_file(drive_service, image_file["id"], local_img_path)
        print(f"[OK] Downloaded {image_file['name']} locally.")

        posted_any = False

        # 1. Post to X.com
        if post_to_x(local_img_path, caption):
            posted_any = True

        # 2. Post to Instagram
        if os.getenv("INSTAGRAM_USER_ID") and os.getenv("INSTAGRAM_ACCESS_TOKEN"):
            public_url = upload_image_to_public_host(local_img_path)
            if public_url:
                if post_to_instagram(public_url, caption):
                    posted_any = True
            else:
                print("[WARN] Skipping Instagram: could not generate public URL for image.")

        # 3. Move image (and caption file) to archive folder if posted
        if posted_any and posted_folder_id:
            move_file_in_drive(drive_service, image_file["id"], queue_folder_id, posted_folder_id)
            if caption_file:
                move_file_in_drive(drive_service, caption_file["id"], queue_folder_id, posted_folder_id)
            print("[SUCCESS] Processing completed successfully.")
        elif not posted_any:
            print("[WARN] No platforms were posted to. Check your platform credentials.")

    finally:
        if os.path.exists(local_img_path):
            os.remove(local_img_path)


if __name__ == "__main__":
    main()
