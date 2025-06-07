import os
from dotenv import load_dotenv
from google.cloud import texttospeech
import re # Import regular expression module

load_dotenv() # This loads the variables from .env into your script's environment

def chunk_text(text, max_chars_per_chunk=4800):
    """
    Chunks a long string of text into smaller pieces,
    preferring to break at paragraph boundaries.
    If a paragraph is too long, it will be broken by sentence.
    """
    chunks = []
    paragraphs = text.split('\n\n') # Split by double newline for paragraphs

    current_chunk = ""
    for para in paragraphs:
        # Remove leading/trailing whitespace from paragraph
        para = para.strip()
        if not para:
            continue

        # If adding the next paragraph exceeds the limit
        if len(current_chunk) + len(para) + 2 > max_chars_per_chunk and current_chunk: # +2 for potential newlines
            chunks.append(current_chunk.strip())
            current_chunk = ""

        # If the paragraph itself is too long, break it down by sentences
        if len(para) > max_chars_per_chunk:
            sentences = re.split(r'(?<=[.!?])\s+', para) # Split by sentence-ending punctuation and whitespace
            sentence_chunk = ""
            for sentence in sentences:
                if len(sentence_chunk) + len(sentence) + 1 > max_chars_per_chunk and sentence_chunk:
                    chunks.append(sentence_chunk.strip())
                    sentence_chunk = ""
                sentence_chunk += sentence + " "
            if sentence_chunk:
                chunks.append(sentence_chunk.strip())
        else:
            # Add paragraph to current chunk
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para

    if current_chunk: # Add any remaining text
        chunks.append(current_chunk.strip())

    return chunks

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
            # Depending on severity, you might want to break, retry, or log.
            continue # Continue to next chunk if one fails

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
    if not os.path.exists(input_filepath):
        print(f"Error: Input file not found at {input_filepath}")
        return []

    try:
        with open(input_filepath, "r", encoding="utf-8") as file:
            full_text = file.read()
    except Exception as e:
        print(f"Error reading input file {input_filepath}: {e}")
        return []

    print(f"Processing chapter {chapter_num} from {input_filepath}")
    chunks = chunk_text(full_text, max_chars_per_chunk)
    print(f"Text chunked into {len(chunks)} parts.")

    # Base filename for output, e.g., "audiobook_chapter1"
    base_output_name = f"audiobook_chapter{chapter_num}"
    synthesized_files = synthesize_audio_from_chunks(chunks, base_output_name, chapter_num)

    return synthesized_files

# --- Example Usage ---

# 1. Create a dummy text file for demonstration
dummy_text_content_long = """
Chapter 1: The Old Mill. The wind howled mournfully across the moor,
whipping the ancient timbers of the old mill. Inside, the miller, a man
of grizzled beard and weary eyes, tended to his lonely duties. He had lived
in this remote place all his life, and the creak of the grinding stones
was as familiar to him as his own heartbeat. Tonight, however, there was
an unusual chill in the air, a silence that felt heavier than usual between
the gusts of wind. He shivered, pulling his woolen cloak tighter, and cast
a nervous glance towards the darkened windows.

The air grew colder. A sudden gust rattled the loose panes, and the miller
jumped, his heart pounding. He told himself it was just the wind, nothing
more. But deep down, a primal fear stirred. Tales of the moor, of ancient
spirits and lost travelers, flooded his mind. He grabbed a lantern, its
flickering light doing little to dispel the gloom, and began his rounds,
checking the locks, double-checking the rusty bolts. Every shadow seemed
to lengthen, every creak of the old wood sounded like a footstep.

He remembered the story his grandmother used to tell, about the 'Whispering
Stone' just beyond the mill's boundary. They said if you listened closely
on a moonless night, you could hear the whispers of those lost to the moor.
He scoffed at the memory, but still, a shiver ran down his spine. He was a
man of logic, of stone and grain, not of old wives' tales. Yet, the mill,
usually a comforting presence, felt ominous tonight.

(This is a very long paragraph to test sentence splitting within a paragraph.
It goes on and on, trying to reach a significant length to ensure that the
chunking logic properly breaks it down by sentences if the entire paragraph
exceeds the maximum character limit. We need enough text here to reliably
trigger the internal sentence-based splitting. The Google Cloud Text-to-Speech
API has character limits per request, typically around 5,000 for standard voices
and up to 100,000 for Chirp voices, so we want to make sure we don't exceed that
in a single API call. This is just a test to simulate very dense text. The
purpose is to confirm that the `chunk_text` function handles paragraphs that are
individually larger than the `max_chars_per_chunk` by splitting them further
into sentences. This ensures that no single API request becomes too large,
even if a single paragraph is excessively long. The exact splitting will
depend on the regular expression used for sentence detection.)
"""

input_text_filename = "long_chapter1.txt"
input_text_filepath = os.path.join("./input", input_text_filename)

os.makedirs("./input", exist_ok=True)
with open(input_text_filepath, "w", encoding="utf-8") as f:
    f.write(dummy_text_content_long)
print(f"Created dummy input file: {input_text_filepath}")

# 2. Call the new function
print("\nCreating audiobook chapter from file with chunking...")
synthesized_files = create_audiobook_chapter(input_text_filepath, chapter_num=1, max_chars_per_chunk=4800)
print(f"Finished synthesizing chapter 1. Total files: {len(synthesized_files)}")

# At this point, `synthesized_files` will contain a list of paths to your MP3 files.
# You could then use a tool like pydub to concatenate them if desired.
# (e.g., pip install pydub)
# from pydub import AudioSegment
# combined_audio = AudioSegment.empty()
# for f in synthesized_files:
#     combined_audio += AudioSegment.from_mp3(f)
# combined_audio.export("./output/audiobook_chapter1_full.mp3", format="mp3")