import os
from pydub import AudioSegment

# Import functions from analysis module
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

# Import functions from text_processing module
from text_processing import (
    setup_output_directory,
    get_user_book_url,
    download_book_content,
    get_book_title,
    get_book_author,
    export_raw_text,
    clean_text,
    export_cleaned_text,
    chunk_text_from_file
)

# --- Main orchestration function ---
def generate_full_audiobook(output_base_dir="audiobook_output"):
    """
    Orchestrates the entire process: downloads, cleans, analyzes, and generates
    an audiobook from a Project Gutenberg URL.
    """
    setup_output_directory(output_base_dir)

    book_url = get_user_book_url()
    if not book_url:
        print("No URL provided. Exiting.")
        return

    raw_text_content = download_book_content(book_url)
    if not raw_text_content:
        print("Failed to download book content. Exiting.")
        return

    raw_book_title, sanitized_book_title = get_book_title(raw_text_content)
    book_author = get_book_author(raw_text_content)
    print(f"Detected Title: {raw_book_title}")
    print(f"Detected Author: {book_author}")

    book_output_dir = os.path.join(output_base_dir, sanitized_book_title)
    setup_output_directory(book_output_dir)

    raw_text_filepath = export_raw_text(raw_text_content, sanitized_book_title, book_output_dir)
    if not raw_text_filepath:
        print("Failed to export raw text. Exiting.")
        return

    print("\nCleaning text content...")
    cleaned_text_content = clean_text(raw_text_filepath, raw_book_title)
    if not cleaned_text_content:
        print("Failed to clean text. Exiting.")
        return

    cleaned_text_filepath = os.path.join(book_output_dir, f"{sanitized_book_title}_cleaned.txt")
    if not export_cleaned_text(cleaned_text_content, cleaned_text_filepath):
        print("Failed to export cleaned text. Exiting.")
        return

    # --- Audiobook Generation Logic Starts Here ---
    print("\n--- Audiobook Generation ---")
    print("Fetching available Text-to-Speech voices...")
    get_available_tts_voices()

    user_gender_preference = get_user_gender_preference()
    if user_gender_preference:
        print(f"User selected narrator gender: {user_gender_preference.name}")
    else:
        print("User opted for automatic gender selection.")

    print("Detecting overall language of the text...")
    detected_language_code = analyze_language(cleaned_text_content)
    print(f"Overall Detected Language: {detected_language_code}")

    # Analyze regional context
    regional_code_from_text = None
    if detected_language_code == "en": # Only try for English
        print("Analyzing text for regional English context (US vs. GB)...")
        regional_code_from_text = analyze_regional_context(cleaned_text_content, detected_language_code)
        if regional_code_from_text:
            print(f"Detected regional English context: {regional_code_from_text}")
        else:
            print("No strong regional English context detected or language is not English.")

    print("Analyzing overall sentiment of the text...")
    overall_score, overall_magnitude = analyze_sentiment(cleaned_text_content)
    print(f"Overall Sentiment Score: {overall_score:.2f}, Magnitude: {overall_magnitude:.2f}")

    print("Classifying content categories...")
    classified_categories = []
    if len(cleaned_text_content.split()) >= 20:
        classified_categories = analyze_category(cleaned_text_content)
        print(f"Content Categories: {', '.join(classified_categories) if classified_categories else 'None detected'}")
    else:
        print(f"Text too short ({len(cleaned_text_content.split())} words) for category classification. Skipping.")

    print("Analyzing syntax complexity...")
    syntax_analysis_info = analyze_syntax_complexity(cleaned_text_content)
    print(f"Syntax Info: Sentences={syntax_analysis_info['num_sentences']}, "
          f"Avg Tokens/Sentence={syntax_analysis_info['avg_tokens_per_sentence']:.2f}, "
          f"Complex Clauses={syntax_analysis_info['num_complex_clauses']}")

    voice_params = get_contextual_voice_parameters(
        detected_language_code=detected_language_code,
        sentiment_score=overall_score,
        categories=classified_categories,
        syntax_info=syntax_analysis_info,
        user_gender_preference=user_gender_preference,
        regional_code_from_text=regional_code_from_text # Pass regional context
    )
    final_voice_name = voice_params["name"]
    final_pitch = voice_params["pitch"]
    final_speaking_rate = voice_params["speaking_rate"]
    final_language_code = voice_params["language_code"]
    final_voice_gender = voice_params["voice_gender"]

    print(f"\nSelected Fixed Voice based on context: {final_voice_name} ({final_language_code}, Gender: {final_voice_gender.name}), Pitch: {final_pitch}, Speaking Rate: {final_speaking_rate}")

    MAX_CHARS_PER_TTS_CHUNK = 4800
    text_chunks = chunk_text_from_file(cleaned_text_filepath, max_chars_per_chunk=MAX_CHARS_PER_TTS_CHUNK)
    if not text_chunks:
        print("No text chunks generated for audiobook. Exiting.")
        return

    audio_segments = []
    temp_audio_dir = os.path.join(book_output_dir, "temp_audio_chunks")
    setup_output_directory(temp_audio_dir)

    print(f"\nStarting audio synthesis for {len(text_chunks)} chunks...")
    for i, chunk in enumerate(text_chunks):
        if not chunk.strip():
            print(f"  Skipping empty chunk {i+1}/{len(text_chunks)}.")
            continue

        print(f"  Processing chunk {i+1}/{len(text_chunks)} (approx {len(chunk)} chars): '{chunk[:50].replace('\n', ' ')}...'")
        
        temp_audio_file = os.path.join(temp_audio_dir, f"chunk_{i:04d}.mp3")
        
        success = synthesize_text_to_speech(chunk, final_voice_name, final_language_code, final_voice_gender, temp_audio_file, final_pitch, final_speaking_rate)
        
        if success:
            try:
                audio_segments.append(AudioSegment.from_mp3(temp_audio_file))
            except Exception as e:
                print(f"Error loading generated audio for chunk {i}: {e}. This might indicate a problem with the generated MP3. Skipping this chunk.")
                continue
        else:
            print(f"Failed to synthesize audio for chunk {i} after multiple retries. Skipping this chunk.")
            with open(os.path.join(book_output_dir, f"failed_chunk_{i:04d}.txt"), "w", encoding="utf-8") as err_f:
                err_f.write(chunk)
            continue

    if not audio_segments:
        print("No audio segments were successfully generated for the audiobook. Exiting.")
        return

    print("\nCombining audio segments into final audiobook...")
    combined_audio = AudioSegment.empty()
    for segment in audio_segments:
        combined_audio += segment

    output_audio_file = os.path.join(book_output_dir, f"{sanitized_book_title}_audiobook.mp3")
    combined_audio.export(output_audio_file, format="mp3")
    print(f"Audiobook created successfully: '{output_audio_file}'")

    print("Cleaning up temporary audio files...")
    for file_name in os.listdir(temp_audio_dir):
        os.remove(os.path.join(temp_audio_dir, file_name))
    os.rmdir(temp_audio_dir)
    print("Cleaned up temporary audio files.")


if __name__ == "__main__":
    generate_full_audiobook()