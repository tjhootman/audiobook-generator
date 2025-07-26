from audiobook.text_processing import (
    AudiobookTextPipeline,
    GutenbergSource,
    GutenbergCleaner,
    FileTextExporter,
    DefaultTextChunker,
    get_book_title,
    get_book_author,
    setup_output_directory
)

# Example usage of AudioBookTextPipeline

# 1. Define the URL of a Gutenberg book (Huckleberry Finn)
gutenberg_url = "https://www.gutenberg.org/cache/epub/76/pg76.txt"

# 2. Setup output directory
output_dir = "./audiobook_output"
setup_output_directory(output_dir)

# 3. Download the raw text and extract metadata
source = GutenbergSource(gutenberg_url)
raw_text = source.get_text()
if raw_text is None:
    print("Download failed.")
    exit(1)

raw_title, sanitized_title = get_book_title(raw_text)
author = get_book_author(raw_text)
print(f"Book Title: {raw_title}")
print(f"Sanitized Title: {sanitized_title}")
print(f"Author: {author}")

# 4. Define output file paths
raw_output_path = f"{output_dir}/{sanitized_title}_raw.txt"
clean_output_path = f"{output_dir}/{sanitized_title}_cleaned.txt"

# 5. Prepare pipeline components
cleaner = GutenbergCleaner()
exporter = FileTextExporter()
chunker = DefaultTextChunker()

# 6. Instantiate the pipeline (injecting abstractions)
pipeline = AudiobookTextPipeline(
    source=source,
    cleaner=cleaner,
    exporter=exporter,
    chunker=chunker
)

# 7. Run the pipeline: download, clean, export, chunk
cleaned_text, chunks = pipeline.process(
    raw_title=raw_title,
    raw_output_path=raw_output_path,
    clean_output_path=clean_output_path,
    chunk_size=4800
)

print(f"Cleaned text saved to: {clean_output_path}")
print(f"Number of chunks for TTS: {len(chunks)}")

# Optionally, inspect a sample chunk
for i, chunk in enumerate(chunks[:3], 1):
    print(f"\n--- Chunk {i} ---\n{chunk[:200]}...")  # Print first 200 chars