import os
import re
from dotenv import load_dotenv
from google.cloud import texttospeech
from pydub import AudioSegment
from text_processing import export_cleaned_text, chunk_text_from_file

load_dotenv()

def synthesize_audio_from_chunks(chunks, base_output_filename="output", start_part_num=1):
    """
    Synthesizes speech from a list of text chunks and saves them as separate files.

    Args:
        chunks (list): A list of text strings, each representing a chunk.
        base_output_filename (str): The base name for output audio files (e.g., "chapter1_part").
        start_part_num (int): The starting part number for naming the files.

    Returns:
        list: A list of paths to the generated individual audio files.
    """
    client = texttospeech.TextToSpeechClient()
    output_dir = "./output"
    os.makedirs(output_dir, exist_ok=True)

    voice = texttospeech.VoiceSelectionParams(
        language_code="en-GB",
        name="en-GB-Chirp-HD-D"
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    audio_file_paths = []
    current_part_num = start_part_num
    for i, chunk in enumerate(chunks):
        # Using a temporary filename for individual parts, as they will be concatenated
        part_filename = f"{base_output_filename}_part{current_part_num}.mp3"
        full_output_path = os.path.join(output_dir, part_filename)

        synthesis_input = texttospeech.SynthesisInput(text=chunk)

        try:
            response = client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )
            with open(full_output_path, "wb") as out:
                out.write(response.audio_content)
                print(f'Audio content written to file "{full_output_path}"')
            audio_file_paths.append(full_output_path)
        except Exception as e:
            print(f"Error synthesizing part {current_part_num}: {e}")
            continue
        current_part_num += 1

    return audio_file_paths

def concatenate_audio_files(input_files, output_filename):
    """
    Concatenates a list of MP3 audio files into a single MP3 file.

    Args:
        input_files (list): A list of paths to the MP3 files to concatenate.
        output_filename (str): The path and filename for the concatenated output MP3.

    Returns:
        str: The path to the concatenated audio file, or None if an error occurred.
    """
    if not input_files:
        print("No input files provided for concatenation.")
        return None

    print(f"\nConcatenating {len(input_files)} audio files into {output_filename}...")
    combined_audio = AudioSegment.empty()

    try:
        for audio_file in input_files:
            if os.path.exists(audio_file):
                segment = AudioSegment.from_mp3(audio_file)
                combined_audio += segment
            else:
                print(f"Warning: File not found, skipping: {audio_file}")

        combined_audio.export(output_filename, format="mp3")
        print(f"Successfully concatenated audio to: {output_filename}")
        return output_filename
    except Exception as e:
        print(f"Error during audio concatenation: {e}")
        return None

def generate_full_audiobook(book_title, cleaned_book_content, cleaned_file_path, output_directory, max_chars_per_chunk=4800):
    """
    Synthesizes the entire cleaned book content as a series of audiobook files,
    then concatenates them into a single file.

    Args:
        book_title (str): The title of the book.
        cleaned_book_content (str): The entire cleaned text content of the book.
        cleaned_file_path (str): The path where the cleaned text is/should be exported.
        output_directory (str): The directory to save the generated audio files.
        max_chars_per_chunk (int): Maximum characters per API request.
    """

    try:
        max_chars_per_chunk = int(max_chars_per_chunk)
    except ValueError:
        print(f"Error: max_chars_per_chunk '{max_chars_per_chunk}' could not be converted to an integer. Using default 4800.")
        max_chars_per_chunk = 4800

    if not cleaned_book_content.strip():
        print("No cleaned content was provided or it's empty. Skipping audiobook generation.")
        return

    # Export cleaned text
    if export_cleaned_text(cleaned_book_content, cleaned_file_path):
        print(f"Cleaned text exported to: {cleaned_file_path}")
    else:
        print("Failed to export cleaned text. Skipping audiobook generation.")
        return

    print("\n--- Starting Full Book Audiobook Generation ---")

    # Read the cleaned text content (re-reading from file ensures consistency)
    try:
        with open(cleaned_file_path, "r", encoding="utf-8") as f:
            full_cleaned_text = f.read()
    except Exception as e:
        print(f"Error reading cleaned text file at {cleaned_file_path}: {e}")
        return

    if not full_cleaned_text.strip():
        print("Cleaned text content in file is empty. Skipping audiobook generation.")
        return

    # Sanitize book title for filename
    book_title_for_file = re.sub(r'[^\w\s-]', '', book_title).replace(' ', '_')[:50]
    base_output_name = f"{book_title_for_file}"
    final_audiobook_name = os.path.join(output_directory, f"{book_title_for_file}_full_audiobook.mp3")

    print(f"\nSynthesizing: {book_title} (Full Book)")

    # 1. Chunk the text
    chunks = chunk_text_from_file(cleaned_file_path, max_chars_per_chunk)

    if not chunks:
        print("No chunks were generated from the cleaned text. Skipping audio synthesis.")
        return

    print(f"Text chunked into {len(chunks)} parts.")

    # 2. Synthesize audio from the chunks (creates individual part files)
    individual_audio_files = synthesize_audio_from_chunks(chunks, base_output_name, start_part_num=1)

    if individual_audio_files:
        print(f"Generated {len(individual_audio_files)} individual audio part(s) for '{book_title}'.")

        # 3. Concatenate the individual audio files
        concatenated_file = concatenate_audio_files(individual_audio_files, final_audiobook_name)

        if concatenated_file:
            print(f"Full audiobook successfully created at: {concatenated_file}")
            # Optionally, delete the individual part files after concatenation
            for f in individual_audio_files:
                try:
                    os.remove(f)
                    print(f"Removed temporary file: {f}")
                except Exception as e:
                    print(f"Error removing temporary file {f}: {e}")
        else:
            print(f"Failed to concatenate audio files for '{book_title}'. Individual parts remain in './output/'.")
    else:
        print(f"Failed to generate any audio parts for '{book_title}'.")

    print(f"\n--- Full Audiobook Generation Complete for '{book_title}' ---")
