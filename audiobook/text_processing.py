"""
Module containing functions for text file cleaning, exporting, and preparing
text for Text-to-Speech (TTS) conversion. This includes downloading content,
extracting metadata, and sanitizing text.
"""
from abc import ABC, abstractmethod
from typing import Optional
import logging
import urllib.parse
import os
import re
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# --- Abstractions ---

class TextSource(ABC):
    """Abstract base class for all text sources."""
    @abstractmethod
    def get_text(self) -> Optional[str]:
        """
        Retrieves text content from a source.

        Returns:
            Optional[str]: The text content as a string, or None if retrieval fails.
        """
        pass

class TextCleaner(ABC):
    """
    Abstract base class for all text cleaning implementations.
    The method signature is flexible to accommodate different cleaning needs.
    """
    @abstractmethod
    def clean(self, text: str, **kwargs) -> str:
        """
        Sanitizes and formats a given text string.

        Args:
            text (str): The raw text content to be cleaned.
            **kwargs: Flexible keyword arguments for specific cleaner implementations.

        Returns:
            str: The cleaned and sanitized text.
        """
        pass

class TextExporter(ABC):
    """Abstract base class for all text exporters."""
    @abstractmethod
    def export(self, content: str, destination: str) -> bool:
        """
        Exports text content to a specified destination.

        Args:
            content (str): The text content to be exported.
            destination (str): The target location for the export.

        Returns:
            bool: True if the export was successful, False otherwise.
        """
        pass

# --- Implementation Classes ---

class GutenbergSource(TextSource):
    """A TextSource implementation for downloading raw text files from Project Gutenberg."""

    def __init__(self, url: str):
        """
        Initializes the GutenbergSource with a URL and validates its format.

        Args:
            url (str): The URL for the Project Gutenberg raw text file.
        """
        # Proactively validate the URL format
        parsed_url = urllib.parse.urlparse(url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            logging.error("Invalid URL format: %s", url)
            raise ValueError("Invalid URL format. Must be a complete URL with scheme and netloc.")
        self.url = url

    def get_text(self) -> Optional[str]:
        """
        Downloads text content from the specified URL.

        Returns:
            Optional[str]: The text content if the download is successful, None otherwise.
        """
        logging.info("Attempting to download from: %s", self.url)

        # Define a timeout for the request and a user-agent header
        headers = {'User-Agent': 'Mozilla/5.0'}
        timeout = 30 #seconds

        try:
            r = requests.get(self.url, headers=headers, timeout=timeout)
            r.raise_for_status() # This will raise an HTTPError for bad status codes

            # Verify the response content type is text
            content_type =  r.headers.get('Content-Type', '').split(';')[0]
            if not content_type.startswith('text/'):
                logging.error("Expected a text file, but received Content-Type: %s", content_type)
                return None

            logging.info("Download successful")
            return r.text
        except requests.exceptions.HTTPError as e:
            logging.error("HTTP error occurred: %s", e)
            logging.error("Please ensure the URL is correct and points to a valid file.")
            return None
        except requests.exceptions.ConnectionError as e:
            logging.error("Connection error occurred: %s", e)
            logging.error("Please check your network connection.")
            return None
        except requests.exceptions.Timeout as e:
            logging.error("Request timed out after %d seconds: %s", timeout, e)
            logging.error("The server may be too slow or unresponsive. Please try again later.")
            return None
        except requests.exceptions.RequestException as e:
            # Catch any other requests-related exceptions
            logging.error("An unexpected error occurred during the request: %s", e)
            return None
        except ValueError as e:
            # Catch the ValieError from the constructor
            logging.error("Failed to initialize GutenbergSource due to: %s", e)
            return None

class LocalFileSource(TextSource):
    """A TextSource implementation for reading text from a local file path."""

    def __init__(self, filepath: str, encoding: str = 'utf-8'):
        """
        Initializes the LocalFileSource with a file path and encoding.

        Args:
            filepath (str): The local file path to read from.
            encoding (str, optional): The character encoding of the file. Defaults to 'utf-8'.
        """
        # Normalize the path in the constructor to ensure consistency
        self.filepath = os.path.normpath(os.path.abspath(filepath))
        self.encoding = encoding

    def get_text(self) -> Optional[str]:
        """
        Reads text content from the specified local file.

        Returns:
            Optional[str]: The text content if the file is read successfully, None otherwise.
        """
        logging.info("Attempting to read file from: %s", self.filepath)

        # Proactively check if the path points to a file
        if not os.path.isfile(self.filepath):
            logging.error("Error: Path is not a file or does not exist at %s", self.filepath)
            return None

        try:
            with open(self.filepath, 'r', encoding=self.encoding) as f:
                content = f.read()
                logging.info("File read successfully.")
                return content
        except PermissionError as e:
            logging.error("Permission denied when trying to read file %s: %s", self.filepath, e)
            return None
        except UnicodeDecodeError as e:
            logging.error("Error decoding file %s with encoding '%s': %s", self.filepath, self.encoding, e)
            return None
        except IOError as e:
            logging.error("Error reading file %s: %s", self.filepath, e)
            return None
        except Exception as e:
            # A final, general catch-all for unexpected issues
            logging.error("An unexpected error occurred while reading file %s: %s", self.filepath, e)
            return None
   
class GutenbergCleaner(TextCleaner):
    """Cleans text from Project Gutenberg, removing headers, footers, and
    standardizing formatting for Text-to-Speech conversion."""

    def clean(self, text: str, raw_title: str="") -> str:
        """
        Performs a two-step cleaning process on the Project Gutenberg text.

        Args:
            text (str): The raw text content from Project Gutenberg.
            raw_title (str, optional): The raw book title, used as a fallback for finding markers.
                                       Defaults to "".

        Returns:
            str: The cleaned and sanitized text content.
        """
        # --- Header/Footer Cleaning Logic ---
        start_match = end_match = None

        # Primary Logic: Find markers using a generic regex
        header_pattern = r"^\*\*\* START OF THE PROJECT GUTENBERG EBOOK.*?\*\*\*$"
        footer_pattern = r"^\*\*\* END OF THE PROJECT GUTENBERG EBOOK.*?\*\*\*$"
        start_match = re.search(header_pattern, text, flags=re.MULTILINE | re.IGNORECASE | re.DOTALL)
        end_match = re.search(footer_pattern, text, flags=re.MULTILINE | re.IGNORECASE | re.DOTALL)

        if start_match and end_match:
            logging.info("Found generic start and end markers. Slicing text.")
            start_index = start_match.end()
            end_index = end_match.start()
            text = text[start_index:end_index].strip()

        # Fallback Logic: Try a title-specific search if the generic one fails ---
        elif raw_title:
            logging.warning("Generic markers not found. Attempting title-specific fallback.")
            
            # Create title-specific patterns, escaping special characters in the title
            title_start_pattern = re.escape(f"*** START OF THE PROJECT GUTENBERG EBOOK {raw_title.upper()}") + ".*?\n"
            title_end_pattern = re.escape(f"*** END OF THE PROJECT GUTENBERG EBOOK {raw_title.upper()}")
            
            title_start_match = re.search(title_start_pattern, text, flags=re.IGNORECASE | re.DOTALL)
            title_end_match = re.search(title_end_pattern, text, flags=re.IGNORECASE | re.DOTALL)

            if title_start_match and title_end_match:
                logging.info("Fallback successful. Found title-specific markers. Slicing text.")
                start_index = title_start_match.end()
                end_index = title_end_match.start()
                text = text[start_index:end_index].strip()
            else:
                logging.warning("Failed to find title-specific markers. Proceeding with un-sliced text.")
        
        else:
            logging.warning("No markers found. Proceeding with un-sliced text.")

        # --- Core Cleaning Logic ---
        # Fix hyphenated words broken across line breaks
        text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)

        # Replace multiple newlines with a paragraph break (two newlines)
        # and replace single newlines with a space.
        def replace_newlines(match):
            newlines = match.group(0)
            if newlines.count('\n') > 1:
                return '\n\n'
            else:
                return ' '
        
        text = re.sub(r'\s*\n\s*', replace_newlines, text)

        # Additional cleanup
        text = text.replace('_', ' ')
        text = text.replace('*', '')
        text = re.sub(r' {2,}', ' ', text).strip()

        return text

class NoOpCleaner(TextCleaner):
    """
    A TextCleaner implementation that returns the text unchanged.
    This is used for local files that are assumed to be already clean.
    """
    def clean(self, text: str, **kwargs) -> str:
        return text

class FileTextExporter(TextExporter):
    """Exports text content to a file, handling directory creation and I/O errors."""
    def export(self, content: str, destination: str) -> bool:
        """
        Exports text content to a specified file.

        Args:
            content (str): The text content to be exported.
            destination (str): The full path to the output file.

        Returns:
            bool: True if the export was successful, False otherwise.
        """
        if not content:
            logging.warning("No cleaned content to export.")
            return False
        try:
            output_dir = os.path.dirname(destination)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(destination, 'w', encoding='utf-8') as f:
                f.write(content)
            logging.info("Successfully exported text to %s", destination)
            return True
        except PermissionError as e:
            logging.error("Permission denied when writing to file %s: %s", destination, e)
            return False
        except IOError as e:
            logging.error("An I/O error occurred while writing to file %s: %s", destination, e)
            return False
        except Exception as e:
            # A final, general catch-all for unexpected issues
            logging.error("An unexpected error occurred in exporting text: %s", e)
            return False

# --- Utility Functions ---

def setup_output_directory(directory_path: str):
    """
    Ensures that the specified output directory exists, creating it if necessary.

    Args:
        directory_path (str): The path to the directory to be created.
    """
    logging.info("Setting up output directory...")
    try:
        os.makedirs(directory_path, exist_ok=True)
        logging.info("Output directory '%s' ensured.", directory_path)
    except PermissionError as e:
        logging.error("Permission denied when creating directory '%s': %s", directory_path, e)
    except Exception as e:
        logging.error("An unexpected error occurred while creating directory '%s': %s", directory_path, e)

def get_user_book_url() -> str:
    """
    Prompts the user for a Project Gutenberg URL and validates its format.

    The function continuously prompts the user until a valid URL is provided.
    The user can type 'q' or 'quit' to exit the function.

    Returns:
        Optional[str]: The validated URL provided by the user, or None if the user quits.
    """

    while True:
        user_url = input(
            "Please enter the Project Gutenberg URL for the raw text of the book "
            "(e.g., https://www.gutenberg.org/cache/epub/76/pg76.txt) or 'q' to quit: ").strip()
        
        if user_url.lower() in ['q', 'quit']:
            return None
        
        if not user_url:
            logging.warning('URL cannot be empty. Please try again.')
            continue

        try:
            parsed_url = urllib.parse.urlparse(user_url)

            # Check for a valid scheme, domain, and a .txt file extension in the path
            is_valid_gutenberg_url = (
                parsed_url.scheme in ['http', 'https'] and
                "gutenberg.org" in parsed_url.netloc and
                parsed_url.path.lower().endswith('.txt')
            )
            
            if is_valid_gutenberg_url:
                return user_url
            else:
                logging.warning("Invalid URL format. Please ensure it is a Project Gutenberg raw text (.txt) URL.")
        except Exception as e:
            logging.error("An unexpected error occurred during URL validation: %s", e)
            logging.warning("Please try entering the URL again.")

def get_user_local_file() -> str:
    """
    Prompts the user for a local file path and validates its existence and permissions.

    The function continuously prompts the user until a valid file path is provided.
    The user can type 'q' or 'quit' to exit the function.

    Returns:
        Optional[str]: The validated, absolute file path, or None if the user quits.
    """
    while True:
        local_file_path = input("Enter the path to your local TXT file or 'q' to quit: ").strip()

        if local_file_path.lower() in ['q', 'quit']:
            return None

        if not local_file_path:
            logging.warning("File path cannot be empty. Please try again.")
            continue

        # Get the absolute path for consistent validation and later use
        abs_path = os.path.abspath(local_file_path)

        # Proactive checks to ensure the path is a valid, readable file
        if not os.path.exists(abs_path):
            logging.warning("Error: File not found at '%s'. Please try again.", abs_path)
            continue

        if not os.path.isfile(abs_path):
            logging.warning("Error: Path '%s' is not a file. Please try again.", abs_path)
            continue
        
        if not os.access(abs_path, os.R_OK):
            logging.warning("Error: No read permissions for file '%s'. Please try again.", abs_path)
            continue

        # Check for a .txt extension (as before)
        if not abs_path.lower().endswith('.txt'):
            logging.warning(
                "Warning: The file '%s' does not have a .txt extension. "
                "This may cause unexpected behavior.", abs_path
            )

        # If all checks pass, return the validated absolute path
        return abs_path

def get_book_title(text_content: str, limit: int = 20) -> tuple[str, str]:
    """
    Extracts the raw and sanitized book title from text metadata.

    The function searches the first `limit` lines of the text for a line starting with "Title:".
    The sanitized title is suitable for use as a filename.

    Args:
        text_content (str): The full text content of the book.
        limit (int, optional): The maximum number of lines to search for the title. Defaults to 20.

    Returns:
        tuple[str, str]: A tuple containing the raw title and the sanitized title.
                         Returns ("unknown_book", "unknown_book") if no title is found.
    """
    default_title = "unknown_book"
    lines = text_content.splitlines()

    for line in lines[:limit]:
        match = re.match(r'Title:\s*(.*)', line.strip(), re.IGNORECASE)
        if match:
            raw_title = match.group(1).strip()

            if not raw_title:
                return (default_title, default_title)

            # Sanitize the title for use as a filename
            # This regex replaces illegal filename characters and whitespace with underscores
            sanitized_title = re.sub(r'[\\/:*?"<>|,;]', '', raw_title)
            sanitized_title = re.sub(r'\s+', '_', sanitized_title)
            sanitized_title = sanitized_title.strip('._')

            return (raw_title, sanitized_title if sanitized_title else default_title)
    return (default_title, default_title)

def get_book_author(text_content: str, limit: int = 20) -> str:
    """
    Extracts the author's name from text metadata.

    The function searches the first `limit` lines of the text for a line starting with "Author:".

    Args:
        text_content (str): The full text content of the book.
        limit (int, optional): The maximum number of lines to search for the author.
                               Defaults to 20.

    Returns:
        str: The raw author's name. Returns "unknown_author" if no author is found.
    """
    default_author = "unknown_author" 
    lines = text_content.splitlines()

    for line in lines[:limit]:
        match = re.match(r'Author:\s*(.*)', line.strip(), re.IGNORECASE)
        if match:
            raw_author = match.group(1).strip()
            return raw_author or default_author

    return default_author


# --- High-level Service ---

class TextProcessingService:
    """
    High-level service class for end-to-end text file processing:
    - Downloads or loads text (via TextSource)
    - Cleans text (via TextCleaner)
    - Exports raw and cleaned text (via TextExporter)
    - Extracts metata (title, author)
    """

    def __init__(
        self,
        source,
        cleaner,
        exporter,
    ):
        self.source = source
        self.cleaner = cleaner
        self.exporter = exporter

    def process_text(
        self,
        raw_output_path: str,
        clean_output_path: str,
    ) -> Optional[dict]:
        """
        Orchestrates the full text processing pipeline.

        Args:
            raw_output_path (str): Output path for raw text export.
            clean_output_path (str): Output path for cleaned text export.

        Returns:
            dict: {
                "raw_title": ...,
                "sanitized_title": ...,
                "author": ...,
                "raw_text": ...,
                "cleaned_text": ...,
            }
        """
        raw_text = self.source.get_text()
        if not raw_text:
            print("No text available from source.")
            return None

        # 1. Extract metadata before cleaning
        raw_title, sanitized_title = get_book_title(raw_text)
        author = get_book_author(raw_text)

        logging.info("Detected Title: %s", raw_title)
        logging.info("Detected Author: %s", author)
        logging.info("Sanitized Title for filename: %s", sanitized_title)

        # 2. Export raw text (using the sanitized title for the filename)
        raw_export_path = os.path.join(os.path.dirname(raw_output_path), f"{sanitized_title}_raw.txt")
        self.exporter.export(raw_text, raw_export_path)

        # 3. Clean the text using extracted raw title
        cleaned_text = self.cleaner.clean(raw_text, raw_title=raw_title)

        # 4. Export the cleaned text (using the sanitized title for the filename)
        clean_export_path = os.path.join(os.path.dirname(clean_output_path), f"{sanitized_title}_cleaned.txt")
        self.exporter.export(cleaned_text, clean_export_path)

        return {
            "raw_title": raw_title,
            "sanitized_title": sanitized_title,
            "author": author,
            "raw_text": raw_text,
            "cleaned_text": cleaned_text,
        }
