"""
Module containing functions for text file cleaning, exporting, and preparing
text for Text-to-Speech (TTS) conversion. This includes downloading content,
extracting metadata, and sanitizing text.
"""
from abc import ABC, abstractmethod
from typing import Optional
import logging
import os
import re
import requests
import urllib.parse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# --- Abstractions ---

class TextSource(ABC):
    @abstractmethod
    def get_text(self) -> Optional[str]:
        pass

class TextCleaner(ABC):
    @abstractmethod
    def clean(self, text: str) -> str:
        pass

class TextExporter(ABC):
    @abstractmethod
    def export(self, content: str, destination: str) -> bool:
        pass

# --- Implementation Classes ---

class GutenbergSource(TextSource):
    """A TextSource implementation for downloading raw text files from Project Gutenberg.

    Args:
        url (str): The URL for the Project Gutenberg raw text file.
    """
    def __init__(self, url: str):
        # Proactively validate the URL format
        parsed_url = urllib.parse.urlparse(url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            logging.error("Invalid URL format: %s", url)
            raise ValueError("Invalid URL format. Must be a complete URL with scheme and netloc.")
        self.url = url

    def get_text(self) -> Optional[str]:
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
    """A TextSource implementation for reading text from a local file path.

    Args:
        filepath (str): The local file path to read from.
        encoding (str, optional): The character encoding of the file. Defaults to 'utf-8'.
    """
    def __init__(self, filepath: str, encoding: str = 'utf-8'):
        # Normalize the path in the constructor to ensure consistency
        self.filepath = os.path.normpath(os.path.abspath(filepath))
        self.encoding = encoding

    def get_text(self) -> Optional[str]:
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
    standardizing formatting for Text-to-Speech conversion.

    Args:
        text (str): Project Gutenberg text
        raw_title (str): Raw book title
    """
    def clean(self, text: str, raw_title: str="") -> str:
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
        text = re.sub(r' {2,}', ' ', text).strip()

        return text

class FileTextExporter(TextExporter):
    def export(self, content: str, destination: str) -> bool:
        if not content:
            print("Warning: No cleaned content to export.")
            return False
        try:
            output_dir = os.path.dirname(destination)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(destination, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Successfully exported text to '{destination}'")
            return True
        except Exception as e:
            print(f"Error in exporting text: {e}")
            return False

# --- Utility Functions ---

def setup_output_directory(directory_path: str):
    print("Setting up output directory...")
    os.makedirs(directory_path, exist_ok=True)
    print(f"Output directory '{directory_path}' ensured.")

def get_user_book_url() -> str:
    while True:
        user_url = input("Please enter the Project Gutenberg URL for the raw text of the book (e.g., https://www.gutenberg.org/cache/epub/76/pg76.txt): ")
        if user_url.strip():
            if user_url.startswith("http://www.gutenberg.org") or user_url.startswith("https://www.gutenberg.org"):
                return user_url
            else:
                print("Invalid URL format. Please enter a Project Gutenberg URL.")
        else:
            print("URL cannot be empty. Please try again.")

def get_user_local_file() -> str:
    local_file_path = input("Enter the path to your local TXT file: ")
    try:
        return local_file_path
    except FileNotFoundError:
        print(f"Error: File not found at {local_file_path}. Exiting.")
        return
    except Exception as e:
        print(f"Error reading local file: {e}. Exiting.")
        return

def get_book_title(text_content: str) -> tuple[str, str]:
    default_title = "unknown_book"
    lines = text_content.splitlines()
    for i, line in enumerate(lines[:20]):
        match = re.match(r'Title:\s*(.*)', line.strip(), re.IGNORECASE)
        if match:
            raw_title = match.group(1).strip()
            if not raw_title:
                return (default_title, default_title)
            sanitized_title = re.sub(r'[\\/:*?"<>|,;]', '', raw_title)
            sanitized_title = re.sub(r'\s+', '_', sanitized_title)
            sanitized_title = sanitized_title.strip('._')
            return (raw_title, sanitized_title if sanitized_title else default_title)
    return (default_title, default_title)

def get_book_author(text_content: str) -> str:
    default_author = "unknown_author" 
    lines = text_content.splitlines()
    for i, line in enumerate(lines[:20]):
        match = re.match(r'Author:\s*(.*)', line.strip(), re.IGNORECASE)
        if match:
            raw_author = match.group(1).strip()
            return raw_author if raw_author else default_author
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
