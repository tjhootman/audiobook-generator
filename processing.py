import re
import nltk
from gtts import gTTS

nltk.download('punkt')


def get_book_title(text_content):
    """
    Locates the "Title: " line in a string and extracts the book title.
    Sanitizes the title for use in file names.

    Args:
        text_content (str): The input text content as a string.

    Returns:
        str: The sanitized book title, or "unknown_book" if not found or an error occurs.
    """
    default_title = "unknown_book"
    
    # Split the content into lines and iterate through them
    # You can still limit the lines to check, e.g., first 15 lines
    lines = text_content.splitlines()
    for i, line in enumerate(lines):
        if i >= 15:  # Stop after checking the first 15 lines
            break
            
        match = re.match(r'Title:\s*(.*)', line.strip(), re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            # Sanitize the title for filename use
            # Remove characters that are invalid in filenames
            # and replace spaces with underscores (optional, but good practice)
            sanitized_title = re.sub(r'[\\/:*?"<>;,|]', '', title) # Invalid filename chars
            sanitized_title = re.sub(r'\s+', '_', sanitized_title) # Replace spaces with underscores
            sanitized_title = sanitized_title.strip('._') # Clean up leading/trailing underscores/dots
            return sanitized_title if sanitized_title else default_title
            
    return default_title

def clean_text(file_path):
    """
    Reads a text file, removes mid-sentence line breaks, and preserves
    paragraph breaks (indicated by two or more newlines).

    Args:
        file_path (str): The path to the input text file.

    Returns:
        str: The processed text with mid-sentence line breaks removed.
    """
    text = ""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
    except FileNotFoundError:
        print(f"Error: The input file '{file_path}' was not found. Please check the path.")
        return ""
    except PermissionError:
        print(f"Error: Permission denied to read file '{file_path}'. Check file permissions.")
        return ""
    except IsADirectoryError:
        print(f"Error: '{file_path}' is a directory, not a file. Cannot read.")
        return ""
    except UnicodeDecodeError as e:
        print(f"Error: Unable to decode file '{file_path}' with UTF-8 encoding. "
              f"It might be in a different encoding. Details: {e}")
        return ""
    except IOError as e: # Catches other general I/O errors
        print(f"An I/O error occurred while reading file '{file_path}': {e}")
        return ""
    except Exception as e: # Catches any other unexpected errors during reading
        print(f"An unexpected error occurred while reading file '{file_path}': {e}")
        return ""

    # Step 1: Handle hyphenated word breaks (e.g., "senten-\nce")
    # This removes the hyphen and the line break, joining the two parts of the word.
    # Example: "some- \nthing" becomes "something"
    # The \s* allows for optional whitespace around the hyphen and newline.
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)

    # Step 2: Normalize sequences of two or more newlines to a single standard paragraph break placeholder.
    # This ensures that actual paragraph breaks (blank lines or multiple newlines)
    # are preserved and treated uniformly.
    # Example: "\n\n", "\n  \n", "\n\n\n" all become 'PARAGRAPH_BREAK_PLACEHOLDER'
    text = re.sub(r'\n\s*\n+', 'PARAGRAPH_BREAK_PLACEHOLDER', text)


    # Step 3: Replace any *remaining* single newlines with a space.
    # At this point, any '\n' left in the text *should* be a mid-sentence line break
    # because all paragraph breaks were converted to the placeholder in Step 2.
    # We also strip leading/trailing whitespace around these single newlines to avoid
    # extra spaces if the original had "word \n word".
    text = re.sub(r'\s*\n\s*', ' ', text)


    # Step 4: Restore the paragraph breaks from the placeholder.
    text = text.replace('PARAGRAPH_BREAK_PLACEHOLDER', '\n\n')

    # Step 5: Clean up any instances of multiple spaces that might have been introduced
    # (e.g., if original text had "word  \n  word" it could become "word    word").
    text = re.sub(r' {2,}', ' ', text).strip()

    return text


def convert_text_to_speech_gtts(text_content, output_audio_file='output_book.mp3', lang='en'):
    """
    Converts text content to speech using gTTS and saves it as an MP3 file.

    Args:
        text_content (str): The text to convert to speech.
        output_audio_file (str): The name of the output MP3 file.
        lang (str): The language of the text (e.g., 'en' for English, 'fr' for French).
    """
    if not text_content:
        print("No text content provided for speech conversion.")
        return

    print(f"Converting text to speech using gTTS (language: {lang})...")
    try:
        # Create a gTTS object
        tts = gTTS(text=text_content, lang=lang, slow=False) # slow=True for slower speech

        # Save the audio file
        tts.save(output_audio_file)
        print(f"Speech saved to '{output_audio_file}'")

        # Optional: Play the audio file directly (requires a system command)
        # On Windows: os.system(f"start {output_audio_file}")
        # On macOS: os.system(f"afplay {output_audio_file}")
        # On Linux: os.system(f"xdg-open {output_audio_file}") # or 'mpg321', 'vlc', etc.

    except Exception as e:
        print(f"An error occurred during gTTS conversion: {e}")
        print("Please ensure you have an active internet connection.")

# Export the processed text to the output file
def export_cleaned_text(content: str, file_path: str) -> bool:
    """
    Exports the cleaned text content to a specified file path,
    prepending the character count to the first line.

    Args:
        content: The cleaned text content to write.
        file_path: The full path to the output file (e.g., './output/book_cleaned.txt').

    Returns:
        True if the export was successful, False otherwise.
    """
    if not content:
        print("Warning: No cleaned content to export.")
        return False

    # Calculate character count of the actual content
    character_count = len(content)
    print(f"Character count (including spaces and newlines): {character_count}")

    # Prepare the content to be written
    # We add a newline after the count so the actual text starts on the next line
    content_to_write = f"Character Count: {character_count}\n\n{content}"

    try:
        with open(file_path, 'w', encoding='utf-8') as output_file:
            output_file.write(content_to_write)
        print(f"Successfully exported cleaned text to '{file_path}'")
        return True
    except PermissionError:
        print(f"Error: Permission denied to write to file '{file_path}'. "
              f"Check file permissions or target directory.")
    except IsADirectoryError:
        print(f"Error: '{file_path}' is a directory. Cannot write to it as a file.")
    except UnicodeEncodeError as e:
        print(f"Error: Unable to encode text to UTF-8 for '{file_path}'. "
              f"Details: {e}")
    except IOError as e:
        print(f"An I/O error occurred while writing to file '{file_path}': {e}")
    except Exception as e:
        print(f"An unexpected error occurred during export: {e}")
    return False