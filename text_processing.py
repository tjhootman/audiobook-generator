"""Module containing functions for text file cleaning and exporting."""

import os
import re
import requests
import nltk
from gtts import gTTS

nltk.download('punkt')

def get_user_book_url() -> str:
    """
    Prompts the user for a Project Gutenberg URL and validates it.

    Returns:
        The validated URL string.
    """
    while True:
        user_url = input("Please enter the Project Gutenberg URL for the raw text of the book (e.g., https://www.gutenberg.org/cache/epub/76/pg76.txt): ")
        if user_url.strip():
            # Basic check for a plausible URL start, could be more robust with regex
            if user_url.startswith("http://www.gutenberg.org") or user_url.startswith("https://www.gutenberg.org"):
                return user_url
            else:
                print("Invalid URL format. Please enter a Project Gutenberg URL.")
        else:
            print("URL cannot be empty. Please try again.")

def download_book_content(url: str) -> str | None:
    """
    Downloads the raw text content of a book from the given URL.

    Args:
        url: The URL of the book's raw text.

    Returns:
        The book content as a string if successful, None otherwise.
    """
    print(f"Attempting to download from: {url}")
    try:
        r = requests.get(url)
        r.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        return r.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {e}")
        print("Please ensure the URL is correct and accessible.")
        return None

def setup_output_directory(directory_path: str):
    """
    Creates the specified output directory if it doesn't exist.

    Args:
        directory_path: The path to the directory to create.
    """
    os.makedirs(directory_path, exist_ok=True)
    print(f"Output directory '{directory_path}' ensured.")

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

def export_raw_text(content: str, book_title: str, output_dir: str) -> str | None:
    """
    Exports the raw book content to a file.

    Args:
        content: The raw text content of the book.
        book_title: The title of the book.
        output_dir: The directory where the file should be saved.

    Returns:
        The full path to the raw output file if successful, None otherwise.
    """
    output_raw_path = os.path.join(output_dir, f"{book_title}_raw.txt")
    try:
        with open(output_raw_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Successfully exported raw text to '{output_raw_path}'")
        return output_raw_path
    except IOError as e:
        print(f"Error exporting raw text to '{output_raw_path}': {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while exporting raw text: {e}")
        return None

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
