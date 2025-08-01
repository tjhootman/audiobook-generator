"""Modules for authenticating and uploading videos to YouTube. """

import os
from typing import Optional, List, Protocol, Dict, Any
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# --- Abstractions (Interfaces) ---

class IYouTubeAuthenticator(Protocol):
    def authenticate(self) -> Any: ...

class IYouTubeUploader(Protocol):
    def upload_video(
            self,
            file_path: str,
            title: str,
            description: str,
            category_id: str = "22",
            tags: Optional[List[str]] = None,
            privacy_status: str = "private"
    ) -> Optional[Dict]: ...

# --- Implementations ---

class YouTubeAuthenticator(IYouTubeAuthenticator):
    # The YouTube Data API scopes required for uploading videos.
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    API_SERVICE_NAME = "youtube"
    API_VERSION = "v3"
    TOKEN_PATH = "./credentials/token.json"
    CLIENT_SECRET_PATH = "./credentials/client_secret.json"

    def authenticate(self) -> Any:
        """Authenticates with YouTube and returns the YouTube service object."""
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists(self.TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(self.TOKEN_PATH, self.SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.CLIENT_SECRET_PATH, self.SCOPES
                )
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(self.TOKEN_PATH, "w") as token:
                token.write(creds.to_json())
        return build(self.API_SERVICE_NAME, self.API_VERSION, credentials=creds)

class YouTubeUploader(IYouTubeUploader):
    def __init__(self, authenticator: IYouTubeAuthenticator):
        self.authenticator = authenticator

    def upload_video(
            self,
        file_path: str,
        title: str,
        description: str,
        category_id: str = "22",
        tags: Optional[List[str]] = None,
        privacy_status: str = "private"
    ) -> Optional[Dict]:
            
        youtube = self.authenticator.authenticate()

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

# --- High-level Service ---

class YouTubeVideoService:
    def __init__(self, uploader: IYouTubeUploader):
        self.uploader = uploader

    def upload(
            self,
        file_path: str,
        title: str,
        description: str,
        category_id: str = "22",
        tags: Optional[List[str]] = None,
        privacy_status: str = "private"
    ) -> Optional[Dict]:
        return self.uploader.upload_video(
            file_path=file_path,
            title=title,
            description=description,
            category_id=category_id,
            tags=tags,
            privacy_status=privacy_status
        )
