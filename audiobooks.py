import requests
from audiobook_processing import get_book_title, clean_text

# request the raw text of The Great Gatsby
r = requests.get(r'https://www.gutenberg.org/cache/epub/84/pg84.txt')
book_content = r.text

# Define your input file path
# input_book_path = 'my_book.txt'

# Locate the book title
book_title = get_book_title(book_content)
print(f"Detected Book Title: '{book_title}'")

# Write the raw content to a file
with open(f'{book_title}_raw.txt', 'w', encoding='utf-8') as f:
    f.write(book_content)

# Define input and output file paths based on the title
input_file_path = f"{book_title}_raw.txt"
output_cleaned_path = f"{book_title}_cleaned.txt"
output_audio_file_gtts = f"{book_title}_audio_gtts.mp3"

# Process the text
cleaned_book_content = clean_text(input_file_path)

# Export the processed text to the output file
if cleaned_book_content: # Only export if the processing was successful
    try:
        with open(output_cleaned_path, 'w', encoding='utf-8') as output_file:
            output_file.write(cleaned_book_content)
        print(f"Successfully exported cleaned text to '{output_cleaned_path}'")

        # Count characters and output
        character_count = len(cleaned_book_content)
        print(f"Character count (including spaces and newlines): {character_count}")

        # Convert to speech using gTTS
        # convert_text_to_speech_gtts(cleaned_book_content, output_audio_file_gtts, lang='en')

    except PermissionError:
        print(f"Error: Permission denied to write to file '{output_cleaned_path}'. "
              f"Check file permissions or target directory.")
    except IsADirectoryError:
        print(f"Error: '{output_cleaned_path}' is a directory. Cannot write to it as a file.")
    except UnicodeEncodeError as e:
        print(f"Error: Unable to encode text to UTF-8 for '{output_cleaned_path}'. "
              f"Details: {e}")
    except IOError as e:
        print(f"An I/O error occurred while writing to file '{output_cleaned_path}': {e}")
    except Exception as e:
        print(f"An unexpected error occurred during export: {e}")

# Read and print the cleaned content to verify (optional)
# with open(output_cleaned_path, 'r', encoding='utf-8') as f:
#     print("\n--- Cleaned Content ---")
#     print(f.read())
