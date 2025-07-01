"""Main program for converting text files to audiobooks."""

import os

from text_processing import get_user_book_url, download_book_content, get_book_title
from text_processing import setup_output_directory, export_raw_text, clean_text

from audio_processing import generate_full_audiobook

from video_processing import create_video

# For dummy file creation (if you're using it), you might need these
try:
    from pydub import AudioSegment
except ImportError:
    print("Pillow or Pydub not installed. Install with: pip install Pillow pydub")
    print("You'll need to provide your own dummy files or install these libraries.")

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

    # 9. Generate video of audiobook image and audio.
    image_path = f"{book_title}.png"
    dummy_image_path = "timeless_tales.png"
    if not os.path.exists(image_path):
        image_path = dummy_image_path
        print(f"Using dummy image: {dummy_image_path}")
        
    audio_path = os.path.join(output_directory, f"{book_title}_full_audiobook.mp3")
    dummy_audio_path = "./output/dummy_audiobook.mp3"
    if not os.path.exists(audio_path):
        try:
            # Create a 5-second silent audio segment
            silent_audio = AudioSegment.silent(duration=5000)
            silent_audio.export(dummy_audio_path, format="mp3")
            audio_path = dummy_audio_path
            print(f"Created dummy audio: {dummy_audio_path}")
        except NameError: # pydub.AudioSegment not imported
            print("Pydub not installed. Cannot create dummy audio. Please install it: pip install pydub")
            print("Or provide your own 'dummy_audio.mp3'.")
            exit()
        except Exception as e:
            print(f"Error creating dummy audio: {e}. Make sure ffmpeg is installed and in your PATH.")
            exit()

    my_image = image_path
    my_audio = audio_path
    output_video = f"{book_title}_audiobook.mp4" # need to correct this to proper output location

    create_video(my_image, my_audio, output_video)

if __name__ == "__main__":
    main()
