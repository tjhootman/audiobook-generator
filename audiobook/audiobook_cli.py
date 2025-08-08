"""Main program for converting text files to audiobooks."""
import os
import logging
import sys
from typing import Optional, Any, Dict, List, Tuple
from dotenv import load_dotenv

# --- Abstractions and implementations for Text Processing ---
from text_processing import (
    GutenbergSource,
    GutenbergCleaner,
    NoOpCleaner,
    FileTextExporter,
    TextProcessingService,
    LocalFileSource,
    TextCleaner,
    get_user_book_url,
    setup_output_directory,
    get_user_local_file
)

# --- Abstractions and implementations for Audio Synthesis ---
from audio_synthesis import (
    GoogleLanguageAnalyzer,
    GoogleTTSVoiceSelector,
    GoogleTTSSynthesizer,
    UserPreference,
    AudioSynthesisService,
    TTSVoiceSelector,
    TTSSynthesizer,
    LanguageAnalyzer,
    UserPreferenceProvider,
    DefaultTextChunker,
)

# --- Abstractions and implementations for Image Generation ---
from image_generation import (
    GoogleAuthenticator,
    VertexAIImageGenerator,
    PILImageSaver,
    CoverImageService,
    get_env_or_raise,
    ImageGenerator,
    ImageSaver,
    Authenticator,
)

# --- Abstractions and implementations for Video Processing ---
from video_processing import (
    AudiobookVideoRenderer,
    AudiobookVideoService,
    VideoRenderer
)

# --- Abstractions and implementations for YouTube Upload ---
from youtube_upload import (
    YouTubeOauthAuthenticator,
    GoogleAPIYouTubeUploader,
    YouTubeVideoService,
    YouTubeAuthenticator,
    YouTubeUploader,
)

# Load .env variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def run_video_youtube_pipeline(
    audio_file: str,
    cover_image_file: str,
    book_title: str,
    book_author: str,
    output_dir: str,
    upload_to_youtube: bool = True,
    made_for_kids: bool = False
) -> Optional[str]:
    """
    Orchestrates the creation of an audiobook video and its optional upload to YouTube.
    """
    logging.info("Starting video and YouTube upload pipeline.")
    
    uploader = None
    video_service = None

    try:
        if upload_to_youtube:
            logging.info("YouTube upload requested. Starting authentication...")
            
            client_secret_path = get_env_or_raise('YOUTUBE_CLIENT_SECRET_PATH', 'YouTube client secret JSON file path')
            token_path = get_env_or_raise('YOUTUBE_TOKEN_PATH', 'YouTube authentication token file path')

            authenticator = YouTubeOauthAuthenticator(
                client_secret_path=client_secret_path,
                token_path=token_path
            )
            authenticator.authenticate()
            uploader = GoogleAPIYouTubeUploader(authenticator=authenticator)
            video_service = YouTubeVideoService(uploader=uploader)
            logging.info("YouTube authentication successful.")
    
        # --- Video Rendering ---
        renderer = AudiobookVideoRenderer(fps=24)
        video_creation_service = AudiobookVideoService(renderer)

        output_video_file = os.path.join(output_dir, f"{book_title}_audiobook.mp4")
        output_image_path = os.path.join(output_dir, cover_image_file)

        video_creation_service.create_video(
            image_path=output_image_path,
            audio_path=audio_file,
            output_video_path=output_video_file,
            intro_video_path=None
        )

        # --- YouTube Uploading ---
        if upload_to_youtube and video_service:
            video_title = f"{book_title} Audiobook"
            video_description = f"Audiobook version of '{book_title}' by {book_author}."
            video_tags = ["audiobook", "book", "literature", "classic"]
            video_privacy = "public"
            
            logging.info("Attempting to upload video to YouTube...")
            uploaded_video_info = video_service.upload(
                file_path=output_video_file,
                title=video_title,
                description=video_description,
                tags=video_tags,
                privacy_status=video_privacy,
                made_for_kids=made_for_kids
            )

            if uploaded_video_info:
                logging.info("YouTube upload complete. Video details: %s", uploaded_video_info)
            else:
                logging.error("Video upload failed. Check YouTube API settings and permissions.")
                return None
    
        logging.info("Pipeline completed successfully.")
        return output_video_file

    except Exception as e:
        logging.error("An error occurred in the video/YouTube pipeline: %s", e, exc_info=True)
        return None
    

def generate_full_audiobook(output_base_dir="audiobook_output"):
    
    logging.info("Starting full audiobook generation pipeline.")

    try:
        # --- Setup Output directory ---
        setup_output_directory(output_base_dir)

        # --- User Input: Select Source ---
        source_choice = input("Select text source (1: URL, 2: Local File): ").strip()

        source = None
        cleaner = None
        book_data_source = ""

        if source_choice == "1":
            book_url = get_user_book_url()
            if not book_url:
                logging.info("No URL provided. Exiting.")
                return
            source = GutenbergSource(book_url)
            cleaner = GutenbergCleaner()
            book_data_source = book_url
            
        elif source_choice == "2":
            local_file_path = get_user_local_file()
            if not local_file_path:
                logging.info("No local file path provided. Exiting.")
                return
            source = LocalFileSource(local_file_path)
            cleaner = NoOpCleaner()
            book_data_source = local_file_path

        else:
            logging.error("Invalid source choice. Exiting.")
            return

        user_pref_provider = UserPreference()
        user_gender_preference = user_pref_provider.get_gender_preference()

        do_video = input("Would you like to create a video and upload to YouTube? (y/n): ").strip().lower() == "y"
        
        # --- Text Processing ---
        exporter = FileTextExporter()
        text_processor = TextProcessingService(
            source=source,
            cleaner=cleaner,
            exporter=exporter
        )

        logging.info("Processing book text from '%s'...", book_data_source)
        raw_placeholder_path = os.path.join(output_base_dir, "raw_placeholder.txt")
        clean_placeholder_path = os.path.join(output_base_dir, "cleaned_placeholder.txt")

        book_data = text_processor.process_text(
            raw_output_path=raw_placeholder_path,
            clean_output_path=clean_placeholder_path
        )
            
        if not book_data:
            logging.error("Text processing failed. Exiting.")
            return
    
        try:
            raw_book_title = book_data["raw_title"]
            book_author = book_data["author"]
            sanitized_book_title = book_data["sanitized_title"]
            cleaned_text_content = book_data["cleaned_text"]
        except KeyError as e:
            logging.error("TextProcessingService returned an invalid dictionary: Missing key %s", e)
            logging.error("Text processing failed. Exiting.")
            return

        logging.info("Detected Title: %s", raw_book_title)
        logging.info("Detected Author: %s", book_author)

        book_output_dir = os.path.join(output_base_dir, sanitized_book_title)
        setup_output_directory(book_output_dir)
        logging.info("Book output directory: %s", book_output_dir)

        # --- Image Generation ---
        # PROJECT_ID = get_env_or_raise('GOOGLE_CLOUD_PROJECT_ID', 'Google Cloud Project ID')
        # LOCATION = get_env_or_raise('GOOGLE_CLOUD_LOCATION', 'Google Cloud Location')

        # google_authenticator = GoogleAuthenticator(project=PROJECT_ID, location=LOCATION)
        # image_generator = VertexAIImageGenerator(project_id=PROJECT_ID, location=LOCATION)
        # image_saver = PILImageSaver()

        # cover_image_service = CoverImageService(
        #     authenticator=google_authenticator,
        #     image_generator=image_generator,
        #     image_saver=image_saver,
        # )

        # prompt = f"Generate a cover image for {book_author}'s '{raw_book_title}' audiobook."
        # output_image_file = f"{sanitized_book_title}.png"
        # cover_image_service.create_cover_image(prompt, book_output_dir, output_image_file)

        # --- Audiobook Synthesis ---
        language_analyzer = GoogleLanguageAnalyzer()
        voice_selector = GoogleTTSVoiceSelector()
        tts_synthesizer = GoogleTTSSynthesizer(5,2.0)
        user_pref_provider = UserPreference()
        audio_service = AudioSynthesisService(
            language_analyzer,
            voice_selector,
            tts_synthesizer,
            user_pref_provider
        )

        output_audio_file = os.path.join(book_output_dir, f"{sanitized_book_title}_audiobook.mp3")
        audio_result = audio_service.synthesize_audio(
            text=cleaned_text_content,
            output_audio_path=output_audio_file,
            temp_audio_dir=os.path.join(book_output_dir, "temp_audio_chunks"),
            user_gender_preference=user_gender_preference
        )

        if not audio_result:
            logging.error("No audio segments were successfully generated for the audiobook. Exiting.")
            return

        if do_video:
            run_video_youtube_pipeline(
                audio_file=output_audio_file,
                cover_image_file=output_image_file,
                book_title=raw_book_title,
                book_author=book_author,
                output_dir=book_output_dir,
                upload_to_youtube=True,
                made_for_kids=False
            )
        else:
            logging.info("Skipping video generation and YouTube upload.")

        logging.info("Full pipeline completed successfully.")
    
    except Exception as e:
        logging.error("An error occurred in the full audiobook pipeline: %s", e, exc_info=True)
        return


if __name__ == "__main__":
    generate_full_audiobook()
