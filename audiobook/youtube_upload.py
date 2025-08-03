"""Modules for authenticating and uploading videos to YouTube. """

import os
import logging
from typing import Optional, List, Protocol, Dict, Any
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import GoogleAuthError

# --- Custom Exceptions ---

class YouTubeAuthError(Exception):
    """Custom exception raised for errors during YouTube authentication."""
    pass

class YouTubeUploadError(Exception):
    """Custom exception raised for errors during YouTube video upload."""
    pass

# --- Interface Definitions ---

class YouTubeAuthenticator(Protocol):
    """Protocol for classes that perform authentication with the YouTube API."""
    def authenticate(self) -> Any:
        """
        Performs the authentication process for the YouTube API.

        Returns:
            Any: A credentials object required to access the YouTube API.
                 The exact type depends on the authentication flow (e.g., Google's `Credentials`).
        """
        ...

class YouTubeUploader(Protocol):
    """Protocol for classes that handle uploading a video to YouTube."""
    def upload_video(
            self,
            file_path: str,
            title: str,
            description: str,
            category_id: str = "22",
            tags: Optional[List[str]] = None,
            privacy_status: str = "private",
            made_for_kids: bool = False
    ) -> Optional[Dict]:
        """
        Uploads a video file to YouTube.

        Args:
            file_path (str): The path to the video file.
            title (str): The title of the video.
            description (str): A description of the video.
            category_id (str, optional): The ID of the video category. Defaults to "22".
            tags (Optional[List[str]], optional): A list of tags for the video. Defaults to None.
            privacy_status (str, optional): The privacy status of the video ("public", "private", "unlisted").
                                            Defaults to "private".

        Returns:
            Optional[Dict]: A dictionary containing the video's details from the API response
                            if the upload is successful, None otherwise.
        """
        ...

# --- Implementation Classes ---

class YouTubeOauthAuthenticator(YouTubeAuthenticator):
    """
    An Authenticator implementation that handles the OAuth 2.0 flow for the YouTube Data API.

    It stores and refreshes credentials automatically to simplify the authentication process.
    """
    def __init__(
        self,
        client_secret_path: str,
        token_path: str,
        scopes: Optional[List[str]] = None
    ):
        """
        Initializes the authenticator with file paths and API scopes.

        Args:
            client_secret_path (str): The path to the client secret JSON file.
            token_path (str): The path to the file where the authentication token will be saved.
            scopes (Optional[List[str]], optional): The list of OAuth 2.0 scopes.
                                                    Defaults to the required YouTube upload scope.
        """

        if scopes is None:
            self.scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        else:
            self.scopes = scopes
        
        self.client_secret_path = client_secret_path
        self.token_path = token_path
        self.api_service_name = "youtube"
        self.api_version = "v3"


    # The YouTube Data API scopes required for uploading videos.
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    API_SERVICE_NAME = "youtube"
    API_VERSION = "v3"
    TOKEN_PATH = "./credentials/token.json"
    CLIENT_SECRET_PATH = "./credentials/client_secret.json"

    def authenticate(self) -> Any:
        """
        Performs the authentication process for the YouTube Data API.

        The method handles refreshing expired tokens and running the initial
        authorization flow if no valid token is found.

        Returns:
            Any: An authenticated YouTube service object.

        Raises:
            YouTubeAuthError: If authentication fails for any reason.
        """
        creds = None

        try:
            # Check for existing credentials file
            if os.path.exists(self.token_path):
                creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)

            # If no valid credentials, run the authorization flow
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    logging.info("Refreshing expired credentials.")
                    creds.refresh(Request())
                else:
                    logging.info("Running new OAuth authorization flow.")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.client_secret_path, self.scopes
                    )
                    creds = flow.run_local_server(port=0)
                
                # Save the new or refreshed credentials
                with open(self.token_path, "w") as token:
                    token.write(creds.to_json())
            
            logging.info("Authentication successful. Building YouTube service.")
            return build(self.api_service_name, self.api_version, credentials=creds)
        
        except GoogleAuthError as e:
            msg = f"Google authentication failed: {e}"
            logging.error(msg, exc_info=True)
            raise YouTubeAuthError(msg) from e
        except FileNotFoundError as e:
            msg = f"Client secret file not found at '{self.client_secret_path}': {e}"
            logging.error(msg, exc_info=True)
            raise YouTubeAuthError(msg) from e
        except Exception as e:
            msg = f"An unexpected error occurred during authentication: {e}"
            logging.error(msg, exc_info=True)
            raise YouTubeAuthError(msg) from e

class GoogleAPIYouTubeUploader(YouTubeUploader):
    """An implementation of the YouTubeUploader protocol using the Google API client library."""
    def __init__(self, authenticator: YouTubeAuthenticator):
        """
        Initializes the uploader with a YouTube authenticator instance.

        Args:
            authenticator (YouTubeAuthenticator): An object that handles YouTube API authentication.
        """
        self.authenticator = authenticator

    def upload_video(
        self,
        file_path: str,
        title: str,
        description: str,
        category_id: str = "22",
        tags: Optional[List[str]] = None,
        privacy_status: str = "private",
        made_for_kids: bool = False
    ) -> Optional[Dict]:
        """
        Uploads a video to a YouTube channel.

        Args:
            file_path (str): The path to the video file to upload.
            title (str): The title of the video.
            description (str): The description of the video.
            category_id (str, optional): The video's category ID. Defaults to "22" (People & Blogs).
            tags (Optional[List[str]], optional): A list of tags for the video. Defaults to None.
            privacy_status (str, optional): The privacy status of the video ("public", "private", "unlisted").
                                            Defaults to "private".

        Returns:
            Optional[Dict]: A dictionary containing the uploaded video's details, or None on failure.
        
        Raises:
            YouTubeUploadError: If the file does not exist or the upload fails.
        """
        try:
            youtube = self.authenticator.authenticate()
        except Exception as e:
            msg = f"Failed to authenticate with YouTube: {e}"
            logging.error(msg, exc_info=True)
            raise YouTubeUploadError(msg) from e

        if not os.path.exists(file_path):
            msg = f"Error: Video file not found at {file_path}"
            logging.error(msg)
            raise YouTubeUploadError(msg)
            
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags if tags is not None else [],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "madeForKids": made_for_kids
            }
        }

        try:
            media_body = MediaFileUpload(file_path, chunksize=-1, resumable=True)
            insert_request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media_body
            )

            logging.info("Uploading video '%s' from '%s'...", title, file_path)
            
            response = None
            while response is None:
                status, response = insert_request.next_chunk()
                if status:
                    logging.info("Uploaded %d%%", int(status.progress() * 100))

            logging.info("Video uploaded successfully! Video ID: %s", response['id'])
            video_url = f"https://www.youtube.com/watch?v={response['id']}"
            logging.info("Video URL: %s", video_url)

            return response

        except HttpError as e:
            msg = f"An HTTP error occurred during upload: {e.resp.status}, {e.content}"
            logging.error(msg, exc_info=True)
            raise YouTubeUploadError(msg) from e
        except Exception as e:
            msg = f"An unexpected error occurred during upload: {e}"
            logging.error(msg, exc_info=True)
            raise YouTubeUploadError(msg) from e

# --- High-level Service ---

class YouTubeVideoService:
    """
    A service that orchestrates the video upload process to YouTube.
    
    This service delegates the actual upload logic to an injected uploader implementation.
    """
    def __init__(self, uploader: YouTubeUploader) -> None:
        """
        Initializes the service with a concrete YouTube uploader implementation.
        
        Args:
            uploader (YouTubeUploader): An object that handles the video uploading process.
        """
        self.uploader = uploader

    def upload(
        self,
        file_path: str,
        title: str,
        description: str,
        category_id: str = "22",
        tags: Optional[List[str]] = None,
        privacy_status: str = "private",
        made_for_kids: bool = False
    ) -> Optional[Dict]:
        """
        Uploads a video to YouTube using the provided details.

        Args:
            file_path (str): The path to the video file.
            title (str): The title of the video.
            description (str): A description of the video.
            category_id (str, optional): The ID of the video category. Defaults to "22".
            tags (Optional[List[str]], optional): A list of tags for the video. Defaults to None.
            privacy_status (str, optional): The privacy status of the video ("public", "private", "unlisted").
                                            Defaults to "private".

        Returns:
            Optional[Dict]: A dictionary containing the video's details if the upload is successful,
                            None otherwise.
        """
        logging.info("YouTube video upload service starting...")

        uploaded_video_info = self.uploader.upload_video(
            file_path=file_path,
            title=title,
            description=description,
            category_id=category_id,
            tags=tags,
            privacy_status=privacy_status,
            made_for_kids=made_for_kids
        )
        
        if uploaded_video_info:
            logging.info("YouTube video upload service complete.")
        else:
            logging.error("YouTube video upload service failed.")
        
        return uploaded_video_info
