"""Module containing functions for processing text to speech."""

import os
from dotenv import load_dotenv
from google.cloud import texttospeech

load_dotenv() # This loads the variables from .env into your script's environment

def synthesize_audio_from_chunks(chunks, base_output_filename="output", chapter_num=1):
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
        part_filename = f"{base_output_filename}_chapter{chapter_num}_part{i+1}.mp3"
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
            print(f"Error synthesizing part {i+1} of chapter {chapter_num}: {e}")
            continue

    return audio_file_paths

def create_audiobook_chapter(input_filepath, chapter_num=1, max_chars_per_chunk=4800):
    """
    Reads a text file, chunks its content, and synthesizes speech for each chunk,
    saving them as individual audio files for an audiobook chapter.

    Args:
        input_filepath (str): The path to the input text file for the chapter.
        chapter_num (int): The chapter number (used for naming output files).
        max_chars_per_chunk (int): Maximum characters per API request.
    """
    print(f"Processing chapter {chapter_num} from {input_filepath}")
    # Now call the refactored chunk_text_from_file
    chunks = chunk_text_from_file(input_filepath, max_chars_per_chunk)

    if not chunks: # If chunk_text_from_file returned empty due to error
        return []

    print(f"Text chunked into {len(chunks)} parts.")

    base_output_name = f"audiobook_chapter{chapter_num}"
    synthesized_files = synthesize_audio_from_chunks(chunks, base_output_name, chapter_num)

    return synthesized_files
