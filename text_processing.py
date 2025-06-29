"""Module containing functions for text file cleaning and exporting."""

import os
import re
import requests
import nltk

nltk.download('punkt')

def setup_output_directory(directory_path: str):
    """
    Creates the specified output directory if it doesn't exist.

    Args:
        directory_path: The path to the directory to create.
    """
    os.makedirs(directory_path, exist_ok=True)
    print(f"Output directory '{directory_path}' ensured.")

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

def get_book_title(text_content):
    """
    Locates the "Title: " line in a string and extracts the book title.
    Sanitizes the title for use in file names.

    Args:
        text_content (str): The input text content as a string.

    Returns:
        tuple: A tuple containing (raw_book_title, sanitized_book_title).
               Returns ("unknown_book", "unknown_book") if not found or an error occurs.
    """
    default_title = "unknown_book"
    
    # Split the content into lines and iterate through them
    # Increased the limit slightly for robustness in case metadata is a bit further down
    lines = text_content.splitlines()
    for i, line in enumerate(lines):
        if i >= 20:  # Stop after checking the first 20 lines
            break
            
        # Use re.match to find 'Title:' at the beginning of the stripped line
        # re.IGNORECASE makes it case-insensitive
        match = re.match(r'Title:\s*(.*)', line.strip(), re.IGNORECASE)
        if match:
            raw_title = match.group(1).strip() # This is the title before any sanitization
            
            # If the extracted raw title is empty, return default titles for both
            if not raw_title:
                return (default_title, default_title)

            # Sanitize the title for filename use
            # Remove characters that are invalid in filenames for most OSes
            # Windows invalid chars: \ / : * ? " < > |
            # We also include ; , which are not strictly invalid but can cause issues.
            sanitized_title = re.sub(r'[\\/:*?"<>|,;]', '', raw_title)

            # Replace multiple spaces (or tabs, newlines) with a single underscore
            sanitized_title = re.sub(r'\s+', '_', sanitized_title)

            # Clean up leading/trailing underscores or dots that might be left
            # from sanitization if the title started/ended with special chars or spaces
            sanitized_title = sanitized_title.strip('._')

            # Ensure the sanitized title is not empty after all operations.
            # If it becomes empty, revert to default_title.
            final_sanitized_title = sanitized_title if sanitized_title else default_title

            # Return both the raw and the sanitized title as a tuple
            return (raw_title, final_sanitized_title)
            
    # If no title is found after checking all lines, return default titles
    return (default_title, default_title)

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

def clean_text(file_path, raw_title):
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

    # Define the marker line
    marker = f"*** START OF THE PROJECT GUTENBERG EBOOK {raw_title.upper()} ***"

    # --- MODIFIED STEP: Remove text prior to AND including the marker ---
    marker_index = text.find(marker)

    if marker_index != -1:
        # If the marker is found, keep only the text *after* the marker.
        # This is done by starting the slice from marker_index + length of the marker.
        # We also need to account for any newline characters immediately following the marker.
        # Project Gutenberg files often have a newline right after the marker.
        # Let's find the end of the marker line to ensure we start cleanly.
        end_of_marker_line = text.find('\n', marker_index + len(marker))
        if end_of_marker_line != -1:
            text = text[end_of_marker_line + 1:].lstrip() # +1 to skip the newline, then lstrip to remove leading whitespace
        else:
            # If no newline found after the marker (unlikely for PG files but for robustness)
            text = text[marker_index + len(marker):].lstrip()
    else:
        print(f"Warning: The marker '{marker}' was not found in '{file_path}'. "
              f"Processing the entire file.")

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
