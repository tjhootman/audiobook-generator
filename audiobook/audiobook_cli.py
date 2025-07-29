"""Main program for converting text files to audiobooks."""
import os
from pydub import AudioSegment

from text_processing import (
    GutenbergSource,
    GutenbergCleaner,
    FileTextExporter,
    DefaultTextChunker,
    get_user_book_url,
    get_book_title,
    get_book_author,
    setup_output_directory
)

from audio_analysis import (
    get_available_tts_voices,
    analyze_language,
    analyze_sentiment,
    analyze_category,
    analyze_syntax_complexity,
    analyze_regional_context,
    synthesize_text_to_speech,
    get_user_gender_preference,
    get_contextual_voice_parameters
)

from image_generation import create_cover_image
from video_processing import create_video
from youtube_upload import upload_youtube_video

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

    # --- Audiobook Generation Logic ---
    get_available_tts_voices()
    user_gender_preference = get_user_gender_preference()

    detected_language_code = analyze_language(cleaned_text_content)
    regional_code_from_text = None
    if detected_language_code == "en":
        regional_code_from_text = analyze_regional_context(cleaned_text_content, detected_language_code)
    overall_score, overall_magnitude = analyze_sentiment(cleaned_text_content)
    classified_categories = analyze_category(cleaned_text_content) if len(cleaned_text_content.split()) >= 20 else []
    syntax_analysis_info = analyze_syntax_complexity(cleaned_text_content)

    voice_params = get_contextual_voice_parameters(
        detected_language_code=detected_language_code,
        sentiment_score=overall_score,
        categories=classified_categories,
        syntax_info=syntax_analysis_info,
        user_gender_preference=user_gender_preference,
        regional_code_from_text=regional_code_from_text
    )
    final_voice_name = voice_params["name"]
    final_pitch = voice_params["pitch"]
    final_speaking_rate = voice_params["speaking_rate"]
    final_language_code = voice_params["language_code"]
    final_voice_gender = voice_params["voice_gender"]

    MAX_CHARS_PER_TTS_CHUNK = 4800
    chunker = DefaultTextChunker()
    text_chunks = chunker.chunk(cleaned_text_content, max_chars_per_chunk=MAX_CHARS_PER_TTS_CHUNK)
    if not text_chunks:
        print("No text chunks generated for audiobook. Exiting.")
        return

    audio_segments = []
    temp_audio_dir = os.path.join(book_output_dir, "temp_audio_chunks")
    setup_output_directory(temp_audio_dir)

    for i, chunk in enumerate(text_chunks):
        if not chunk.strip():
            continue
        temp_audio_file = os.path.join(temp_audio_dir, f"chunk_{i:04d}.mp3")
        success = synthesize_text_to_speech(chunk, final_voice_name, final_language_code, final_voice_gender, temp_audio_file, final_pitch, final_speaking_rate)
        if success:
            try:
                audio_segments.append(AudioSegment.from_mp3(temp_audio_file))
            except Exception as e:
                print(f"Error loading chunk {i}: {e}")
        else:
            with open(os.path.join(book_output_dir, f"failed_chunk_{i:04d}.txt"), "w", encoding="utf-8") as err_f:
                err_f.write(chunk)

    if not audio_segments:
        print("No audio segments were successfully generated for the audiobook. Exiting.")
        return

    combined_audio = AudioSegment.empty()
    for segment in audio_segments:
        combined_audio += segment

    output_audio_file = os.path.join(book_output_dir, f"{sanitized_book_title}_audiobook.mp3")
    combined_audio.export(output_audio_file, format="mp3")
    print(f"Audiobook created successfully: '{output_audio_file}'")

    for file_name in os.listdir(temp_audio_dir):
        os.remove(os.path.join(temp_audio_dir, file_name))
    os.rmdir(temp_audio_dir)
    print("Cleaned up temporary audio files.")

    # # 19. Create cover image.
    # prompt = f"Generate a cover image for {book_author}'s '{raw_book_title}' audiobook"
    # output_image_file = f"{sanitized_book_title}.png"

    # create_cover_image(prompt, book_output_dir, output_image_file)

    # # 20. Create video for audiobook.
    # output_video_file = os.path.join(book_output_dir, f"{sanitized_book_title}_audiobook.mp4")
    # output_image_path = os.path.join(book_output_dir, output_image_file)
    # create_video(output_image_path, output_audio_file, output_video_file, None, 24)

    # #21. Upload video to YouTube Channel
    # video_file = output_video_file
    # video_title = f"{raw_book_title} Audiobook"
    # video_description = f"Audiobook version of '{raw_book_title}' by {book_author}."
    # video_tags = ["audiobook", "book", "literature", "classic"]
    # video_privacy = "public" # Can be "public", "private", or "unlisted"

    # uploaded_video_info = upload_youtube_video(
    #     file_path=video_file,
    #     title=video_title,
    #     description=video_description,
    #     tags=video_tags,
    #     privacy_status=video_privacy
    # )

    # if uploaded_video_info:
    #     print("\nUpload complete. Video details:")
    #     print(f"Title: {uploaded_video_info['snippet']['title']}")
    #     print(f"Description: {uploaded_video_info['snippet']['description']}")
    #     print(f"Privacy Status: {uploaded_video_info['status']['privacyStatus']}")
    #     print(f"Video ID: {uploaded_video_info['id']}")
    # else:
    #     print("\nVideo upload failed.")

if __name__ == "__main__":
    # Entry point of the script when executed directly.
    generate_full_audiobook()
