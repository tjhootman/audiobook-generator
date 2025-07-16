-----
# Audiobook Generator

This application allows you to convert Project Gutenberg books into audiobooks using Google Cloud's Natural Language and Text-to-Speech APIs. It intelligently analyzes the text to select an appropriate voice and adjusts speech parameters (pitch, speaking rate) based on the content's sentiment, category, and syntax complexity.

-----

## Features

  * **Project Gutenberg Integration:** Easily download raw text content directly from Project Gutenberg URLs.
  * **Intelligent Text Cleaning:** Removes Project Gutenberg boilerplate, normalizes line breaks, and sanitizes text for optimal speech synthesis.
  * **Advanced Text Analysis:**
      * **Language Detection:** Automatically identifies the language of the book.
      * **Regional Context Analysis:** Differentiates between US and British English based on spelling.
      * **Sentiment Analysis:** Determines the emotional tone of the text.
      * **Content Categorization:** Classifies the book into various categories (e.g., "Fiction," "Science & Technology").
      * **Syntax Complexity Analysis:** Provides insights into sentence structure and complexity.
  * **Contextual Voice Selection:**
      * Prioritizes high-quality voices (Chirp, Neural2, Wavenet) available from Google Cloud.
      * **Dynamic Gender Selection:** Infers narrator gender based on content sentiment/category, or allows user preference.
      * **Adaptive Speech Parameters:** Adjusts **pitch** and **speaking rate** to match the text's mood, complexity, and genre.
  * **Robust Audio Synthesis:** Chunks large texts to adhere to API limits and includes retry logic for transient API errors.
  * **MP3 Output:** Combines all synthesized audio chunks into a single, complete MP3 audiobook file.
  * **Organized Output:** Creates a dedicated directory for each book, containing raw text, cleaned text, and the final audiobook.

-----

## Getting Started

### Prerequisites

Before running this application, you'll need:

1.  **Python 3.8+:** The application is developed in Python.
2.  **Google Cloud Project:** A Google Cloud project with billing enabled.
3.  **API Enablement:** Enable the following APIs in your Google Cloud project:
      * **Cloud Text-to-Speech API**
      * **Cloud Natural Language API**
4.  **Service Account Key:** Download a JSON service account key for your Google Cloud project.
      * Go to IAM & Admin -\> Service Accounts.
      * Create a new service account or select an existing one.
      * Create a new key (JSON format) and download it.
5.  **Environment Variable:** Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to the path of your downloaded JSON key file.
      * **Linux/macOS:**
        ```bash
        export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/keyfile.json"
        ```
      * **Windows (Command Prompt):**
        ```cmd
        set GOOGLE_APPLICATION_CREDENTIALS="C:\path\to\your\keyfile.json"
        ```
      * **Windows (PowerShell):**
        ```powershell
        $env:GOOGLE_APPLICATION_CREDENTIALS="C:\path\to\your\keyfile.json"
        ```

### Installation

1.  **Clone the repository:**

    ```bash
    git clone <repository_url>
    cd <repository_name>
    ```

    (Replace `<repository_url>` and `<repository_name>` with your actual repository details.)

2.  **Create a virtual environment (recommended):**

    ```bash
    python -m venv venv
    ```

3.  **Activate the virtual environment:**

      * **Linux/macOS:**
        ```bash
        source venv/bin/activate
        ```
      * **Windows:**
        ```cmd
        venv\Scripts\activate
        ```

4.  **Install the required Python packages:**

    ```bash
    pip install -r requirements.txt
    ```

    ```
    google-ai-generativelanguage==0.6.15
    google-api-core==2.24.2
    google-auth==2.40.2
    google-cloud-aiplatform==1.101.0
    google-cloud-bigquery==3.34.0
    google-cloud-core==2.4.3
    google-cloud-language==2.17.2
    google-cloud-resource-manager==1.14.2
    google-cloud-storage==2.19.0
    google-cloud-texttospeech==2.27.0
    google-genai==1.24.0
    google-generativeai==0.8.5
    google-resumable-media==2.7.2
    googleapis-common-protos==1.70.0
    grpc-google-iam-v1==0.14.2
    ffmpeg==1.4
    ffmpeg-python==0.2.0
    nltk==3.9.1
    protobuf==5.29.5
    pydub==0.25.1
    requests==2.32.3
    ```

    Pydub requires `ffmpeg` or `libav`. Instructions for installing these are usually platform-specific. For example, on Ubuntu: `sudo apt-get install ffmpeg`. On macOS with Homebrew: `brew install ffmpeg`.

-----

## Usage

To generate an audiobook, simply run the main script:

```bash
python audiobook_generator.py
```

The application will then prompt you to:

1.  Enter the **Project Gutenberg URL** for the book's raw text.
2.  Optionally, choose a **narrator gender** (Male, Female, Neutral, or let the application decide automatically).

The script will then proceed to:

  * Download and clean the book text.
  * Perform various language analyses (language, sentiment, categories, syntax).
  * Select a suitable Google Cloud TTS voice and adjust its parameters based on the analysis.
  * Synthesize the audio chunk by chunk.
  * Combine all audio chunks into a single MP3 file.
  * Save all output (raw text, cleaned text, and the final audiobook) in an organized directory structure under `audiobook_output/Your_Book_Title/`.

-----

## Project Structure

```
.
└── audiobook/ 
    ├── audiobook_cli.py            # CLI orchestration script for audiobook generation
    ├── audiobook_gui.py            # GUI application for audiobook generation
    ├── audio_analysis.py           # Functions for text analysis and TTS voice selection
    ├── text_processing.py          # Functions for downloading, cleaning, and chunking text
    ├── requirements.txt            # Python dependencies
└── audiobook_output/               # (Automatically created) Output directory
    └── Your_Book_Title/            # Dedicated directory for each generated audiobook
        ├── Your_Book_Title_raw.txt      # Raw downloaded text
        ├── Your_Book_Title_cleaned.txt  # Cleaned text
        ├── Your_Book_Title_audiobook.mp3 # Final combined audiobook
        └── temp_audio_chunks/   # (Temporary) Stores individual audio chunks during synthesis
            └── chunk_0000.mp3
            └── ...
```

-----

## Contributing

Contributions are welcome\! Please feel free to open issues or submit pull requests.

-----

## License

MIT License

-----
