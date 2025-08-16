"""Test for text processing modules"""
import os
import pytest

from audiobook import text_processing

# --- Mock Classes ---
class DummySource(text_processing.TextSource):
    def __init__(self, text):
        self._text = text
    def get_text(self):
        return self._text

class DummyExporter(text_processing.TextExporter):
    def export(self, content, destination):
        self.last_content = content
        self.last_destination = destination
        return bool(content and destination)

# --- GutenbergSource Tests ---
def test_gutenberg_source_invalid_url():
    with pytest.raises(ValueError):
        text_processing.GutenbergSource("invalid-url")

def test_gutenberg_source_non_text(monkeypatch):
    source = text_processing.GutenbergSource("https://www.gutenberg.org/cache/epub/76/pg76.txt")
    class DummyResponse:
        status_code = 200
        text = "foo"
        headers = {"Content-Type": "application/pdf"}
        def raise_for_status(self): pass
    monkeypatch.setattr(text_processing.requests, "get", lambda *a, **kw: DummyResponse())
    assert source.get_text() is None

def test_gutenberg_source_connection(monkeypatch):
    source = text_processing.GutenbergSource("https://www.gutenberg.org/cache/epub/76/pg76.txt")
    def raise_conn(*a, **kw): raise text_processing.requests.ConnectionError("fail")
    monkeypatch.setattr(text_processing.requests, "get", raise_conn)
    assert source.get_text() is None

# --- LocalFileSource Tests ---
def test_local_file_source_missing(monkeypatch):
    src = text_processing.LocalFileSource("/tmp/notfound.txt")
    assert src.get_text() is None

def test_local_file_source_permission(monkeypatch, tmp_path):
    testfile = tmp_path / "file.txt"
    testfile.write_text("hi")
    os.chmod(testfile, 0o000)  # Remove all perms
    src = text_processing.LocalFileSource(str(testfile))
    assert src.get_text() is None
    os.chmod(testfile, 0o644)  # Restore perms

def test_local_file_source_success(tmp_path):
    testfile = tmp_path / "file.txt"
    testfile.write_text("Hello world")
    src = text_processing.LocalFileSource(str(testfile))
    assert src.get_text() == "Hello world"

# --- GutenbergCleaner Tests ---
def test_gutenberg_cleaner_basic():
    cleaner = text_processing.GutenbergCleaner()
    raw = "*** START OF THE PROJECT GUTENBERG EBOOK ***\nfoo-\nbar\n*** END OF THE PROJECT GUTENBERG EBOOK ***"
    assert "foobar" in cleaner.clean(raw)

def test_gutenberg_cleaner_no_markers():
    cleaner = text_processing.GutenbergCleaner()
    raw = "No markers here\nsome_text"
    assert "No markers here" in cleaner.clean(raw)

def test_gutenberg_cleaner_title_fallback():
    cleaner = text_processing.GutenbergCleaner()
    text = "*** START OF THE PROJECT GUTENBERG EBOOK SOMEBOOK\nOnce upon\na time\n*** END OF THE PROJECT GUTENBERG EBOOK SOMEBOOK"
    assert "Once upon" in cleaner.clean(text, raw_title="SomeBook")

# --- NoOpCleaner ---
def test_noop_cleaner():
    cleaner = text_processing.NoOpCleaner()
    assert cleaner.clean("abc") == "abc"

# --- FileTextExporter ---
def test_file_exporter_success(tmp_path):
    path = tmp_path / "test.txt"
    exporter = text_processing.FileTextExporter()
    assert exporter.export("abc", str(path))
    assert path.read_text() == "abc"

def test_file_exporter_permission(monkeypatch, tmp_path):
    path = tmp_path / "test.txt"
    def raise_perm(*a, **kw): raise PermissionError("fail")
    monkeypatch.setattr("builtins.open", lambda *a, **kw: raise_perm())
    exporter = text_processing.FileTextExporter()
    assert not exporter.export("abc", str(path))

# --- Utility Functions ---
def test_setup_output_directory(tmp_path):
    dirpath = tmp_path / "newdir"
    text_processing.setup_output_directory(str(dirpath))
    assert dirpath.exists()

def test_get_book_title_and_author():
    text = "Title: The Book\nAuthor: John Doe\nMore text"
    assert text_processing.get_book_title(text)[1] == "The_Book"
    assert text_processing.get_book_author(text) == "John Doe"
    assert text_processing.get_book_title("No title")[0] == "unknown_book"
    assert text_processing.get_book_author("No author") == "unknown_author"

# --- TextProcessingService ---
def test_text_processing_service_success(tmp_path):
    src = DummySource("Title: Test\nAuthor: A\n*** START OF THE PROJECT GUTENBERG EBOOK ***\nHi\n*** END OF THE PROJECT GUTENBERG EBOOK ***")
    clean = text_processing.GutenbergCleaner()
    exp = DummyExporter()
    service = text_processing.TextProcessingService(src, clean, exp)
    result = service.process_text(str(tmp_path/"raw.txt"), str(tmp_path/"clean.txt"))
    assert result["raw_title"] == "Test"
    assert result["author"] == "A"
    assert "Hi" in result["cleaned_text"]

def test_text_processing_service_no_text():
    src = DummySource(None)
    service = text_processing.TextProcessingService(src, text_processing.NoOpCleaner(), DummyExporter())
    assert service.process_text("raw.txt", "clean.txt") is None
