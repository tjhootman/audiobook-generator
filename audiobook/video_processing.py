"""Module containing functions for creating video from audiobooks."""

import os
from moviepy import ImageClip, AudioFileClip, VideoFileClip, concatenate_videoclips
from typing import Optional, Protocol

# --- Abstractions (Interfaces) ---

class IVideoRenderer(Protocol):
    def render_video(
            self,
            image_path: str,
            audio_path: str,
            output_video_path: Optional[str] = None,
            fps: int = 24
    ) -> None:
        ...

# --- Implentations ---

class AudiobookVideoRenderer(IVideoRenderer):
    def render_video(
            self,
            image_path: str,
            audio_path: str,
            output_video_path: str,
            intro_video_path: Optional[str] = None,
            fps: int = 24
    ) -> None:
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
                    # Optionally, set image_clip size to match intro_clip for consistency:
                    # image_clip = image_clip.set_size(intro_clip.size)

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

# --- High-level Service (optional for further extension) ---

class AudiobookVideoService:
    def __init__(self, renderer: IVideoRenderer):
        self.renderer = renderer

    def create_video(
            self,
        image_path: str,
        audio_path: str,
        output_video_path: str,
        intro_video_path: Optional[str] = None,
        fps: int = 24
    ) -> None:
        self.renderer.render_video(image_path, audio_path, output_video_path, intro_video_path, fps)
