"""Main program for converting audiobook mp3 to video."""
import os
from pydub import AudioSegment

from text_processing import get_book_title, get_book_author

from video_processing import create_video

from image_generation import create_cover_image

def main():
    """
    Orchestrates the process of generating video for audiobook and uploading to YouTube.
    """

    output_directory = ""

    book_content = ""

    # 1. Locates the "Title: " line in a string and extracts the book title.
    raw_book_title, book_title = get_book_title(book_content)
  
    if not book_title: # Handle cases where title extraction might fail
        print("Could not detect book title. Using a generic title.")
        book_title = "untitled_book"
    print(f"Detected Book Title: '{raw_book_title}'")

    # 2. Locates the "Author: " line in a string and extracts the book author.
    book_author = get_book_author(book_content)
    if not book_author: # Handle cases where author extraction might fail
        print("Could not detect book author. Using 'Unknown Author'.")
    print(f"Detected Book Author: '{book_author}'")

    # 3. Create cover image.
    prompt = f"Generate a cover image for {book_author}'s '{raw_book_title}' audiobook"
    output_filename = f"{book_title}.png"

    create_cover_image(prompt, output_directory, output_filename)

    # 4. Generate video of audiobook image and audio.
    image_path = os.path.join(output_directory, f"{book_title}.png")
    dummy_image_path = "./assets/narrated_classics.png"
    if not os.path.exists(image_path):
        image_path = dummy_image_path
        print(f"Using dummy image: {dummy_image_path}")
   
    audio_path = os.path.join(output_directory, f"{book_title}_audiobook.mp3")
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
    output_video = os.path.join(output_directory, f"{book_title}_audiobook.mp4")

    create_video(my_image, my_audio, output_video, "./assets/narrated_classics_intro.mp4")

if __name__ == "__main__":
    main()
