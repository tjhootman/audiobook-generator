"""Module containing functions for creating video from audiobooks."""

import os
from moviepy import ImageClip, AudioFileClip, VideoFileClip, concatenate_videoclips

def create_video(image_path, audio_path, output_video_path, intro_video_path=None, fps=24):
    """
    Creates a video from a static image and an MP3 audio track, optionally
    appending an intro video at the beginning.

    Args:
        image_path (str): The file path to the static image (e.g., JPG, PNG).
        audio_path (str): The file path to the MP3 audio track.
        output_video_path (str): The desired file path for the output video (e.g., MP4).
        intro_video_path (str, optional): The file path to an intro video (e.g., MP4)
                                          to be prepended. Defaults to None.
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
        image_clip = ImageClip(image_path, duration=audio_clip.duration)

        # Set the audio of the image clip
        image_clip.audio = audio_clip

        # Initialize a list to hold all video clips
        clips_to_concatenate = []

        # If an intro video path is provided, load it and add to the list
        if intro_video_path:
            if not os.path.exists(intro_video_path):
                print(f"Warning: Intro video file not found at '{intro_video_path}'. Skipping intro.")
            else:
                intro_clip = VideoFileClip(intro_video_path)
                clips_to_concatenate.append(intro_clip)
                # It's good practice to ensure consistent size,
                # though concatenate_videoclips with 'compose' handles different sizes.
                # If you want to explicitly resize, you could do:
                # image_clip = image_clip.set_size(intro_clip.size)
                # For now, we'll rely on 'compose' to center clips if sizes differ.

        # Add the main audiobook video (image with audio) to the list
        clips_to_concatenate.append(image_clip)
        
        # Concatenate all clips
        # Using method="compose" handles different resolutions by centering smaller clips
        final_video_clip = concatenate_videoclips(clips_to_concatenate, method="compose")

        # Write the final video file
        final_video_clip.write_videofile(output_video_path, fps=fps, codec="libx264", audio_codec="aac")

        print(f"Video created successfully at '{output_video_path}'")

    except Exception as e:
        print(f"An error occurred: {e}")
