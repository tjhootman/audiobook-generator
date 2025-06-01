import re
import requests
import nltk
from gtts import gTTS

nltk.download('punkt')

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





# <--- Main execution block --->

# request the raw text of The Great Gatsby
r = requests.get(r'https://www.gutenberg.org/cache/epub/64317/pg64317.txt')
book_content = r.text

# Write the content to a file
with open('my_book.txt', 'w', encoding='utf-8') as f:
    f.write(book_content)

# Define your input and output file paths
input_book_path = 'my_book.txt' # Make sure this file exists with your book content
output_cleaned_path = 'cleaned_book.txt'
output_audio_file_gtts = 'cleaned_book_audio_gtts.mp3'

# Process the text
cleaned_book_content = clean_text(input_book_path)

# Export the processed text to the output file
if cleaned_book_content: # Only export if the processing was successful
    try:
        with open(output_cleaned_path, 'w', encoding='utf-8') as output_file:
            output_file.write(cleaned_book_content)
        print(f"Successfully exported cleaned text to '{output_cleaned_path}'")

        # Count characters and output
        character_count = len(cleaned_book_content)
        print(f"Character count (including spaces and newlines): {character_count}")

        # Convert to speech using gTTS
        convert_text_to_speech_gtts(cleaned_book_content, output_audio_file_gtts, lang='en')

    except PermissionError:
        print(f"Error: Permission denied to write to file '{output_cleaned_path}'. "
              f"Check file permissions or target directory.")
    except IsADirectoryError:
        print(f"Error: '{output_cleaned_path}' is a directory. Cannot write to it as a file.")
    except UnicodeEncodeError as e:
        print(f"Error: Unable to encode text to UTF-8 for '{output_cleaned_path}'. "
              f"Details: {e}")
    except IOError as e:
        print(f"An I/O error occurred while writing to file '{output_cleaned_path}': {e}")
    except Exception as e:
        print(f"An unexpected error occurred during export: {e}")

# Read and print the cleaned content to verify (optional)
# with open(output_cleaned_path, 'r', encoding='utf-8') as f:
#     print("\n--- Cleaned Content ---")
#     print(f.read())
