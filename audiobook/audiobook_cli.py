"""Main program for converting text files to audiobooks."""
import os
from dotenv import load_dotenv

from text_processing import (
    GutenbergSource,
    GutenbergCleaner,
    FileTextExporter,
    TextProcessingService,
    get_user_book_url,
    get_book_title,
    get_book_author,
    setup_output_directory,
)

from audiobook.audio_synthesis import (
    GoogleLanguageAnalyzer,
    GoogleTTSVoiceSelector,
    GoogleTTSSynthesizer,
    UserPreference,
    AudioSynthesisService,
)

from image_generation import (
    GoogleAuthenticator,
    VertexAIImageGenerator,
    PILImageSaver,
    CoverImageService,
    get_env_or_raise,
)

from video_processing import AudiobookVideoRenderer, AudiobookVideoService

from youtube_upload import YouTubeAuthenticator, YouTubeUploader, YouTubeVideoService

# Load .env variables
load_dotenv()

def generate_full_audiobook(output_base_dir="audiobook_output"):

    setup_output_directory(output_base_dir)

    book_url = get_user_book_url()
    if not book_url:
        print("No URL provided. Exiting.")
        return

    source = GutenbergSource(book_url)
    raw_text_content = source.get_text()
    if raw_text_content is None:
        print("Failed to download book content. Exiting.")
        return

    raw_book_title, sanitized_book_title = get_book_title(raw_text_content)
    book_author = get_book_author(raw_text_content)
    print(f"Detected Title: {raw_book_title}")
    print(f"Detected Author: {book_author}")

    book_output_dir = os.path.join(output_base_dir, sanitized_book_title)
    setup_output_directory(book_output_dir)

    # Export raw text
    exporter = FileTextExporter()
    raw_text_filepath = os.path.join(book_output_dir, f"{sanitized_book_title}_raw.txt")
    exporter.export(raw_text_content, raw_text_filepath)

    # Clean text
    cleaner = GutenbergCleaner()
    cleaned_text_content = cleaner.clean(raw_text_content, raw_title=raw_book_title, file_path=raw_text_filepath)

    # Export cleaned text
    cleaned_text_filepath = os.path.join(book_output_dir, f"{sanitized_book_title}_cleaned.txt")
    exporter.export(cleaned_text_content, cleaned_text_filepath)

    # User gender preference
    user_pref_provider = UserPreference()
    user_gender_preference = user_pref_provider.get_gender_preference()


    # --- Audiobook Generation Logic ---

    # Audio Synthesis Service Setup
    language_analyzer = GoogleLanguageAnalyzer()
    voice_selector = GoogleTTSVoiceSelector()
    tts_synthesizer = GoogleTTSSynthesizer()
    user_pref_provider = UserPreference()
    audio_service = AudioSynthesisService(
        language_analyzer,
        voice_selector,
        tts_synthesizer,
        user_pref_provider
    )

    # Syntesize Audiobook (the service handles chunking and temp files)
    output_audio_file = os.path.join(book_output_dir, f"{sanitized_book_title}_audiobook.mp3")
    audio_result = audio_service.synthesize_audio(
        text=cleaned_text_content,
        output_audio_path=output_audio_file,
        temp_audio_dir=os.path.join(book_output_dir, "temp_audio_chunks"),
        user_gender_preference=user_gender_preference
    )

    if not audio_result:
        print("No audio segments were successfully generated for the audiobook. Exiting.")
        return

    # Create cover image
    prompt = f"Generate a cover image for {book_author}'s '{raw_book_title}' audiobook"
    output_image_file = f"{sanitized_book_title}.png"

    # --- Configuration for Vertex AI Imagen ---
    # IMPORTANT: Replace with your actual Google Cloud Project ID and Location.
    # Ensure Vertex AI API is enabled in your Google Cloud Project.
    # Authenticate by running `gcloud auth application-default login` in your terminal.
    # It's good practice to get these from environment variables.
    PROJECT_ID = get_env_or_raise('GOOGLE_CLOUD_PROJECT_ID', 'Google Cloud Project ID')
    LOCATION = get_env_or_raise('GOOGLE_CLOUD_LOCATION', 'Google Cloud Location')

    cover_image_service = CoverImageService(
        authenticator=GoogleAuthenticator(),
        image_generator=VertexAIImageGenerator(PROJECT_ID, LOCATION),
        image_saver=PILImageSaver(),
    )
    cover_image_service.create_cover_image(prompt, book_output_dir, output_image_file)

    # Create video for audiobook
    renderer = AudiobookVideoRenderer()
    service = AudiobookVideoService(renderer)

    output_video_file = os.path.join(book_output_dir, f"{sanitized_book_title}_audiobook.mp4")
    output_image_path = os.path.join(book_output_dir, output_image_file)
    service.renderer.render_video(output_image_path, output_audio_file, output_video_file, None, 24)

    # Upload video to YouTube Channel
    authenticator = YouTubeAuthenticator()
    uploader = YouTubeUploader(authenticator)
    video_service = YouTubeVideoService(uploader)

    video_file = output_video_file
    video_title = f"{raw_book_title} Audiobook"
    video_description = f"Audiobook version of '{raw_book_title}' by {book_author}."
    video_tags = ["audiobook", "book", "literature", "classic"]
    video_privacy = "public" # Can be "public", "private", or "unlisted"

    uploaded_video_info = video_service.upload(
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

if __name__ == "__main__":
    # Entry point of the script when executed directly.
    generate_full_audiobook()
