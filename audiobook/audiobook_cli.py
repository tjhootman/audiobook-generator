"""Main program for converting text files to audiobooks."""
import os
from pydub import AudioSegment

# Import functions related to audio analysis and TTS voice selection from the 'audio_analysis' module.
from audio_analysis import (
    get_available_tts_voices,       # Fetches and caches available TTS voices.
    analyze_language,               # Detects the language of the text.
    analyze_sentiment,              # Analyzes the emotional sentiment of the text.
    analyze_category,               # Classifies the text into predefined categories.
    analyze_syntax_complexity,      # Analyzes the grammatical complexity of sentences.
    analyze_regional_context,       # Detects regional variations in language (e.g., US vs. GB English).
    synthesize_text_to_speech,      # Converts text chunks to speech using Google Cloud TTS.
    get_user_gender_preference,     # Prompts user for narrator gender preference.
    get_contextual_voice_parameters # Selects TTS voice parameters based on text analysis.
)

# Import functions related to text processing and book content handling from the 'text_processing' module.
from text_processing import (
    setup_output_directory,     # Creates the output directory structure.
    get_user_book_url,          # Prompts the user for a Project Gutenberg book URL.
    download_book_content,      # Downloads the raw text content of the book.
    get_book_title,             # Extracts the title from the book content.
    get_book_author,            # Extracts the author from the book content.
    export_raw_text,            # Saves the raw downloaded text to a file.
    clean_text,                 # Cleans the raw text (removes boilerplate, formatting).
    export_cleaned_text,        # Saves the cleaned text to a file.
    chunk_text_from_file        # Splits the text into smaller chunks suitable for TTS API.
)

# Import function for image creation.
from image_generation import create_cover_image

# Import function for video creation.
from video_processing import create_video

# Import function for uploading video to YouTube.
from youtube_upload import upload_youtube_video

# --- Main orchestration function ---
def generate_full_audiobook(output_base_dir="audiobook_output"):
    """
    Orchestrates the entire process of creating an audiobook from a Project Gutenberg URL.
    This includes downloading, cleaning, analyzing the text, and then synthesizing
    speech for each chunk, finally combining them into a single audio file.

    Args:
        output_base_dir (str, optional): The base directory where all audiobook
                                         output (raw text, cleaned text, audio chunks,
                                         final audiobook) will be stored.
                                         Defaults to "audiobook_output".
    """
    # 1. Setup Output Directory
    # Ensure the base output directory exists.
    setup_output_directory(output_base_dir)

    # 2. Get Book URL
    # Prompt the user to enter the URL of the Project Gutenberg book.
    book_url = get_user_book_url()
    if not book_url:
        print("No URL provided. Exiting.")
        return

    # 3. Download Book Content
    # Fetch the raw text content from the provided URL.
    raw_text_content = download_book_content(book_url)
    if not raw_text_content:
        print("Failed to download book content. Exiting.")
        return

    # 4. Extract Book Metadata
    # Get the book title and author from the downloaded content.
    raw_book_title, sanitized_book_title = get_book_title(raw_text_content)
    book_author = get_book_author(raw_text_content)
    print(f"Detected Title: {raw_book_title}")
    print(f"Detected Author: {book_author}")

    # Create a specific directory for this book within the base output directory.
    book_output_dir = os.path.join(output_base_dir, sanitized_book_title)
    setup_output_directory(book_output_dir)

    # 5. Export Raw Text
    # Save the initially downloaded raw text content.
    raw_text_filepath = export_raw_text(raw_text_content, sanitized_book_title, book_output_dir)
    if not raw_text_filepath:
        print("Failed to export raw text. Exiting.")
        return

    # 6. Clean Text Content
    # Clean the raw text by removing Project Gutenberg headers/footers and extra formatting.
    print("\nCleaning text content...")
    cleaned_text_content = clean_text(raw_text_filepath, raw_book_title)
    if not cleaned_text_content:
        print("Failed to clean text. Exiting.")
        return

    # 7. Export Cleaned Text
    # Save the cleaned text content to a new file.
    cleaned_text_filepath = os.path.join(book_output_dir, f"{sanitized_book_title}_cleaned.txt")
    if not export_cleaned_text(cleaned_text_content, cleaned_text_filepath):
        print("Failed to export cleaned text. Exiting.")
        return
    
    # 8. Create cover image.
    prompt = f"Generate a cover image for {book_author}'s '{raw_book_title}' audiobook"
    output_image_file = f"{sanitized_book_title}.png"

    create_cover_image(prompt, book_output_dir, output_image_file)

    # --- Audiobook Generation Logic Starts Here ---
    print("\n--- Audiobook Generation ---")
    print("Fetching available Text-to-Speech voices...")
    # Initialize the global cache of available TTS voices.
    get_available_tts_voices()

    # 8. Get User Gender Preference
    # Ask the user if they have a preferred narrator gender.
    user_gender_preference = get_user_gender_preference()
    if user_gender_preference:
        print(f"User selected narrator gender: {user_gender_preference.name}")
    else:
        print("User opted for automatic gender selection.")

    # 9. Analyze Overall Language
    # Detect the dominant language of the cleaned text using Google NL API.
    print("Detecting overall language of the text...")
    detected_language_code = analyze_language(cleaned_text_content)
    print(f"Overall Detected Language: {detected_language_code}")

    # 10. Analyze Regional Context (for English only)
    # If the language is English, try to determine if it's US or GB English.
    regional_code_from_text = None
    if detected_language_code == "en":
        print("Analyzing text for regional English context (US vs. GB)...")
        regional_code_from_text = analyze_regional_context(cleaned_text_content, detected_language_code)
        if regional_code_from_text:
            print(f"Detected regional English context: {regional_code_from_text}")
        else:
            print("No strong regional English context detected or language is not English.")

    # 11. Analyze Overall Sentiment
    # Determine the emotional tone of the entire text.
    print("Analyzing overall sentiment of the text...")
    overall_score, overall_magnitude = analyze_sentiment(cleaned_text_content)
    print(f"Overall Sentiment Score: {overall_score:.2f}, Magnitude: {overall_magnitude:.2f}")

    # 12. Classify Content Categories
    # Classify the text into broad categories (e.g., Fiction, History).
    print("Classifying content categories...")
    classified_categories = []
    # Category classification requires a minimum amount of text (approx. 20 words).
    if len(cleaned_text_content.split()) >= 20:
        classified_categories = analyze_category(cleaned_text_content)
        print(f"Content Categories: {', '.join(classified_categories) if classified_categories else 'None detected'}")
    else:
        print(f"Text too short ({len(cleaned_text_content.split())} words) for category classification. Skipping.")

    # 13. Analyze Syntax Complexity
    # Analyze sentence structure and complexity.
    print("Analyzing syntax complexity...")
    syntax_analysis_info = analyze_syntax_complexity(cleaned_text_content)
    print(f"Syntax Info: Sentences={syntax_analysis_info['num_sentences']}, "
          f"Avg Tokens/Sentence={syntax_analysis_info['avg_tokens_per_sentence']:.2f}, "
          f"Complex Clauses={syntax_analysis_info['num_complex_clauses']}")

    # 14. Determine Contextual Voice Parameters
    # Select the optimal TTS voice (name, pitch, speaking rate, gender) based on all analyses.
    voice_params = get_contextual_voice_parameters(
        detected_language_code=detected_language_code,
        sentiment_score=overall_score,
        categories=classified_categories,
        syntax_info=syntax_analysis_info,
        user_gender_preference=user_gender_preference,
        regional_code_from_text=regional_code_from_text # Pass regional context to influence voice choice
    )
    final_voice_name = voice_params["name"]
    final_pitch = voice_params["pitch"]
    final_speaking_rate = voice_params["speaking_rate"]
    final_language_code = voice_params["language_code"]
    final_voice_gender = voice_params["voice_gender"]

    print(f"\nSelected Fixed Voice based on context: {final_voice_name} ({final_language_code}, Gender: {final_voice_gender.name}), Pitch: {final_pitch}, Speaking Rate: {final_speaking_rate}")

    # 15. Chunk Text for TTS
    # Google Cloud TTS has character limits per request, so the text is split into chunks.
    MAX_CHARS_PER_TTS_CHUNK = 4800
    text_chunks = chunk_text_from_file(cleaned_text_filepath, max_chars_per_chunk=MAX_CHARS_PER_TTS_CHUNK)
    if not text_chunks:
        print("No text chunks generated for audiobook. Exiting.")
        return

    audio_segments = []
    # Create a temporary directory to store individual audio chunks.
    temp_audio_dir = os.path.join(book_output_dir, "temp_audio_chunks")
    setup_output_directory(temp_audio_dir)

    # 16. Synthesize Speech for Each Chunk
    print(f"\nStarting audio synthesis for {len(text_chunks)} chunks...")
    for i, chunk in enumerate(text_chunks):
        if not chunk.strip(): # Skip empty chunks that might result from cleaning/chunking.
            print(f"  Skipping empty chunk {i+1}/{len(text_chunks)}.")
            continue

        print(f"  Processing chunk {i+1}/{len(text_chunks)} (approx {len(chunk)} chars): '{chunk[:50].replace('\n', ' ')}...'")
        
        temp_audio_file = os.path.join(temp_audio_dir, f"chunk_{i:04d}.mp3")
        
        # Call the TTS synthesis function with the determined voice parameters.
        success = synthesize_text_to_speech(chunk, final_voice_name, final_language_code, final_voice_gender, temp_audio_file, final_pitch, final_speaking_rate)
        
        if success:
            try:
                # Load the generated audio chunk using pydub.
                audio_segments.append(AudioSegment.from_mp3(temp_audio_file))
            except Exception as e:
                print(f"Error loading generated audio for chunk {i}: {e}. This might indicate a problem with the generated MP3. Skipping this chunk.")
                continue # Continue to the next chunk even if loading failed
        else:
            print(f"Failed to synthesize audio for chunk {i} after multiple retries. Skipping this chunk.")
            # Optionally save the failed chunk text for debugging.
            with open(os.path.join(book_output_dir, f"failed_chunk_{i:04d}.txt"), "w", encoding="utf-8") as err_f:
                err_f.write(chunk)
            continue

    if not audio_segments:
        print("No audio segments were successfully generated for the audiobook. Exiting.")
        return

    # 17. Combine Audio Segments
    # Concatenate all successfully generated audio chunks into a single AudioSegment.
    print("\nCombining audio segments into final audiobook...")
    combined_audio = AudioSegment.empty()
    for segment in audio_segments:
        combined_audio += segment

    # 18. Export Final Audiobook
    # Save the combined audio to the final MP3 audiobook file.
    output_audio_file = os.path.join(book_output_dir, f"{sanitized_book_title}_audiobook.mp3")
    combined_audio.export(output_audio_file, format="mp3")
    print(f"Audiobook created successfully: '{output_audio_file}'")

    # 19. Clean Up Temporary Files
    # Remove the individual audio chunk files and the temporary directory.
    print("Cleaning up temporary audio files...")
    for file_name in os.listdir(temp_audio_dir):
        os.remove(os.path.join(temp_audio_dir, file_name))
    os.rmdir(temp_audio_dir)
    print("Cleaned up temporary audio files.")

    # 20. Create video for audiobook.
    output_video_file = os.path.join(book_output_dir, f"{sanitized_book_title}_audiobook.mp4")
    output_image_path = os.path.join(book_output_dir, output_image_file)
    create_video(output_image_path, output_audio_file, output_video_file, None, 24)

    #21. Upload video to YouTube Channel
    video_file = output_video_file
    video_title = f"{raw_book_title} Audiobook"
    video_description = f"Audiobook version of '{raw_book_title}' by {book_author}."
    video_tags = ["audiobook", "book", "literature", "classic"]
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

if __name__ == "__main__":
    # Entry point of the script when executed directly.
    generate_full_audiobook()
