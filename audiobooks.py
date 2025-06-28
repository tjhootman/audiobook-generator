"""Main program for converting text files to audiobooks."""

import os
import re

from text_processing import get_user_book_url, download_book_content, get_book_title, parse_chapters
from text_processing import setup_output_directory, export_raw_text, clean_text, export_cleaned_text

# from speech_processing import create_audiobook_chapter

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

    if cleaned_book_content:
        if export_cleaned_text(cleaned_book_content, cleaned_file_path):
            print(f"Cleaned text exported to: {cleaned_file_path}")

            # # --- Chapter Parsing and Audiobook Generation Steps ---
            # print("\n--- Starting Chapter Parsing and Audiobook Generation ---")

            # # Read the cleaned text content for chapter parsing
            # # (assuming clean_text outputs content, otherwise re-read from cleaned_file_path)
            # # For simplicity, let's re-read the content from the cleaned file
            # try:
            #     with open(cleaned_file_path, "r", encoding="utf-8") as f:
            #         full_cleaned_text = f.read()
            # except Exception as e:
            #     print(f"Error reading cleaned text file: {e}")
            #     return

            # chapters_data = parse_chapters(full_cleaned_text)

            # if not chapters_data:
            #     print("No chapters identified. Converting entire cleaned text as a single 'Full Book' chapter.")
            #     chapters_data = [{
            #         'title': f"{book_title} (Full Book)",
            #         'content': full_cleaned_text
            #     }]

            # # Process each chapter
            # for i, chapter in enumerate(chapters_data):
            #     chapter_title_for_file = re.sub(r'[^\w\s-]', '', chapter['title']).replace(' ', '_')[:50] # Sanitize for filename
            #     chapter_output_filename_base = f"{book_title}_{chapter_title_for_file}"

            #     print(f"\nSynthesizing: {chapter['title']} (Chapter {i+1} of {len(chapters_data)})")

            #     # Temporarily save the chapter content to a file for `create_audiobook_chapter`
            #     # A more direct way would be to modify create_audiobook_chapter to accept content directly,
            #     # but sticking to the file-based approach for consistency with previous discussion.
            #     temp_chapter_filepath = os.path.join(output_directory, f"temp_chapter_{i+1}.txt")
            #     with open(temp_chapter_filepath, "w", encoding="utf-8") as f:
            #         f.write(chapter['content'])

            #     # Call create_audiobook_chapter for each identified chapter
            #     synthesized_audio_files = create_audiobook_chapter(
            #         input_filepath=temp_chapter_filepath,
            #         chapter_num=i + 1, # Use the loop index as chapter number
            #         max_chars_per_chunk=4800 # Google Cloud TTS limit
            #     )

            #     if synthesized_audio_files:
            #         print(f"Generated {len(synthesized_audio_files)} audio part(s) for '{chapter['title']}'.")
            #     else:
            #         print(f"Failed to generate audio for '{chapter['title']}'.")

            #     # Clean up temporary chapter file
            #     os.remove(temp_chapter_filepath)
            
            # print(f"\n--- Audiobook Generation Complete for '{book_title}' ---")
            # print("All chapter audio files are located in the './output/' directory.")

        else:
            print("Failed to export cleaned text. Skipping audiobook generation.")
    else:
        print("No cleaned content was generated. Skipping export and audiobook generation.")

if __name__ == "__main__":
    main()