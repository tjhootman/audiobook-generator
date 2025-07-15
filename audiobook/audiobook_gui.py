"""
GUI application for converting Project Gutenberg text books into audiobooks.
The long-running audiobook generation process is handled in a separate thread to ensure
the GUI remains responsive during execution.
"""

import tkinter as tk
from tkinter import messagebox
import os
import threading
import sys
from google.cloud import texttospeech
from pydub import AudioSegment # For audio combination

try:
    import subprocess
except ImportError:
    # This block handles cases where the 'subprocess' module might not be available,
    # which can happen in highly restricted environments, although it's part of Python's standard library.
    # It prints a warning and sets subprocess to None, disabling the folder opening feature on those platforms.
    print("Warning: 'subprocess' module not available. Folder opening might not work on macOS/Linux.")
    subprocess = None # Set to None if import fails

# Import custom modules containing core logic for audiobook generation.
# These modules should be located in the same directory as this GUI application script.
from audio_analysis import (
    get_available_tts_voices,       # Fetches and caches available TTS voices from Google Cloud.
    analyze_language,               # Detects the language of the input text.
    analyze_sentiment,              # Analyzes the emotional tone of the text.
    analyze_category,               # Classifies the text into predefined content categories.
    analyze_syntax_complexity,      # Analyzes the grammatical complexity of sentences.
    analyze_regional_context,       # Detects regional variations in English (e.g., US vs. GB).
    synthesize_text_to_speech,      # Converts text chunks to speech using Google Cloud TTS.
    get_contextual_voice_parameters # Selects TTS voice parameters based on text analysis.
)
from text_processing import (
    setup_output_directory,     # Creates and ensures the existence of output directories.
    download_book_content,      # Downloads raw text content from a Project Gutenberg URL.
    get_book_title,             # Extracts the book title from raw text and sanitizes it for file paths.
    get_book_author,            # Extracts the book author from raw text.
    export_raw_text,            # Saves the raw downloaded text to a file.
    clean_text,                 # Cleans boilerplate and formatting from the raw text.
    export_cleaned_text,        # Saves the cleaned text to a file.
    chunk_text_from_file        # Splits the cleaned text into smaller chunks for TTS API processing.
)

# --- Application-wide Configuration ---
# Base directory where all generated audiobook files will be stored.
OUTPUT_BASE_DIR = "audiobook_output_gui"
# Maximum number of characters per text chunk sent to the Text-to-Speech API.
# This adheres to API limits and optimizes synthesis.
MAX_CHARS_PER_TTS_CHUNK = 4800

# --- Global State Initialization ---
# This function is called once at application startup to fetch and cache
# the list of available Google Cloud TTS voices. This prevents repeated
# API calls and speeds up voice selection later.
print("Initializing available TTS voices for the application...")
get_available_tts_voices()
print("TTS voice initialization complete.")


class AudiobookApp:
    """
    Main class for the Audiobook Generator GUI application.

    Manages the Tkinter window, widgets, user interactions, and orchestrates
    the audiobook generation process by integrating with the `audio_analysis`
    and `text_processing` modules. The core generation logic runs in a
    separate thread to maintain GUI responsiveness.
    """
    def __init__(self, master):
        """
        Initializes the Tkinter application window and its widgets.

        Args:
            master (tk.Tk): The root Tkinter window.
        """
        self.master = master
        master.title("Project Gutenberg Audiobook Generator")
        master.geometry("600x550") # Sets the initial width and height of the window.
        master.resizable(False, False) # Prevents the user from resizing the window.

        # --- ADD ICON HERE ---
        try:
            # Set icon path. 
            # Assuming app_icon.png is in assets folder. Update to your appropriate file structure.
            icon_path = os.path.join("assets", "app_icon.png")
            if os.path.exists(icon_path):
                # Create a PhotoImage object
                self.app_icon = tk.PhotoImage(file=icon_path)
                # Set the window icon. True means it replaces default icons.
                master.iconphoto(True, self.app_icon)
            else:
                print(f"Warning: Icon file not found at {icon_path}")
        except Exception as e:
            print(f"Error setting application icon: {e}")
        # --- END ICON ADDITION ---


        # --- GUI Widgets Setup ---

        # 1. Title Label
        self.title_label = tk.Label(master, text="Generate Audiobook from Project Gutenberg", font=("Arial", 16, "bold"))
        self.title_label.pack(pady=15) # Adds padding above and below the label.

        # 2. URL Input Frame and Entry
        self.url_frame = tk.Frame(master)
        self.url_frame.pack(pady=5, fill="x", padx=20) # Packs with vertical padding, fills horizontally, with side padding.
        tk.Label(self.url_frame, text="Book URL:").pack(side="left", padx=(0, 10)) # Label for the URL input.
        self.url_entry = tk.Entry(self.url_frame, width=50) # Text entry widget for the URL.
        self.url_entry.insert(0, "https://www.gutenberg.org/cache/epub/76/pg76.txt") # Pre-fills with an example URL.
        self.url_entry.pack(side="left", expand=True, fill="x") # Makes entry expand to fill available space.

        # 3. Gender Preference Frame and OptionMenu
        self.gender_frame = tk.Frame(master)
        self.gender_frame.pack(pady=5, fill="x", padx=20)
        tk.Label(self.gender_frame, text="Narrator Gender:").pack(side="left", padx=(0, 10))
        self.gender_var = tk.StringVar(master) # Variable to hold the selected gender option.
        self.gender_var.set("Automatic") # Sets the default selected option.
        self.gender_options = ["Automatic", "Male", "Female", "Neutral"] # List of available gender choices.
        self.gender_menu = tk.OptionMenu(self.gender_frame, self.gender_var, *self.gender_options) # Dropdown menu.
        self.gender_menu.pack(side="left", expand=True, fill="x")

        # 4. Generate Button
        self.generate_button = tk.Button(master, text="Generate Audiobook", command=self.start_generation, font=("Arial", 12))
        self.generate_button.pack(pady=20) # Adds padding above and below.

        # 5. Status Display (Text Widget with Scrollbar)
        self.status_label_frame = tk.LabelFrame(master, text="Process Log", padx=5, pady=5) # Creates a framed section for the log.
        self.status_label_frame.pack(pady=10, padx=20, fill="both", expand=True) # Fills available space and expands.

        self.status_text = tk.Text(self.status_label_frame, height=15, wrap="word", state="disabled", font=("Courier New", 10))
        self.status_text.pack(side="left", fill="both", expand=True) # Text widget for displaying log messages.
        
        self.status_scrollbar = tk.Scrollbar(self.status_label_frame, command=self.status_text.yview) # Vertical scrollbar.
        self.status_scrollbar.pack(side="right", fill="y")
        self.status_text.config(yscrollcommand=self.status_scrollbar.set) # Connects text widget to scrollbar.

        # 6. Output Link/Button (Initially hidden until audiobook is generated)
        self.output_frame = tk.Frame(master)
        # self.output_frame.pack(pady=10) # This frame is initially not packed (hidden).

        self.output_label = tk.Label(self.output_frame, text="Audiobook Ready:", font=("Arial", 10))
        self.output_label.pack(side="left", padx=5)
        
        self.output_link_button = tk.Button(self.output_frame, text="Open Output Folder", command=self.open_output_folder, font=("Arial", 10, "underline"), fg="blue", cursor="hand2")
        self.output_link_button.pack(side="left", padx=5)
        
        # Attribute to store the full path to the generated audiobook file.
        self.current_audiobook_path = None

        # --- Initial Setup Actions ---
        # Redirect standard output (print statements) and standard error to the Tkinter Text widget.
        self.redirect_stdout_to_text_widget()
        # Display initial welcome messages in the log.
        self.log_message("Welcome to the Audiobook Generator!")
        self.log_message("Please enter a Project Gutenberg URL and click 'Generate'.")
        self.log_message("Ensure GOOGLE_APPLICATION_CREDENTIALS is set and FFmpeg is installed.")

    def log_message(self, message):
        """
        Appends a message to the status text widget and ensures the GUI updates.

        Args:
            message (str): The string message to append.
        """
        self.status_text.config(state="normal") # Temporarily enable the text widget for writing.
        self.status_text.insert(tk.END, message + "\n") # Insert message at the end.
        self.status_text.see(tk.END) # Scrolls the text widget to the end to show the latest message.
        self.status_text.config(state="disabled") # Disable the text widget to prevent user editing.
        self.master.update_idletasks() # Forces Tkinter to process pending events, updating the GUI immediately.

    def redirect_stdout_to_text_widget(self):
        """
        Redirects both `sys.stdout` and `sys.stderr` to route all print statements
        and error messages into the `status_text` Tkinter widget.
        This allows the user to see the progress and any warnings/errors directly in the GUI.
        """
        class StdoutRedirector:
            """A custom file-like object to redirect stdout/stderr to a Tkinter Text widget."""
            def __init__(self, text_widget_logger):
                """
                Initializes the redirector.
                Args:
                    text_widget_logger (callable): A method (e.g., self.log_message)
                                                   to which new output strings will be passed.
                """
                self.text_widget_logger = text_widget_logger
                self.stdout = sys.stdout # Keep a reference to the original stdout for console logging.

            def write(self, s):
                """Writes a string to the text widget and the original stdout."""
                if s.strip(): # Only process non-empty strings (e.g., ignore just newlines).
                    self.text_widget_logger(s.strip()) # Pass stripped string to log method.
                self.stdout.write(s) # Also write to the original console stdout.

            def flush(self):
                """Flushes the underlying stdout stream."""
                self.stdout.flush()

        sys.stdout = StdoutRedirector(self.log_message) # Redirect standard output.
        sys.stderr = StdoutRedirector(self.log_message) # Redirect standard error.

    def open_output_folder(self):
        """
        Opens the directory where the generated audiobook was saved.
        Uses platform-specific commands (os.startfile for Windows, subprocess.Popen for macOS/Linux).
        """
        if self.current_audiobook_path:
            folder_path = os.path.dirname(self.current_audiobook_path)
            if os.path.exists(folder_path):
                try:
                    if sys.platform == "win32":
                        os.startfile(folder_path)
                    elif sys.platform == "darwin": # macOS
                        # 'open' command opens files/directories/apps on macOS.
                        # subprocess is needed to run external commands.
                        subprocess.Popen(["open", folder_path])
                    else: # Linux (e.g., Ubuntu, Fedora with XDG)
                        # 'xdg-open' is a common utility to open files/directories
                        # with the default application on Linux desktop environments.
                        subprocess.Popen(["xdg-open", folder_path])
                except Exception as e:
                    messagebox.showerror("Error", f"Could not open folder: {e}")
            else:
                messagebox.showwarning("Warning", "Output folder does not exist. It might have been deleted.")
        else:
            messagebox.showinfo("Info", "No audiobook has been generated yet to open its folder.")


    def start_generation(self):
        """
        Initiates the audiobook generation process. This method is called when
        the "Generate Audiobook" button is clicked. It validates input and
        starts the `_run_audiobook_generation` method in a separate thread
        to keep the GUI responsive.
        """
        book_url = self.url_entry.get().strip()
        if not book_url:
            messagebox.showwarning("Input Error", "Please enter a Project Gutenberg URL.")
            return

        # Disable the generate button to prevent multiple simultaneous generations.
        self.generate_button.config(state="disabled", text="Generating...")
        self.output_frame.pack_forget() # Hide the previous output link if it was visible.
        self.current_audiobook_path = None # Reset the path for the new generation.
        self.log_message("\n--- Starting Audiobook Generation ---")
        self.log_message(f"Processing URL: {book_url}")

        # Create and start a new thread to run the generation logic.
        # This prevents the GUI from freezing during the potentially long-running process.
        generation_thread = threading.Thread(target=self._run_audiobook_generation, args=(book_url, self.gender_var.get()))
        generation_thread.start()

    def _run_audiobook_generation(self, book_url: str, gender_choice: str):
        """
        Contains the core audiobook generation logic, designed to be run
        in a separate thread. It integrates functions from `audio_analysis`
        and `text_processing` modules.

        Args:
            book_url (str): The URL of the Project Gutenberg book.
            gender_choice (str): The user's selected gender preference
                                 ("Automatic", "Male", "Female", "Neutral").
        """
        try:
            # Convert the string gender choice from the GUI to the
            # `google.cloud.texttospeech.SsmlVoiceGender` enum type.
            user_gender_preference = None
            if gender_choice == 'Male':
                user_gender_preference = texttospeech.SsmlVoiceGender.MALE
            elif gender_choice == 'Female':
                user_gender_preference = texttospeech.SsmlVoiceGender.FEMALE
            elif gender_choice == 'Neutral':
                user_gender_preference = texttospeech.SsmlVoiceGender.NEUTRAL
            # If 'Automatic', `user_gender_preference` remains None,
            # allowing `get_contextual_voice_parameters` to infer.

            # --- Integration with existing audiobook generation logic ---
            # This section directly calls functions from the imported modules,
            # providing robust steps for downloading, cleaning, analyzing,
            # synthesizing, and combining the audiobook.

            setup_output_directory(OUTPUT_BASE_DIR)

            raw_text_content = download_book_content(book_url)
            if not raw_text_content:
                self.log_message("Failed to download book content. Aborting.")
                return # Exit if download fails

            raw_book_title, sanitized_book_title = get_book_title(raw_text_content)
            book_author = get_book_author(raw_text_content)
            self.log_message(f"Detected Title: {raw_book_title}")
            self.log_message(f"Detected Author: {book_author}")

            book_output_dir = os.path.join(OUTPUT_BASE_DIR, sanitized_book_title)
            setup_output_directory(book_output_dir)

            raw_text_filepath = export_raw_text(raw_text_content, sanitized_book_title, book_output_dir)
            if not raw_text_filepath:
                self.log_message("Failed to export raw text. Aborting.")
                return

            self.log_message("\nCleaning text content...")
            cleaned_text_content = clean_text(raw_text_filepath, raw_book_title)
            if not cleaned_text_content:
                self.log_message("Failed to clean text. Aborting.")
                return

            cleaned_text_filepath = os.path.join(book_output_dir, f"{sanitized_book_title}_cleaned.txt")
            if not export_cleaned_text(cleaned_text_content, cleaned_text_filepath):
                self.log_message("Failed to export cleaned text. Aborting.")
                return

            self.log_message("Detecting overall language of the text...")
            detected_language_code = analyze_language(cleaned_text_content)
            self.log_message(f"Overall Detected Language: {detected_language_code}")

            regional_code_from_text = None
            if detected_language_code == "en": # Regional analysis only applies to English.
                self.log_message("Analyzing text for regional English context (US vs. GB)...")
                regional_code_from_text = analyze_regional_context(cleaned_text_content, detected_language_code)
                if regional_code_from_text:
                    self.log_message(f"Detected regional English context: {regional_code_from_text}")
                else:
                    self.log_message("No strong regional English context detected or language is not English.")

            self.log_message("Analyzing overall sentiment of the text...")
            overall_score, overall_magnitude = analyze_sentiment(cleaned_text_content)
            self.log_message(f"Overall Sentiment Score: {overall_score:.2f}, Magnitude: {overall_magnitude:.2f}")

            self.log_message("Classifying content categories...")
            classified_categories = []
            # Category analysis requires a minimum text length for meaningful results.
            if len(cleaned_text_content.split()) >= 20:
                classified_categories = analyze_category(cleaned_text_content)
                self.log_message(f"Content Categories: {', '.join(classified_categories) if classified_categories else 'None detected'}")
            else:
                self.log_message(f"Text too short ({len(cleaned_text_content.split())} words) for category classification. Skipping.")

            self.log_message("Analyzing syntax complexity...")
            syntax_analysis_info = analyze_syntax_complexity(cleaned_text_content)
            self.log_message(f"Syntax Info: Sentences={syntax_analysis_info['num_sentences']}, "
                             f"Avg Tokens/Sentence={syntax_analysis_info['avg_tokens_per_sentence']:.2f}, "
                             f"Complex Clauses={syntax_analysis_info['num_complex_clauses']}")

            # Determine the optimal TTS voice and parameters based on all gathered insights.
            voice_params = get_contextual_voice_parameters(
                detected_language_code=detected_language_code,
                sentiment_score=overall_score,
                categories=classified_categories,
                syntax_info=syntax_analysis_info,
                user_gender_preference=user_gender_preference,
                regional_code_from_text=regional_code_from_text
            )
            final_voice_name = voice_params["name"]
            final_pitch = voice_params["pitch"]
            final_speaking_rate = voice_params["speaking_rate"]
            final_language_code = voice_params["language_code"]
            final_voice_gender = voice_params["voice_gender"]

            self.log_message(f"\nSelected Fixed Voice based on context: {final_voice_name} ({final_language_code}, Gender: {final_voice_gender.name}), Pitch: {final_pitch}, Speaking Rate: {final_speaking_rate}")

            # Chunk the cleaned text into smaller parts suitable for the TTS API.
            text_chunks = chunk_text_from_file(cleaned_text_filepath, max_chars_per_chunk=MAX_CHARS_PER_TTS_CHUNK)
            if not text_chunks:
                self.log_message("No text chunks generated for audiobook. Aborting.")
                return

            audio_segments = [] # List to store pydub AudioSegment objects.
            temp_audio_dir = os.path.join(book_output_dir, "temp_audio_chunks")
            setup_output_directory(temp_audio_dir)

            self.log_message(f"\nStarting audio synthesis for {len(text_chunks)} chunks...")
            for i, chunk in enumerate(text_chunks):
                if not chunk.strip(): # Skip any chunks that might be empty after processing.
                    self.log_message(f"  Skipping empty chunk {i+1}/{len(text_chunks)}.")
                    continue

                self.log_message(f"  Processing chunk {i+1}/{len(text_chunks)} (approx {len(chunk)} chars)...")
                
                temp_audio_file = os.path.join(temp_audio_dir, f"chunk_{i:04d}.mp3")
                
                # Synthesize speech for the current text chunk.
                success = synthesize_text_to_speech(chunk, final_voice_name, final_language_code, final_voice_gender, temp_audio_file, final_pitch, final_speaking_rate)
                
                if success:
                    try:
                        # Load the generated MP3 chunk and add to the list for later concatenation.
                        audio_segments.append(AudioSegment.from_mp3(temp_audio_file))
                    except Exception as e:
                        # Handle potential issues with loading the generated MP3, indicating a corruption.
                        self.log_message(f"Error loading generated audio for chunk {i}: {e}. This might indicate a problem with the generated MP3. Skipping this chunk.")
                        continue # Continue to the next chunk.
                else:
                    self.log_message(f"Failed to synthesize audio for chunk {i} after multiple retries. Skipping this chunk.")
                    # Optionally save the failed chunk's text for debugging purposes.
                    with open(os.path.join(book_output_dir, f"failed_chunk_{i:04d}.txt"), "w", encoding="utf-8") as err_f:
                        err_f.write(chunk)
                    continue

            if not audio_segments:
                self.log_message("No audio segments were successfully generated for the audiobook. Aborting.")
                return

            self.log_message("\nCombining audio segments into final audiobook...")
            combined_audio = AudioSegment.empty()
            for segment in audio_segments:
                combined_audio += segment

            # Define the final output path for the combined audiobook.
            output_audio_file = os.path.join(book_output_dir, f"{sanitized_book_title}_audiobook.mp3")
            combined_audio.export(output_audio_file, format="mp3")
            
            # Store the path to enable opening the folder via the GUI button.
            self.current_audiobook_path = output_audio_file
            self.log_message(f"Audiobook created successfully: '{output_audio_file}'")

            self.log_message("Cleaning up temporary audio files...")
            # Remove individual chunk files and the temporary directory.
            for file_name in os.listdir(temp_audio_dir):
                os.remove(os.path.join(temp_audio_dir, file_name))
            os.rmdir(temp_audio_dir)
            self.log_message("Cleaned up temporary audio files.")

            self.log_message("\n--- Audiobook Generation COMPLETE! ---")
            messagebox.showinfo("Success", "Audiobook generated successfully!")
            self.output_frame.pack(pady=10) # Makes the output folder button visible.

        except Exception as e:
            # Catch any unexpected errors during the entire generation process.
            self.log_message(f"\n--- An unexpected ERROR occurred during generation: {e} ---")
            # Display a user-friendly error message box.
            messagebox.showerror("Error", f"An unexpected error occurred: {e}\nCheck the log for details.")
        finally:
            # This block always executes, ensuring the button is re-enabled.
            self.generate_button.config(state="normal", text="Generate Audiobook")


# --- Main Application Execution ---
if __name__ == "__main__":
    # Create the root Tkinter window.
    root = tk.Tk()
    # Instantiate the AudiobookApp class, passing the root window.
    app = AudiobookApp(root)
    # Start the Tkinter event loop, which makes the GUI interactive.
    root.mainloop()
