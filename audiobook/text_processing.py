"""
Module containing functions for text file cleaning, exporting, and preparing
text for Text-to-Speech (TTS) conversion. This includes downloading content,
extracting metadata, sanitizing text, and chunking it into manageable sizes.
"""
from abc import ABC, abstractmethod
from typing import Optional, List
import os
import re
import requests
import nltk

# --- Abstractions ---

class TextSource(ABC):
    @abstractmethod
    def get_text(self) -> Optional[str]:
        pass

class TextCleaner(ABC):
    @abstractmethod
    def clean(self, text: str, **kwargs) -> str:
        pass

class TextExporter(ABC):
    @abstractmethod
    def export(self, content: str, destination: str) -> bool:
        pass

class TextChunker(ABC):
    @abstractmethod
    def chunk(self, text: str, max_chars_per_chunk: int = 4800) -> List[str]:
        pass

# --- Concrete Implementations ---

class GutenbergSource(TextSource):
    def __init__(self, url: str):
        self.url = url

    def get_text(self) -> Optional[str]:
        print(f"Attempting to download from: {self.url}")
        try: 
            r = requests.get(self.url)
            r.raise_for_status()
            return r.text
        except requests.exceptions.RequestException as e:
            print(f"Error fetching URL: {e}")
            print("Please ensure the URL is correct and accesible.")
            return None
 
class LocalFileSource(TextSource):
    def __init__(self, filepath: str):
        self.filepath = filepath

    def get_text(self) -> Optional[str]:
        if not os.path.exists(self.filepath):
            print(f"Error: File not found at {self.filepath}")
            return None
        try: 
            with open(self.filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading file {self.filepath}: {e}")
            return None
       
class GutenbergCleaner(TextCleaner):
    def clean(self, text: str, raw_title: str="", file_path: Optional[str] = None) -> str:
        start_marker = f"*** START OF THE PROJECT GUTENBERG EBOOK {raw_title.upper()} ***"
        end_marker = f"*** END OF THE PROJECT GUTENBERG EBOOK {raw_title.upper()} ***"

        start_index = text.find(start_marker)
        if start_index != -1:
            end_of_start_marker_line = text.find('\n', start_index + len(start_marker))
            if end_of_start_marker_line != -1:
                text = text[end_of_start_marker_line + 1:].lstrip()
            else:
                text = text[start_index + len(start_marker):].lstrip()
        else:
            print(f"Warning: The start marker '{start_marker}' was not found in '{file_path or '[raw text]'}'.")

        end_index = text.find(end_marker)
        if end_index != -1:
            text = text[:end_index].rstrip()
        else:
            print(f"Warning: The end marker '{end_marker}' was not found in '{file_path or '[raw text]'}'.")

        text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
        text = re.sub(r'\n\s*\n+', 'PARAGRAPH_BREAK_PLACEHOLDER', text)
        text = re.sub(r'\s*\n\s*', ' ', text)
        text = text.replace('PARAGRAPH_BREAK_PLACEHOLDER', '\n\n')
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
        
class DefaultTextChunker(TextChunker):
    def chunk(self, text: str, max_chars_per_chunk: int = 4800) -> List[str]:
        # Ensure NLTK punkt is available before tokenizing
        ensure_nltk_resource('tokenizers/punkt')
        chunks = []
        paragraphs = text.split('\n\n')
        current_chunk = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(current_chunk) + len(para) + 2 > max_chars_per_chunk and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            if len(para) > max_chars_per_chunk:
                sentences = nltk.sent_tokenize(para)
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


# --- NLTK resource helper ---

def ensure_nltk_resource(resource: str, download_if_missing: bool = True, quiet: bool = True):
    """
    Checks if the given NLTK resource is available, and downloads it if missing.

    Args:
        resource (str): The resource path, e.g. 'tokenizers/punkt'
        download_if_missing (bool): Whether to download if missing.
        quiet (bool): Whether to suppress download output.
    """
    try:
        nltk.data.find(resource)
    except LookupError:
        if download_if_missing:
            print(f"NLTK resource '{resource}' not found. Downloading...")
            nltk.download(resource.split('/')[-1], quiet=quiet)


# --- Utility Functions ---

def setup_output_directory(directory_path: str):
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


# --- Example Pipeline ---

class AudiobookTextPipeline:
    """
    High-level pipeline coordinating downloading, cleaning, exporting, and chunking.
    Depends only on abstractions.
    """
    def __init__(
        self,
        source: TextSource,
        cleaner: TextCleaner,
        exporter: TextExporter,
        chunker: TextChunker
    ):
        self.source = source
        self.cleaner = cleaner
        self.exporter = exporter
        self.chunker = chunker

    def process(self, raw_title: str, raw_output_path: str, clean_output_path: str, chunk_size: int = 4800):
        raw_text = self.source.get_text()
        if not raw_text:
            print("No text available from source.")
            return None, []

        # Export raw text
        self.exporter.export(raw_text, raw_output_path)

        # Clean text
        cleaned_text = self.cleaner.clean(raw_text, raw_title=raw_title)
        self.exporter.export(cleaned_text, clean_output_path)

        # Chunk text
        chunks = self.chunker.chunk(cleaned_text, max_chars_per_chunk=chunk_size)
        print(f"Chunked into {len(chunks)} pieces for TTS.")

        return cleaned_text, chunks