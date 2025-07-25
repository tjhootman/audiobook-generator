"""Modules for authenticating and uploading videos to YouTube. """

import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# The YouTube Data API scopes required for uploading videos.
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

def authenticate_youtube():
    """Authenticates with YouTube and returns the YouTube service object."""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("./credentials/token.json"):
        creds = Credentials.from_authorized_user_file("./credentials/token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "./credentials/client_secret.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("./credentials/token.json", "w") as token:
            token.write(creds.to_json())
    return build(API_SERVICE_NAME, API_VERSION, credentials=creds)

def upload_youtube_video(file_path, title, description, category_id="22", tags=None, privacy_status="private"):
    """
    Uploads an MP4 video to YouTube.

    Args:
        file_path (str): The full path to the MP4 file to upload.
        title (str): The title of the YouTube video.
        description (str): The description of the YouTube video.
        category_id (str, optional): The video category ID. Defaults to "22" (People & Blogs).
                                     You can find a list of categories here:
                                     https://developers.google.com/youtube/v3/docs/videoCategories/list
        tags (list, optional): A list of tags for the video. Defaults to None.
        privacy_status (str, optional): The privacy status of the video.
                                        Can be "public", "private", or "unlisted".
                                        Defaults to "private".
    Returns:
        dict: The API response containing information about the uploaded video, or None if an error occurs.
    """
    youtube = authenticate_youtube()

    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return None

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags if tags else [],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status
        }
    }

    # Call the API's videos.insert method to upload the video.
    try:
        media_body = MediaFileUpload(file_path, chunksize=-1, resumable=True)
        insert_request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media_body
        )

        print(f"Uploading video '{title}' from '{file_path}'...")
        response = None
        while response is None:
            status, response = insert_request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%")

        print(f"\nVideo uploaded successfully! Video ID: {response['id']}")
        print(f"Video URL: https://www.youtube.com/watch?v={response['id']}")
        return response

    except Exception as e:
        print(f"An error occurred: {e}")
        return None

if __name__ == "__main__":
    
    # --- Example Usage ---
    # IMPORTANT: Replace 'your_video.mp4' with the actual path to your video file.
    # Make sure 'client_secret.json' is in the same directory as this script.

    video_file = "In_our_time_audiobook.mp4"  # <--- CHANGE THIS
    video_title = "My Awesome Python Upload Test"
    video_description = "This video was uploaded using a Python script and the YouTube Data API."
    video_tags = ["python", "youtube api", "automation", "test"]
    video_privacy = "public" # Can be "public", "private", or "unlisted"

    uploaded_video_info = upload_youtube_video(
        file_path=video_file,
        title=video_title,
        description=video_description,
        tags=video_tags,
        privacy_status=video_privacy
    )

    if uploaded_video_info:
        print("\nUpload complete. Video details:")
        print(f"Title: {uploaded_video_info['snippet']['title']}")
        print(f"Description: {uploaded_video_info['snippet']['description']}")
        print(f"Privacy Status: {uploaded_video_info['status']['privacyStatus']}")
        print(f"Video ID: {uploaded_video_info['id']}")
    else:
        print("\nVideo upload failed.")
