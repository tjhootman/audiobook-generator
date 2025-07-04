"""Module containing functions for creating video from audiobooks."""

import os
from moviepy import ImageClip, AudioFileClip

def create_video(image_path, audio_path, output_video_path, fps=24):
    """
    Creates a video from a static image and an MP3 audio track.

    Args:
        image_path (str): The file path to the static image (e.g., JPG, PNG).
        audio_path (str): The file path to the MP3 audio track.
        output_video_path (str): The desired file path for the output video (e.g., MP4).
        fps (int, optional): Frames per second for the output video. Defaults to 24.
    """
    if not os.path.exists(image_path):
        print(f"Error: Image file not found at '{image_path}'")
        return

    if not os.path.exists(audio_path):
        print(f"Error: Audio file not found at '{audio_path}'")
        return

    try:
        # Load the audio clip
        audio_clip = AudioFileClip(audio_path)

        # Create an image clip. The duration of the video will be the duration of the audio.
        # This part remains the same.
        image_clip = ImageClip(image_path, duration=audio_clip.duration)

        # Set the audio of the image clip by assigning to the .audio attribute
        image_clip.audio = audio_clip
        
        # The image_clip now has the audio attached. We can use it directly or rename it.
        final_clip = image_clip

        # Write the final video file
        # It's often good practice to specify an audio_codec for MP4 to ensure compatibility
        final_clip.write_videofile(output_video_path, fps=fps, codec="libx264", audio_codec="aac")

        print(f"Video created successfully at '{output_video_path}'")

    except Exception as e:
        print(f"An error occurred: {e}")
