"""Module containing functions for text file cleaning and exporting."""

import os
import re
import requests
import nltk
from gtts import gTTS

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

# Define common chapter patterns
# Using re.IGNORECASE for case-insensitivity
# Using re.MULTILINE to make ^ and $ match start/end of each line
CHAPTER_PATTERNS = [
    r"^(?:CHAPTER|Chapter)\s+(?:I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII|XIV|XV|XVI|XVII|XVIII|XIX|XX|XXI|XXII|XXIII|XXIV|XXV|XXVI|XXVII|XXVIII|XXIX|XXX)\b", # Roman numerals up to XXX
    r"^(?:CHAPTER|Chapter)\s+\d+\b", # Arabic numerals
    r"^(?:BOOK|Book)\s+(?:I|II|III|IV|V|VI|VII|VIII|IX|X)\b", # Books (for multi-book novels)
    r"^(?:SECTION|Section)\s+\d+\b", # Sections
    r"^(?:Part|PART)\s+(?:I|II|III|IV|V|VI|VII|VIII|IX|X|\d+)\b", # Parts
    r"^\s*(?:I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII|XIV|XV|XVI|XVII|XVIII|XIX|XX|XXI|XXII|XXIII|XXIV|XXV|XXVI|XXVII|XXVIII|XXIX|XXX)\.?(?:\s+[\S].*)?$", # Roman numeral alone, possibly with a title on the same line
    r"^\s*\d+\.?\s*(?:[A-Z].*)?$", # Arabic numeral alone, possibly with a title on the same line
]

# You'll need to define these if they are not in your text_processing.py
# For demonstration purposes, I'll put a placeholder here.
# In a real scenario, you would import these from your text_processing.py
# from text_processing import clean_text, export_cleaned_text

def parse_chapters(text_content):
    """
    Parses the full text content of a book to identify and extract chapters.

    Args:
        text_content (str): The cleaned text content of the entire book.

    Returns:
        list[dict]: A list of dictionaries, where each dictionary represents a chapter
                    and contains 'title' (e.g., "Chapter 1", "Preface"), and 'content'.
    """
    chapters = []
    # Combine all patterns into a single regex for splitting.
    # We use a capturing group around the pattern so that `re.split` includes
    # the delimiter in the result, allowing us to capture the chapter title.
    # Ensure the delimiter is preceded by at least two newlines to avoid splitting mid-paragraph.
    # And followed by at least one newline for clear separation.
    chapter_delimiter_pattern = r"(?:\n\n|^)(?P<chapter_title>(?:" + "|".join(CHAPTER_PATTERNS) + r"))(?:\n\n|\n|$)"
    
    # Split the text by the chapter patterns.
    # re.split keeps the captured groups, so we get the chapter titles as part of the split.
    parts = re.split(chapter_delimiter_pattern, text_content, flags=re.IGNORECASE | re.MULTILINE)

    # The first part is usually the front matter before the first actual chapter.
    # The `re.split` behavior means if the pattern is at the very beginning,
    # the first item in `parts` will be an empty string, then the captured group, then the content.
    # If the first item is non-empty, it's considered "front matter".

    # Let's handle the initial non-chapter content (preface, introduction, etc.)
    # The structure of `parts` after split will be:
    # ['', 'Chapter 1', 'Content of Chapter 1', 'Chapter 2', 'Content of Chapter 2', ...]
    # OR:
    # ['Front Matter Content', 'Chapter 1', 'Content of Chapter 1', ...]
    
    current_chapter_title = "Front Matter / Introduction"
    current_chapter_content_parts = []
    
    # `re.split` with a capturing group behaves differently based on matches.
    # The pattern is: (delimiter)(content)(delimiter)(content)...
    # When the delimiter is found, it splits the text, and the captured group for the delimiter is included.
    # If the split pattern includes surrounding newlines, these might be consumed.
    
    # A more robust approach might be to find all matches, then extract content between them.
    
    # Find all chapter markers and their starting positions
    chapter_markers = []
    for match in re.finditer(chapter_delimiter_pattern, text_content, flags=re.IGNORECASE | re.MULTILINE):
        # match.group('chapter_title') gets the text that matched one of the patterns
        chapter_markers.append({
            'start_index': match.start(),
            'end_index': match.end(),
            'title_text': match.group('chapter_title').strip()
        })

    # If no chapters are found, treat the whole text as one chapter
    if not chapter_markers:
        chapters.append({
            'title': "Full Text",
            'content': text_content.strip()
        })
        return chapters

    # Process content before the first chapter
    if chapter_markers[0]['start_index'] > 0:
        front_matter_content = text_content[0:chapter_markers[0]['start_index']].strip()
        if front_matter_content:
            chapters.append({
                'title': "Front Matter / Introduction",
                'content': front_matter_content
            })

    # Process the main chapters
    for i, marker in enumerate(chapter_markers):
        start_of_chapter_content = marker['end_index']
        end_of_chapter_content = None

        if i + 1 < len(chapter_markers):
            end_of_chapter_content = chapter_markers[i+1]['start_index']
        else:
            # Last chapter, goes to the end of the text
            end_of_chapter_content = len(text_content)

        chapter_content = text_content[start_of_chapter_content:end_of_chapter_content].strip()
        
        # Clean up common Project Gutenberg headers/footers that might sneak into chapter content
        chapter_content = re.sub(r'Project Gutenberg’s.*?\n', '', chapter_content, flags=re.IGNORECASE)
        chapter_content = re.sub(r'Ebook of.*?\n', '', chapter_content, flags=re.IGNORECASE)
        chapter_content = re.sub(r'[\s\S]*START OF THE PROJECT GUTENBERG EBOOK.*?\*\*\*[\s\S]*?\n', '', chapter_content, flags=re.IGNORECASE)
        chapter_content = re.sub(r'[\s\S]*\*\*\* END OF THE PROJECT GUTENBERG EBOOK.*', '', chapter_content, flags=re.IGNORECASE | re.DOTALL)


        if chapter_content: # Only add if there's actual content
            chapters.append({
                'title': marker['title_text'],
                'content': chapter_content
            })

    return chapters
