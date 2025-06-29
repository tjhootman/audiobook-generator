"""Module containing functions for processing text to speech."""

import os
import re # Import regular expression module
from dotenv import load_dotenv
from google.cloud import texttospeech
from text_processing import export_cleaned_text

load_dotenv() # This loads the variables from .env into your script's environment

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
    paragraphs = text.split('\n\n') # Split by double newline for paragraphs

    current_chunk = ""
    for para in paragraphs:
        # Remove leading/trailing whitespace from paragraph
        para = para.strip()
        if not para:
            continue

        # If adding the next paragraph exceeds the limit AND there's something in current_chunk
        # Add 2 for potential newlines when joining paragraphs
        if len(current_chunk) + len(para) + 2 > max_chars_per_chunk and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = ""

        # If the paragraph itself is too long, break it down by sentences
        if len(para) > max_chars_per_chunk:
            # Split by sentence-ending punctuation followed by whitespace.
            # Lookbehind `(?<=[.!?])` ensures the punctuation is kept with the sentence.
            sentences = re.split(r'(?<=[.!?])\s+', para)
            sentence_chunk = ""
            for sentence in sentences:
                if len(sentence_chunk) + len(sentence) + 1 > max_chars_per_chunk and sentence_chunk:
                    chunks.append(sentence_chunk.strip())
                    sentence_chunk = ""
                # Add a space after each sentence to maintain natural spacing
                sentence_chunk += sentence + " "
            if sentence_chunk: # Add any remaining sentence chunk
                chunks.append(sentence_chunk.strip())
        else:
            # Add paragraph to current chunk
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para

    if current_chunk: # Add any remaining text from the last current_chunk
        chunks.append(current_chunk.strip())

    return chunks

def synthesize_audio_from_chunks(chunks, base_output_filename="output", part_num=1):
    """
    Synthesizes speech from a list of text chunks and saves them as separate files.

    Args:
        chunks (list): A list of text strings, each representing a chunk.
        base_output_filename (str): The base name for output audio files (e.g., "chapter1_part").
        chapter_num (int): The current chapter number for naming.
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
    for i, chunk in enumerate(chunks):
        part_filename = f"{base_output_filename}_part{part_num}.mp3"
        full_output_path = os.path.join(output_dir, part_filename)
        part_num = part_num + 1

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
            print(f"Error synthesizing part {part_num}: {e}")
            continue

    return audio_file_paths

def create_audiobook_parts(book_title, input_filepath, part_num=1, max_chars_per_chunk=4800):
    """
    Reads a text file, chunks its content, and synthesizes speech for each chunk,
    saving them as individual audio files for an audiobook chapter.

    Args:
        input_filepath (str): The path to the input text file for the chapter.
        chapter_num (int): The chapter number (used for naming output files).
        max_chars_per_chunk (int): Maximum characters per API request.
    """
    print(f"Processing part {part_num} from {input_filepath}")
    # Now call the refactored chunk_text_from_file
    chunks = chunk_text_from_file(input_filepath, max_chars_per_chunk)

    if not chunks: # If chunk_text_from_file returned empty due to error
        return []

    print(f"Text chunked into {len(chunks)} parts.")

    base_output_name = f"{book_title}"
    synthesized_files = synthesize_audio_from_chunks(chunks, base_output_name, part_num)

    return synthesized_files

def generate_full_audiobook(book_title, cleaned_book_content, cleaned_file_path, output_directory):
    """
    Refactored function to synthesize the entire cleaned book content
    as a single audiobook file.

    Args:
        book_title (str): The title of the book.
        cleaned_book_content (str): The entire cleaned text content of the book.
        cleaned_file_path (str): The path where the cleaned text is/should be exported.
        output_directory (str): The directory to save the generated audio files.
    """

    if cleaned_book_content:
        if export_cleaned_text(cleaned_book_content, cleaned_file_path):
            print(f"Cleaned text exported to: {cleaned_file_path}")

            # --- Full Book Audiobook Generation Steps ---
            print("\n--- Starting Full Book Audiobook Generation ---")

            # Read the cleaned text content (re-reading for consistency with original structure,
            # though cleaned_book_content is already available)
            try:
                with open(cleaned_file_path, "r", encoding="utf-8") as f:
                    full_cleaned_text = f.read()
            except Exception as e:
                print(f"Error reading cleaned text file: {e}")
                return

            if not full_cleaned_text.strip(): # Check if content is empty or just whitespace
                print("Cleaned text content is empty. Skipping audiobook generation.")
                return

            # Sanitize book title for filename
            book_title_for_file = re.sub(r'[^\w\s-]', '', book_title).replace(' ', '_')[:50]
            output_filename_base = f"{book_title_for_file}_Full_Book"

            print(f"\nSynthesizing: {book_title} (Full Book)")

            # Call create_audiobook_chapter (or a new function like create_full_audiobook)
            # You might need to adapt create_audiobook_chapter to handle a single file
            # and potentially remove the 'chapter_num' parameter if it's not needed.
            # For this refactor, we'll keep the call structure similar but imply
            # it's processing the whole book.
            synthesized_audio_files = create_audiobook_parts(
                book_title=book_title,
                input_filepath=cleaned_file_path, # Use the directly exported file
                part_num=1, # Can be set to 1 or removed if create_audiobook_chapter is modified
                max_chars_per_chunk=4800 # Google Cloud TTS limit
            )

            if synthesized_audio_files:
                print(f"Generated {len(synthesized_audio_files)} audio part(s) for '{book_title}'.")
            else:
                print(f"Failed to generate audio for '{book_title}'.")

            # No temporary chapter files to clean up in this refactored version

            print(f"\n--- Full Audiobook Generation Complete for '{book_title}' ---")
            print("All audio files for the full book are located in the './output/' directory.")

        else:
            print("Failed to export cleaned text. Skipping audiobook generation.")
    else:
        print("No cleaned content was generated. Skipping export and audiobook generation.")
