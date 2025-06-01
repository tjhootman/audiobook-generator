import os
import requests
from processing import get_book_title, clean_text, export_cleaned_text

# User Input for the URL
while True:
    user_url = input("Please enter the Project Gutenberg URL for the raw text of the book (e.g., https://www.gutenberg.org/cache/epub/76/pg76.txt): ")
    if user_url.strip(): # Check if the input is not empty
        break
    else:
        print("URL cannot be empty. Please try again.")

print(f"Attempting to download from: {user_url}")

# Request the raw text of the book
try:
    r = requests.get(user_url)
    r.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
    book_content = r.text
except requests.exceptions.RequestException as e:
    print(f"Error fetching URL: {e}")
    print("Please ensure the URL is correct and accessible.")
    exit() # Exit the script if there's an error downloading the content

# Define the output directory
output_directory = './output'

# Create the output directory if it doesn't exist
os.makedirs(output_directory, exist_ok=True)

# Locate the book title
book_title = get_book_title(book_content)
print(f"Detected Book Title: '{book_title}'")

# Write the raw content to a file
with open(f'{output_directory}/{book_title}_raw.txt', 'w', encoding='utf-8') as f:
    f.write(book_content)
    output_raw_path = f"{output_directory}/{book_title}_raw"
    print(f"Successfully exported raw text to '{output_raw_path}'")

# Define input and output file paths based on the title
input_file_path = f"{output_raw_path}.txt"
output_cleaned_path = f"{output_directory}/{book_title}_cleaned.txt"
output_audio_file_gtts = f"{output_directory}/{book_title}_audio_gtts.mp3"

# Process the text
cleaned_book_content = clean_text(input_file_path)

if cleaned_book_content:
    if export_cleaned_text(cleaned_book_content, output_cleaned_path):
        # The character count is now handled inside the function,
        # so we don't need to print it separately here.
        pass # No need for the separate print statement for character count here

        # Convert to speech using gTTS (uncomment when ready and gTTS is installed)
        # from gtts import gTTS
        # def convert_text_to_speech_gtts(text, output_file, lang='en'):
        #     try:
        #         tts = gTTS(text=text, lang=lang, slow=False)
        #         tts.save(output_file)
        #         print(f"Successfully converted text to speech: '{output_file}'")
        #     except Exception as e:
        #         print(f"Error converting text to speech: {e}")
        # # Note: If converting to speech, you might want to pass only the 'cleaned_book_content'
        # # and not the 'content_to_write' which includes the character count line.
        # # convert_text_to_speech_gtts(cleaned_book_content, output_audio_file_gtts, lang='en')
else:
    print("No cleaned content was generated. Skipping export.")

# Read and print the cleaned content to verify (optional)
# with open(output_cleaned_path, 'r', encoding='utf-8') as f:
#     print("\n--- Cleaned Content ---")
#     print(f.read())