"""Main program for converting text files to audiobooks."""

import os

from text_processing import get_user_book_url, download_book_content, get_book_title
from text_processing import setup_output_directory, export_raw_text, clean_text

from speech_processing import generate_full_audiobook

def main():
    """
    Orchestrates the process of downloading, cleaning, and converting book text to an audiobook.
    """
    # 1. Creates the specified output directory if it doesn't exist.
    output_directory = './output'
    setup_output_directory(output_directory)

    # 2. Prompts the user for a Project Gutenberg URL and validates it.
    user_url = get_user_book_url()

    # 3. Downloads the raw text content of a book from the given URL.
    book_content = download_book_content(user_url)

    if not book_content:
        print("Book download failed. Exiting.")
        return

    # 4. Locates the "Title: " line in a string and extracts the book title.
    raw_book_title, book_title = get_book_title(book_content)
    # book_title = get_book_title(book_content)
    if not book_title: # Handle cases where title extraction might fail
        print("Could not detect book title. Using a generic title.")
        book_title = "untitled_book"
    print(f"Detected Book Title: '{book_title}'")

    # 5. Exports the raw book content to a file.
    raw_file_path = export_raw_text(book_content, book_title, output_directory)
    if not raw_file_path:
        print("Failed to export raw text. Exiting.")
        return

    # 6. Reads a text file, removes mid-sentence line breaks, and preserves
    # paragraph breaks (indicated by two or more newlines).
    cleaned_book_content = clean_text(raw_file_path, raw_book_title)

    # 7. Exports the cleaned text content to a specified file path.
    # We will use this cleaned file for the text-to-speech conversion.
    cleaned_file_path = os.path.join(output_directory, f"{book_title}_cleaned.txt")

    # 8. Generate full audiobook from chunked files. 
    generate_full_audiobook(book_title, cleaned_book_content, cleaned_file_path, output_directory)

if __name__ == "__main__":
    main()
