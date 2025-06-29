import os
import re
from dotenv import load_dotenv
from google.cloud import texttospeech
from text_processing import export_cleaned_text

load_dotenv()

def chunk_text_from_file(input_filepath, max_chars_per_chunk=4800):
    """
    Reads a text file and chunks its content into smaller pieces,
    preferring to break at paragraph boundaries.
    If a paragraph is too long, it will be broken by sentence.

    Args:
        input_filepath (str): The path to the input text file.
        max_chars_per_chunk (int): The maximum number of characters allowed per chunk.

    Returns:
        list: A list of strings, where each string is a text chunk.
    """
    if not os.path.exists(input_filepath):
        print(f"Error: Input file not found at {input_filepath}")
        return []

    try:
        with open(input_filepath, "r", encoding="utf-8") as file:
            text = file.read()
    except Exception as e:
        print(f"Error reading input file {input_filepath}: {e}")
        return []

    chunks = []
    paragraphs = text.split('\n\n')

    current_chunk = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Ensure max_chars_per_chunk is an integer here as well,
        # though the main fix is in generate_full_audiobook.
        # This is a safeguard if this function were called directly with a string.
        # It's good practice to ensure types at function boundaries.
        try:
            max_chars_per_chunk = int(max_chars_per_chunk)
        except ValueError:
            print(f"Warning: max_chars_per_chunk '{max_chars_per_chunk}' could not be converted to int. Using default 4800.")
            max_chars_per_chunk = 4800


        if len(current_chunk) + len(para) + 2 > max_chars_per_chunk and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = ""

        if len(para) > max_chars_per_chunk:
            sentences = re.split(r'(?<=[.!?])\s+', para)
            sentence_chunk = ""
            for sentence in sentences:
                if len(sentence_chunk) + len(sentence) + 1 > max_chars_per_chunk and sentence_chunk:
                    chunks.append(sentence_chunk.strip())
                    sentence_chunk = ""
                sentence_chunk += sentence + " "
            if sentence_chunk:
                chunks.append(sentence_chunk.strip())
        else:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks

def synthesize_audio_from_chunks(chunks, base_output_filename="output", start_part_num=1):
    """
    Synthesizes speech from a list of text chunks and saves them as separate files.

    Args:
        chunks (list): A list of text strings, each representing a chunk.
        base_output_filename (str): The base name for output audio files (e.g., "chapter1_part").
        start_part_num (int): The starting part number for naming the files.

    Returns:
        list: A list of paths to the generated audio files.
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

def generate_full_audiobook(book_title, cleaned_book_content, cleaned_file_path, output_directory, max_chars_per_chunk=4800): # Added output_directory here
    """
    Synthesizes the entire cleaned book content as a series of audiobook files.

    Args:
        book_title (str): The title of the book.
        cleaned_book_content (str): The entire cleaned text content of the book.
        cleaned_file_path (str): The path where the cleaned text is/should be exported.
        output_directory (str): The directory to save the generated audio files. (This argument was missing in your original function signature,
                                  but present in the main() call in the traceback)
        max_chars_per_chunk (int): Maximum characters per API request.
    """
    # CRITICAL FIX: Ensure max_chars_per_chunk is an integer
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

    print(f"\nSynthesizing: {book_title} (Full Book)")

    # 1. Chunk the text
    chunks = chunk_text_from_file(cleaned_file_path, max_chars_per_chunk)

    if not chunks:
        print("No chunks were generated from the cleaned text. Skipping audio synthesis.")
        return

    print(f"Text chunked into {len(chunks)} parts.")

    # 2. Synthesize audio from the chunks
    synthesized_audio_files = synthesize_audio_from_chunks(chunks, base_output_name, start_part_num=1)

    if synthesized_audio_files:
        print(f"Generated {len(synthesized_audio_files)} audio part(s) for '{book_title}'.")
        print("All audio files for the full book are located in the './output/' directory.")
    else:
        print(f"Failed to generate audio for '{book_title}'.")

    print(f"\n--- Full Audiobook Generation Complete for '{book_title}' ---")
    