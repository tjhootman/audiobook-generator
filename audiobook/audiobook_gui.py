"""
GUI application for converting text books into audiobooks.
The long-running audiobook generation process is handled in a separate thread to ensure
the GUI remains responsive during execution, preventing the application from freezing.
"""
import tkinter as tk
from tkinter import messagebox, filedialog # filedialog is now needed for local file selection
import os
import threading
import sys
from google.cloud import texttospeech
from pydub import AudioSegment # For combining audio segments

try:
    # Attempt to import subprocess for opening folders on macOS/Linux.
    # This is wrapped in a try-except as it might not be available in highly
    # restricted environments, although it's part of Python's standard library.
    # It prints a warning and sets subprocess to None, disabling the folder opening feature on those platforms.
    import subprocess
except ImportError:
    print("Warning: 'subprocess' module not available. Folder opening might not work on macOS/Linux.")
    subprocess = None # Set to None, disabling the folder opening feature on these platforms.

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
    # export_raw_text,          # No longer directly called, functionality inlined for raw export
    clean_text,                 # Cleans boilerplate and formatting from the raw text.
    export_cleaned_text,        # Saves the cleaned text to a file.
    chunk_text_from_file        # Splits the cleaned text into smaller chunks for TTS API processing.
)

# --- Application-wide Configuration ---
# Base directory where all generated audiobook files will be stored.
# This directory will be created if it doesn't exist.
OUTPUT_BASE_DIR = "audiobook_output"
# Maximum number of characters per text chunk sent to the Text-to-Speech API.
# This adheres to API limits and optimizes synthesis. Google Cloud TTS has a 5000 character limit per request.
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
    def __init__(self, master: tk.Tk):
        """
        Initializes the Tkinter application window and its widgets.

        Args:
            master (tk.Tk): The root Tkinter window instance.
        """
        self.master = master
        master.title("Project Gutenberg Audiobook Generator")
        master.geometry("600x600") # Sets the initial width and height of the window.
        master.resizable(False, False) # Prevents the user from resizing the window.

        # --- Optional: Set application icon ---
        # Ensure 'app_icon.png' is in the same directory as gui_app.py
        # Or specify a path like os.path.join("assets", "app_icon.png")
        try:
            icon_path = os.path.join("assets", "app_icon.png") # Replace with your actual icon file name
            if os.path.exists(icon_path):
                # Create a PhotoImage object. Keep a reference to prevent garbage collection.
                self.app_icon = tk.PhotoImage(file=icon_path)
                # Set the window icon. `True` means it applies to all window states.
                master.iconphoto(True, self.app_icon)
            else:
                print(f"Warning: Icon file not found at {icon_path}")
        except Exception as e:
            print(f"Error setting application icon: {e}")

        # --- GUI Widgets Setup ---

        # 1. Title Label
        self.title_label = tk.Label(master, text="Generate Audiobook from Project Gutenberg", font=("Arial", 16, "bold"))
        self.title_label.pack(pady=15) # Adds vertical padding.

        # 2. Input Source Selection (Radio Buttons)
        self.source_selection_frame = tk.LabelFrame(master, text="Select Book Source", padx=10, pady=10)
        self.source_selection_frame.pack(pady=10, padx=20, fill="x")

        self.source_type_var = tk.StringVar(master)
        self.source_type_var.set("url") # Default selection is Project Gutenberg URL

        self.url_radio = tk.Radiobutton(self.source_selection_frame, text="Project Gutenberg URL", variable=self.source_type_var, value="url", command=self.toggle_source_inputs)
        self.url_radio.pack(anchor="w") # Aligns radio button to the west (left).

        self.local_radio = tk.Radiobutton(self.source_selection_frame, text="Local TXT File", variable=self.source_type_var, value="local", command=self.toggle_source_inputs)
        self.local_radio.pack(anchor="w")

        # 3. Container frame to hold either URL or Local File inputs
        # This frame will manage the position for both input types, ensuring they don't jump.
        self.input_container_frame = tk.Frame(master)
        self.input_container_frame.pack(pady=5, fill="x", padx=20)
        # Configure the grid row and column within this container to expand.
        # This is CRUCIAL for the container to maintain its size when widgets are lifted/lowered,
        # preventing the parent frame from collapsing.
        self.input_container_frame.grid_columnconfigure(0, weight=1)
        self.input_container_frame.grid_rowconfigure(0, weight=1)

        # 4. URL Input Frame and Entry
        # Placed INSIDE the new input_container_frame, gridded at (0,0) with sticky="nsew".
        self.url_input_frame = tk.Frame(self.input_container_frame)
        tk.Label(self.url_input_frame, text="Book URL:").pack(side="left", padx=(0, 10))
        self.url_entry = tk.Entry(self.url_input_frame, width=50)
        self.url_entry.insert(0, "https://www.gutenberg.org/cache/epub/76/pg76.txt") # Pre-fills with an example URL.
        self.url_entry.pack(side="left", expand=True, fill="x")
        self.url_input_frame.grid(row=0, column=0, sticky="nsew") # Grid it initially at (0,0)

        # 5. Local File Input Frame and Widgets
        # Placed INSIDE the new input_container_frame, gridded at (0,0) with sticky="nsew".
        self.local_file_input_frame = tk.Frame(self.input_container_frame)
        tk.Label(self.local_file_input_frame, text="Local TXT File:").pack(side="left", padx=(0, 10))
        # Entry for file path, set to 'readonly' as user selects via browse button.
        self.file_path_entry = tk.Entry(self.local_file_input_frame, width=40, state="readonly")
        self.file_path_entry.pack(side="left", expand=True, fill="x")
        self.browse_button = tk.Button(self.local_file_input_frame, text="Browse...", command=self.browse_file)
        self.browse_button.pack(side="left", padx=(10, 0))
        # Attribute to store the path selected via browse_file method
        self.selected_local_file_path = None
        self.local_file_input_frame.grid(row=0, column=0, sticky="nsew") # Grid it initially at (0,0)

        # Call toggle_source_inputs to set initial state (local_file_input_frame will be lowered behind url_input_frame)
        self.toggle_source_inputs()

        # 6. Gender Preference Frame and OptionMenu
        self.gender_frame = tk.Frame(master)
        self.gender_frame.pack(pady=5, fill="x", padx=20)
        tk.Label(self.gender_frame, text="Narrator Gender:").pack(side="left", padx=(0, 10))
        self.gender_var = tk.StringVar(master)
        self.gender_var.set("Automatic")
        self.gender_options = ["Automatic", "Male", "Female", "Neutral"]
        self.gender_menu = tk.OptionMenu(self.gender_frame, self.gender_var, *self.gender_options)
        self.gender_menu.pack(side="left", expand=True, fill="x")

        # 7. Generate Button
        self.generate_button = tk.Button(master, text="Generate Audiobook", command=self.start_generation, font=("Arial", 12))
        self.generate_button.pack(pady=20)

        # 8. Status Display (Text Widget for detailed log with Scrollbar)
        self.status_label_frame = tk.LabelFrame(master, text="Process Log", padx=5, pady=5)
        self.status_label_frame.pack(pady=10, padx=20, fill="both", expand=True)

        self.status_text = tk.Text(self.status_label_frame, height=15, wrap="word", state="disabled", font=("Courier New", 10))
        self.status_text.pack(side="left", fill="both", expand=True)
        
        self.status_scrollbar = tk.Scrollbar(self.status_label_frame, command=self.status_text.yview)
        self.status_scrollbar.pack(side="right", fill="y")
        self.status_text.config(yscrollcommand=self.status_scrollbar.set)

        # 9. Output Link/Button (Initially hidden until audiobook is generated)
        self.output_frame = tk.Frame(master)
        # This frame is initially not packed (hidden) and will be packed on successful generation.

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
        self.log_message("Welcome to the Project Gutenberg Audiobook Generator!")
        self.log_message("Select a book source (URL or local file), then click 'Generate'.")
        self.log_message("Ensure GOOGLE_APPLICATION_CREDENTIALS is set and FFmpeg is installed.")

    def log_message(self, message: str):
        """
        Appends a message to the status text widget and ensures the GUI updates.

        This method is designed to be safe for updates from both the main thread
        and background threads, as `self.master.update_idletasks()` handles
        scheduling the update on the main Tkinter thread.

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
            """
            A custom file-like object to redirect stdout/stderr to a Tkinter Text widget.
            It also retains a reference to the original stdout/stderr to allow console
            logging as well (useful for debugging during development).
            """
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

    def toggle_source_inputs(self):
        """
        Swaps the visibility of the URL input frame and the local file input frame
        using `tkraise()` (bring to top) to ensure they occupy the same visual space
        without causing the UI to jump.
        """
        selected_source = self.source_type_var.get()

        if selected_source == "url":
            self.url_input_frame.tkraise() # Bring the URL input frame to the front.
        elif selected_source == "local":
            self.local_file_input_frame.tkraise() # Bring the Local File input frame to the front.

    def browse_file(self):
        """
        Opens a file dialog for the user to select a local TXT file.
        Updates the readonly file path entry widget with the selected path.
        """
        file_path = filedialog.askopenfilename(
            title="Select a TXT file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")] # Filters for .txt files
        )
        if file_path:
            # Update the readonly entry widget. Temporarily enable to write, then disable.
            self.file_path_entry.config(state="normal")
            self.file_path_entry.delete(0, tk.END) # Clear any existing text
            self.file_path_entry.insert(0, file_path) # Insert the new file path
            self.file_path_entry.config(state="readonly")
            self.selected_local_file_path = file_path # Store the selected path for processing
        else:
            self.selected_local_file_path = None # Clear if no file was selected

    def open_output_folder(self):
        """
        Opens the directory where the audiobook was saved using the system's default
        file explorer. This method handles different operating systems (Windows, macOS, Linux).
        """
        if self.current_audiobook_path:
            folder_path = os.path.dirname(self.current_audiobook_path)
            if os.path.exists(folder_path):
                try:
                    if sys.platform == "win32":
                        os.startfile(folder_path) # Command for Windows to open a file/folder
                    elif sys.platform == "darwin": # macOS
                        if subprocess:
                            subprocess.Popen(["open", folder_path]) # 'open' command via subprocess for macOS
                        else:
                            messagebox.showerror("Error", "subprocess module not available to open folder on macOS.")
                    else: # Linux (e.g., Ubuntu, Fedora with XDG)
                        if subprocess:
                            subprocess.Popen(["xdg-open", folder_path]) # 'xdg-open' for common Linux desktops
                        else:
                            messagebox.showerror("Error", "subprocess module not available to open folder on Linux.")
                except Exception as e:
                    # Catch any errors that occur during the attempt to open the folder.
                    messagebox.showerror("Error", f"Could not open folder: {e}")
            else:
                messagebox.showwarning("Warning", "Output folder does not exist. It might have been deleted or moved.")
        else:
            messagebox.showinfo("Info", "No audiobook has been generated yet to open its folder.")


    def start_generation(self):
        """
        Initiates the audiobook generation process. This method is called when
        the "Generate Audiobook" button is clicked. It validates input based on
        the selected source type (URL or local file) and then starts the
        `_run_audiobook_generation` method in a separate thread to keep the GUI responsive.
        """
        selected_source = self.source_type_var.get()
        book_content_source = None # This will hold either the URL string or the local file path string.

        # --- Input Validation based on selected source type ---
        if selected_source == "url":
            book_content_source = self.url_entry.get().strip()
            if not book_content_source:
                messagebox.showwarning("Input Error", "Please enter a Project Gutenberg URL.")
                return
            # Basic URL format check (can be expanded with more robust regex if needed)
            if not (book_content_source.startswith("http://") or book_content_source.startswith("https://")):
                messagebox.showwarning("Input Error", "Invalid URL format. Please include http:// or https://.")
                return
        elif selected_source == "local":
            book_content_source = self.file_path_entry.get().strip()
            if not book_content_source:
                messagebox.showwarning("Input Error", "Please select a local TXT file using the 'Browse...' button.")
                return
            if not os.path.exists(book_content_source):
                messagebox.showwarning("Input Error", f"Selected local file does not exist: {book_content_source}")
                return
            if not book_content_source.lower().endswith(".txt"):
                messagebox.showwarning("Input Error", "Selected file is not a .txt file. Please choose a plain text file.")
                return

        # Disable the generate button to provide visual feedback and prevent multiple simultaneous generations.
        self.generate_button.config(state="disabled", text="Generating...")
        self.output_frame.pack_forget() # Hide the previous output link if it was visible.
        self.current_audiobook_path = None # Reset the path for the new generation process.
        self.log_message("\n--- Starting Audiobook Generation ---")
        self.log_message(f"Processing Source ({selected_source}): {book_content_source}")

        # Create and start a new thread to run the main audiobook generation logic.
        # This is essential to prevent the GUI from freezing during the potentially long-running process.
        generation_thread = threading.Thread(
            target=self._run_audiobook_generation,
            args=(book_content_source, selected_source, self.gender_var.get())
        )
        generation_thread.start()

    def _run_audiobook_generation(self, book_content_source: str, source_type: str, gender_choice: str):
        """
        Contains the core audiobook generation logic, designed to be run
        in a separate thread. It integrates functions from `audio_analysis`
        and `text_processing` modules, adapting to the selected book source
        (URL download or local file read).

        Args:
            book_content_source (str): The URL string or local file path string of the book.
            source_type (str): The type of source ('url' or 'local').
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
            # allowing `get_contextual_voice_parameters` to infer gender based on text analysis.

            # --- Step 1: Obtain Raw Text Content ---
            raw_text_content = None
            if source_type == "url":
                self.log_message(f"Downloading content from URL: {book_content_source}")
                raw_text_content = download_book_content(book_content_source)
                if not raw_text_content:
                    self.log_message("Failed to download book content. Aborting generation.")
                    return # Exit if download fails
            elif source_type == "local":
                self.log_message(f"Reading content from local file: {book_content_source}")
                try:
                    # Attempt to read the local file with UTF-8 encoding.
                    with open(book_content_source, 'r', encoding='utf-8') as f:
                        raw_text_content = f.read()
                    if not raw_text_content.strip(): # Check if content is just whitespace after stripping
                        self.log_message("Local file is empty or contains only whitespace. Aborting generation.")
                        return
                except UnicodeDecodeError as ude:
                    self.log_message(f"Error decoding local file (check encoding): {ude}. Aborting generation.")
                    return
                except FileNotFoundError: # Already checked in start_generation, but included for robustness
                    self.log_message(f"Local file not found: {book_content_source}. Aborting generation.")
                    return
                except Exception as e:
                    self.log_message(f"Failed to read local file {book_content_source}: {e}. Aborting generation.")
                    return

            # --- Step 2: Extract Book Metadata (Title & Author) ---
            # For Project Gutenberg URLs, use specialized functions that parse their header format.
            # For local files, infer title from filename and use a generic author.
            if source_type == "url":
                raw_book_title, sanitized_book_title = get_book_title(raw_text_content)
                book_author = get_book_author(raw_text_content)
            else: # Logic for local files
                file_name_without_ext = os.path.splitext(os.path.basename(book_content_source))[0]
                raw_book_title = file_name_without_ext # Use filename as raw title
                # Basic sanitization for local file names to ensure valid directory/file names.
                sanitized_book_title = file_name_without_ext.replace(" ", "_").replace(".", "").replace("-", "_")
                # Ensure it's not empty after sanitization, fallback to a default if so.
                sanitized_book_title = sanitized_book_title if sanitized_book_title else "local_book_file"
                book_author = "Local Author" # Placeholder author for generic local files

            self.log_message(f"Detected Title: {raw_book_title}")
            self.log_message(f"Detected Author: {book_author}")

            # --- Step 3: Setup Output Directory for this specific book ---
            book_output_dir = os.path.join(OUTPUT_BASE_DIR, sanitized_book_title)
            setup_output_directory(book_output_dir)

            # --- Step 4: Export Raw Text Content to a local file ---
            # This step ensures a copy of the raw text is saved, regardless of source.
            raw_text_filepath = os.path.join(book_output_dir, f"{sanitized_book_title}_raw.txt")
            try:
                with open(raw_text_filepath, 'w', encoding='utf-8') as f:
                    f.write(raw_text_content)
                self.log_message(f"Successfully exported raw text to '{raw_text_filepath}'")
            except IOError as e:
                self.log_message(f"Error exporting raw text to '{raw_text_filepath}': {e}. Aborting generation.")
                return # Exit if file writing fails

            # --- Step 5: Clean Text Content ---
            self.log_message("\nCleaning text content...")
            # The `clean_text` function in `text_processing` is optimized for Gutenberg files.
            # For general local TXT files, it will still perform line break normalization,
            # underscore replacement, and space cleanup, but will not remove specific
            # Gutenberg headers/footers unless they happen to match.
            cleaned_text_content = clean_text(raw_text_filepath, raw_book_title)
            if not cleaned_text_content.strip(): # Check if content is just whitespace after cleaning
                self.log_message("Failed to clean text or cleaned text is empty after cleaning. Aborting generation.")
                return

            # --- Step 6: Export Cleaned Text to a file ---
            cleaned_text_filepath = os.path.join(book_output_dir, f"{sanitized_book_title}_cleaned.txt")
            if not export_cleaned_text(cleaned_text_content, cleaned_text_filepath):
                self.log_message("Failed to export cleaned text. Aborting generation.")
                return

            # --- Step 7: Analyze Text for Voice Selection Parameters ---
            # These analyses (language, sentiment, category, syntax) inform voice selection.
            self.log_message("Detecting overall language of the text...")
            detected_language_code = analyze_language(cleaned_text_content)
            self.log_message(f"Overall Detected Language: {detected_language_code}")

            regional_code_from_text = None
            if detected_language_code == "en": # Regional analysis is currently only implemented for English.
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
            # Category analysis requires a minimum text length for meaningful results (approx 20 words).
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

            # --- Step 8: Chunk Text for TTS Synthesis ---
            text_chunks = chunk_text_from_file(cleaned_text_filepath, max_chars_per_chunk=MAX_CHARS_PER_TTS_CHUNK)
            if not text_chunks:
                self.log_message("No text chunks generated for audiobook. Aborting generation.")
                return

            # --- Step 9: Synthesize Audio for Each Chunk ---
            audio_segments = [] # List to store pydub AudioSegment objects for final concatenation.
            temp_audio_dir = os.path.join(book_output_dir, "temp_audio_chunks")
            setup_output_directory(temp_audio_dir)

            self.log_message(f"\nStarting audio synthesis for {len(text_chunks)} chunks...")
            for i, chunk in enumerate(text_chunks):
                if not chunk.strip(): # Skip any chunks that might be empty after processing.
                    self.log_message(f"  Skipping empty chunk {i+1}/{len(text_chunks)}.")
                    continue

                self.log_message(f"  Processing chunk {i+1}/{len(text_chunks)} (approx {len(chunk)} chars)...")
                
                temp_audio_file = os.path.join(temp_audio_dir, f"chunk_{i:04d}.mp3")
                
                # Synthesize speech for the current text chunk using Google Cloud TTS.
                success = synthesize_text_to_speech(
                    chunk, final_voice_name, final_language_code, final_voice_gender,
                    temp_audio_file, final_pitch, final_speaking_rate
                )
                
                if success:
                    try:
                        # Load the generated MP3 chunk using pydub and add to the list for later concatenation.
                        audio_segments.append(AudioSegment.from_mp3(temp_audio_file))
                    except Exception as e:
                        # Handle potential issues with loading the generated MP3 (e.g., corrupted file).
                        self.log_message(f"Error loading generated audio for chunk {i}: {e}. This might indicate a problem with the generated MP3. Skipping this chunk.")
                        continue # Continue to the next chunk even if this one failed to load.
                else:
                    self.log_message(f"Failed to synthesize audio for chunk {i} after multiple retries. Skipping this chunk.")
                    # Optionally, save the failed chunk's text to a file for debugging purposes.
                    with open(os.path.join(book_output_dir, f"failed_chunk_{i:04d}.txt"), "w", encoding="utf-8") as err_f:
                        err_f.write(chunk)
                    continue

            if not audio_segments:
                self.log_message("No audio segments were successfully generated for the audiobook. Aborting generation.")
                return

            # --- Step 10: Combine Audio Segments into Final Audiobook ---
            self.log_message("\nCombining audio segments into final audiobook...")
            combined_audio = AudioSegment.empty()
            for segment in audio_segments:
                combined_audio += segment

            # Define the final output path for the combined audiobook MP3 file.
            output_audio_file = os.path.join(book_output_dir, f"{sanitized_book_title}_audiobook.mp3")
            combined_audio.export(output_audio_file, format="mp3")
            
            # Store the path to enable opening the output folder via the GUI button.
            self.current_audiobook_path = output_audio_file
            self.log_message(f"Audiobook created successfully: '{output_audio_file}'")

            # --- Step 11: Clean Up Temporary Files ---
            self.log_message("Cleaning up temporary audio files...")
            # Remove individual chunk files and the temporary directory.
            for file_name in os.listdir(temp_audio_dir):
                os.remove(os.path.join(temp_audio_dir, file_name))
            os.rmdir(temp_audio_dir)
            self.log_message("Cleaned up temporary audio files.")

            self.log_message("\n--- Audiobook Generation COMPLETE! ---")
            # Show a success pop-up message to the user.
            messagebox.showinfo("Success", "Audiobook generated successfully!")
            # Make the output folder button visible.
            self.output_frame.pack(pady=10)

        except Exception as e:
            # Catch any unexpected errors that occur during the entire generation process.
            self.log_message(f"\n--- An unexpected ERROR occurred during generation: {e} ---")
            # Display a user-friendly error message box.
            messagebox.showerror("Error", f"An unexpected error occurred: {e}\nCheck the log for details.")
        finally:
            # This 'finally' block ensures the generate button is re-enabled
            # regardless of whether the generation succeeded or failed, making the GUI usable again.
            self.generate_button.config(state="normal", text="Generate Audiobook")


# --- Main Application Execution Block ---
# This ensures that the GUI application only runs when the script is executed directly,
# not when it's imported as a module into another script.
if __name__ == "__main__":
    # Create the root Tkinter window instance.
    root = tk.Tk()
    # Instantiate the AudiobookApp class, passing the root window.
    app = AudiobookApp(root)
    # Start the Tkinter event loop. This makes the GUI interactive,
    # listening for user input and updating the display.
    root.mainloop()
