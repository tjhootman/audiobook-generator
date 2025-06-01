import os
from processing import get_user_book_url, download_book_content, get_book_title
from processing import setup_output_directory, export_raw_text, clean_text, export_cleaned_text

def main():
    """
    Orchestrates the process of downloading, cleaning, and exporting book text.
    """
    output_directory = './output'
    setup_output_directory(output_directory)

    user_url = get_user_book_url()
    book_content = download_book_content(user_url)

    if not book_content:
        print("Book download failed. Exiting.")
        return

    book_title = get_book_title(book_content)
    if not book_title: # Handle cases where title extraction might fail
        print("Could not detect book title. Using a generic title.")
        book_title = "untitled_book"
    print(f"Detected Book Title: '{book_title}'")

    raw_file_path = export_raw_text(book_content, book_title, output_directory)
    if not raw_file_path:
        print("Failed to export raw text. Exiting.")
        return

    # Process the text
    # Note: clean_text ideally should take content directly or the path.
    # If it expects the path, then 'raw_file_path' is correct.
    # If it can take content, you might adjust `clean_text` in processing.py.
    cleaned_book_content = clean_text(raw_file_path)

    output_cleaned_path = os.path.join(output_directory, f"{book_title}_cleaned.txt")

    if cleaned_book_content:
        if export_cleaned_text(cleaned_book_content, output_cleaned_path):
            pass
            # Convert speech to text function to be added here
    else:
        print("No cleaned content was generated. Skipping export.")

if __name__ == "__main__":
    main()
