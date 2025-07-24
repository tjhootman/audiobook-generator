"""Main program for uploading a video to YouTube."""
from youtube_upload import upload_youtube_video
import os

def main():
    """Orchestrates the process of uploading video to YouTube."""

    output_video = "audiobook_output/In_our_time/In_our_time_audiobook.mp4"
    raw_book_title = "In Our Time"
    book_author = "Ernest Hemingway"

    # 1. Upload video to YouTube Channel

    video_file = output_video
    video_title = f"{raw_book_title} Audiobook"
    video_description = f"Audiobook version of '{raw_book_title}' by {book_author}."
    video_tags = ["audiobook", "book", "literature", "classic"]
    video_privacy = "public" # Can be "public", "private", or "unlisted"

    uploaded_video_info = upload_youtube_video(
        file_path=video_file,
        title=video_title,
        description=video_description,
        tags=video_tags,
        privacy_status=video_privacy
    )

    if uploaded_video_info:
        print("\nUpload complete. Video details:")
        print(f"Title: {uploaded_video_info['snippet']['title']}")
        print(f"Description: {uploaded_video_info['snippet']['description']}")
        print(f"Privacy Status: {uploaded_video_info['status']['privacyStatus']}")
        print(f"Video ID: {uploaded_video_info['id']}")
    else:
        print("\nVideo upload failed.")

if __name__ == "__main__":
    main()
