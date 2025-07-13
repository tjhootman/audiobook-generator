"""
Module containing functions for text file cleaning, exporting, and preparing
text for Text-to-Speech (TTS) conversion. This includes downloading content,
extracting metadata, sanitizing text, and chunking it into manageable sizes.
"""

import os
import re
import requests
import nltk

# Ensure 'punkt' and 'punkt_tab' tokenizers are downloaded from NLTK.
# These tokenizers are crucial for sentence segmentation, which is used
# when chunking text for TTS, especially for long paragraphs.
# A `LookupError` is caught if the resource is not found, triggering a download.
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    print("Downloading NLTK 'punkt' tokenizer data...")
    nltk.download('punkt')

try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    print("Downloading NLTK 'punkt_tab' tokenizer data...")
    nltk.download('punkt_tab')

def setup_output_directory(directory_path: str):
    """
    Creates the specified output directory if it does not already exist.
    This ensures that file operations can proceed without `FileNotFoundError`
    due to missing directories.

    Args:
        directory_path (str): The path to the directory to create.
    """
    os.makedirs(directory_path, exist_ok=True)
    print(f"Output directory '{directory_path}' ensured.")

def get_user_book_url() -> str:
    """
    Prompts the user for a Project Gutenberg URL and performs a basic validation
    to ensure it starts with the expected Project Gutenberg domain.

    Returns:
        str: The validated Project Gutenberg URL provided by the user.
    """
    while True:
        user_url = input("Please enter the Project Gutenberg URL for the raw text of the book (e.g., https://www.gutenberg.org/cache/epub/76/pg76.txt): ")
        if user_url.strip():
            # Basic validation for a plausible Project Gutenberg URL.
            if user_url.startswith("http://www.gutenberg.org") or user_url.startswith("https://www.gutenberg.org"):
                return user_url
            else:
                print("Invalid URL format. Please enter a Project Gutenberg URL.")
        else:
            print("URL cannot be empty. Please try again.")

def download_book_content(url: str) -> str | None:
    """
    Downloads the raw text content of a book from the given URL.
    It uses the `requests` library and includes error handling for network issues
    or invalid URLs.

    Args:
        url (str): The URL of the book's raw text file.

    Returns:
        str | None: The book content as a string if the download is successful,
                    otherwise returns `None` in case of an error.
    """
    print(f"Attempting to download from: {url}")
    try:
        r = requests.get(url)
        r.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx response codes)
        return r.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {e}")
        print("Please ensure the URL is correct and accessible.")
        return None

def get_book_title(text_content: str) -> tuple[str, str]:
    """
    Locates the "Title: " line in the initial part of the book's text content
    and extracts the book's title. It also sanitizes the title to make it
    suitable for use in filenames (e.g., removing invalid characters, replacing spaces).

    Args:
        text_content (str): The raw input text content of the book.

    Returns:
        tuple[str, str]: A tuple containing two strings:
                         1. The raw book title as found in the text.
                         2. The sanitized book title suitable for filenames.
                         Returns ("unknown_book", "unknown_book") if the title
                         line is not found or is empty.
    """
    default_title = "unknown_book"
    
    # Split the content into lines and iterate through the first few lines
    # where metadata like title is typically found in Project Gutenberg files.
    lines = text_content.splitlines()
    for i, line in enumerate(lines):
        if i >= 20:  # Stop after checking the first 20 lines to optimize performance
            break
            
        # Use re.match to find 'Title:' at the beginning of the stripped line, case-insensitively.
        match = re.match(r'Title:\s*(.*)', line.strip(), re.IGNORECASE)
        if match:
            raw_title = match.group(1).strip() # Extract the text after "Title:"
            
            # If the extracted raw title is empty, return default titles.
            if not raw_title:
                return (default_title, default_title)

            # Sanitize the title for filename use:
            # 1. Remove characters that are invalid in filenames for most operating systems.
            #    Windows invalid chars: \ / : * ? " < > |
            #    Semi-colon and comma are also included for broader compatibility, though not strictly invalid.
            sanitized_title = re.sub(r'[\\/:*?"<>|,;]', '', raw_title)

            # 2. Replace sequences of one or more whitespace characters (spaces, tabs, newlines)
            #    with a single underscore.
            sanitized_title = re.sub(r'\s+', '_', sanitized_title)

            # 3. Clean up any leading/trailing underscores or dots that might be left
            #    from previous sanitization if the title started or ended with special characters or spaces.
            sanitized_title = sanitized_title.strip('._')

            # 4. Ensure the sanitized title is not empty after all operations; revert to default if it is.
            final_sanitized_title = sanitized_title if sanitized_title else default_title

            return (raw_title, final_sanitized_title)
            
    # If no title is found within the checked lines, return default titles.
    return (default_title, default_title)

def get_book_author(text_content: str) -> str:
    """
    Locates the "Author: " line in the initial part of the book's text content
    and extracts the author's name.

    Args:
        text_content (str): The raw input text content of the book.

    Returns:
        str: The raw book author's name as found in the text.
             Returns "unknown_author" if the author line is not found or is empty.
    """
    default_author = "unknown_author"
    
    lines = text_content.splitlines()
    for i, line in enumerate(lines):
        if i >= 20:  # Stop after checking the first 20 lines.
            break
            
        # Use re.match to find 'Author:' at the beginning of the stripped line, case-insensitively.
        match = re.match(r'Author:\s*(.*)', line.strip(), re.IGNORECASE)
        if match:
            raw_author = match.group(1).strip()
            
            # Return the raw author, or default if it's empty after stripping.
            return raw_author if raw_author else default_author
            
    # If no author is found within the checked lines, return the default.
    return default_author

def export_raw_text(content: str, book_title: str, output_dir: str) -> str | None:
    """
    Exports the raw, downloaded book content to a text file within the specified directory.

    Args:
        content (str): The raw text content of the book.
        book_title (str): The sanitized title of the book, used for the filename.
        output_dir (str): The directory where the file should be saved.

    Returns:
        str | None: The full path to the exported raw text file if successful,
                    otherwise `None` in case of an error.
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

def clean_text(file_path: str, raw_title: str) -> str:
    """
    Reads a text file, performs a series of cleaning operations:
    1. Removes Project Gutenberg specific header and footer boilerplate text.
    2. Handles hyphenated word breaks across lines (e.g., "senten-\nce" becomes "sentence").
    3. Preserves genuine paragraph breaks (indicated by two or more newlines).
    4. Replaces mid-sentence line breaks with a single space.
    5. Replaces underscores with blank spaces.
    6. Normalizes multiple spaces into single spaces.

    Args:
        file_path (str): The path to the input raw text file.
        raw_title (str): The raw title of the book, used to construct
                         the Project Gutenberg start and end markers for removal.

    Returns:
        str: The processed and cleaned text content. Returns an empty string
             if the input file cannot be read or an error occurs during cleaning.
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

    # Define the start and end marker lines, converting the raw title to uppercase
    # as typically found in Project Gutenberg markers.
    start_marker = f"*** START OF THE PROJECT GUTENBERG EBOOK {raw_title.upper()} ***"
    end_marker = f"*** END OF THE PROJECT GUTENBERG EBOOK {raw_title.upper()} ***"
    # Note: The original code includes a non-breaking space (\xa0) in the end marker.
    # It's good to keep this in mind if the marker exact match fails.
    # For robustness, you might consider a regex for the markers if they vary.

    # --- Step 0.1: Remove text before and including the start marker ---
    start_index = text.find(start_marker)
    if start_index != -1:
        # If the marker is found, keep only the text *after* the marker.
        # Find the end of the start marker line to ensure we start cleanly.
        end_of_start_marker_line = text.find('\n', start_index + len(start_marker))
        if end_of_start_marker_line != -1:
            # +1 to skip the newline, then lstrip to remove any leading whitespace remaining.
            text = text[end_of_start_marker_line + 1:].lstrip()
        else:
            # Fallback if no newline found after the marker (unlikely for typical PG files).
            text = text[start_index + len(start_marker):].lstrip()
    else:
        print(f"Warning: The start marker '{start_marker}' was not found in '{file_path}'. "
              f"Cannot remove initial boilerplate.")

    # --- Step 0.2: Remove text after and including the end marker ---
    end_index = text.find(end_marker)
    if end_index != -1:
        # If the end marker is found, keep only the text *before* the marker.
        # rstrip to remove any trailing whitespace immediately before the marker.
        text = text[:end_index].rstrip()
    else:
        print(f"Warning: The end marker '{end_marker}' was not found in '{file_path}'. "
              f"Cannot remove final boilerplate.")

    # Step 1: Handle hyphenated word breaks (e.g., "senten-\nce" or "some- \nthing").
    # This regex finds a word part, a hyphen, optional whitespace, a newline,
    # optional whitespace, and another word part, then joins them.
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)

    # Step 2: Normalize sequences of two or more newlines (potentially with intervening whitespace)
    # to a single standard paragraph break placeholder. This preserves true paragraph breaks.
    text = re.sub(r'\n\s*\n+', 'PARAGRAPH_BREAK_PLACEHOLDER', text)

    # Step 3: Replace any *remaining* single newlines with a space.
    # At this point, any '\n' left in the text should be a mid-sentence line break
    # because all paragraph breaks were handled in Step 2.
    # `\s*\n\s*` handles potential leading/trailing whitespace around the newline.
    text = re.sub(r'\s*\n\s*', ' ', text)

    # Step 4: Restore the paragraph breaks from the placeholder.
    text = text.replace('PARAGRAPH_BREAK_PLACEHOLDER', '\n\n')

    # Step 5: Replace underscores with blank spaces. This is common in some
    # older digital texts from Project Gutenberg.
    text = text.replace('_', ' ')

    # Step 6: Clean up any instances of multiple spaces that might have been introduced
    # during previous cleaning steps (e.g., if original text had "word  \n  word" it could become "word    word").
    # Also strips leading/trailing whitespace from the entire cleaned text.
    text = re.sub(r' {2,}', ' ', text).strip()

    return text

def export_cleaned_text(content: str, file_path: str) -> bool:
    """
    Exports the cleaned text content to a specified file path.
    It also ensures the target directory exists before writing.

    Args:
        content (str): The cleaned text content to write.
        file_path (str): The full path to the output file (e.g., './output/book_cleaned.txt').

    Returns:
        bool: True if the export was successful, False otherwise.
    """
    if not content:
        print("Warning: No cleaned content to export.")
        return False

    # Calculate character count for informational purposes.
    character_count = len(content)
    print(f"Character count (including spaces and newlines): {character_count}")

    try:
        # Ensure the directory exists before attempting to write the file.
        output_dir = os.path.dirname(file_path)
        if output_dir: # Only try to create if there's a directory part in the path
            os.makedirs(output_dir, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as output_file:
            output_file.write(content)
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

def chunk_text_from_file(input_filepath: str, max_chars_per_chunk: int = 4800) -> list[str]:
    """
    Reads a text file and chunks its content into smaller pieces,
    prioritizing breaks at paragraph boundaries. If a single paragraph is
    longer than `max_chars_per_chunk`, it will be further broken down by sentence
    to ensure chunk size limits are met for TTS APIs.

    Args:
        input_filepath (str): The path to the input text file (e.g., cleaned text).
        max_chars_per_chunk (int): The maximum number of characters allowed per chunk.
                                   Defaults to 4800, which is a common limit for TTS APIs.

    Returns:
        list[str]: A list of strings, where each string is a text chunk
                   ready for TTS synthesis. Returns an empty list if the
                   file cannot be read or no chunks are generated.
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
    # Split the text into paragraphs using two or more newlines as delimiters.
    paragraphs = text.split('\n\n')

    current_chunk = ""
    for para in paragraphs:
        para = para.strip()
        if not para:  # Skip empty paragraphs that might result from splitting.
            continue

        # Ensure `max_chars_per_chunk` is an integer for reliable comparison.
        # This acts as a safeguard.
        try:
            max_chars_per_chunk = int(max_chars_per_chunk)
        except ValueError:
            print(f"Warning: max_chars_per_chunk '{max_chars_per_chunk}' could not be converted to int. Using default 4800.")
            max_chars_per_chunk = 4800

        # If adding the current paragraph to the `current_chunk` would exceed the limit,
        # and `current_chunk` already contains content, finalize `current_chunk`.
        # Adding 2 for potential `\n\n` separator when combining paragraphs.
        if len(current_chunk) + len(para) + 2 > max_chars_per_chunk and current_chunk:
            chunks.append(current_chunk.strip()) # Add the current chunk and reset
            current_chunk = ""

        # Handle paragraphs that are individually too long (exceed `max_chars_per_chunk`).
        # These need to be broken down by sentence.
        if len(para) > max_chars_per_chunk:
            # Use NLTK's sentence tokenizer (or a regex fallback) to split the long paragraph.
            sentences = nltk.sent_tokenize(para)
            # Fallback to a basic regex split if NLTK fails for some reason or is not robust enough
            # sentences = re.split(r'(?<=[.!?])\s+', para) # Kept commented as NLTK is preferred

            sentence_chunk = ""
            for sentence in sentences:
                # If adding the current sentence to `sentence_chunk` would exceed the limit,
                # and `sentence_chunk` already contains content, finalize `sentence_chunk`.
                # Adding 1 for a space separator.
                if len(sentence_chunk) + len(sentence) + 1 > max_chars_per_chunk and sentence_chunk:
                    chunks.append(sentence_chunk.strip())
                    sentence_chunk = ""
                sentence_chunk += sentence + " " # Add sentence and a space
            if sentence_chunk: # Add any remaining part of the sentence_chunk
                chunks.append(sentence_chunk.strip())
        else:
            # If the paragraph fits, add it to the `current_chunk`.
            if current_chunk:
                current_chunk += "\n\n" + para # Add with paragraph separator
            else:
                current_chunk = para # Start a new chunk with this paragraph

    # After iterating through all paragraphs, add any remaining content in `current_chunk`.
    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks
