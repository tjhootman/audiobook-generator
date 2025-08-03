"""Module containing functions for creating video from audiobooks."""

import os
import logging
from typing import Optional, Protocol
from moviepy import ImageClip, AudioFileClip, VideoFileClip, concatenate_videoclips

# --- Custom exceptions ---

class RenderingError(Exception):
    """Custom exception raised for errors during video rendering."""
    pass

# --- Interface Definitions ---

class VideoRenderer(Protocol):
    """Protocol for classes that render a video from an image and an audio file."""
    def __init__(
        self,
        fps: int = 24,
        video_codec: str = "libx264",
        audio_codec: str = "aac"
    ) -> None:
        """
        Initializes the renderer with video and audio settings.

        Args:
            fps (int, optional): The frames per second for the output video. Defaults to 24.
            video_codec (str, optional): The codec to use for the video stream. Defaults to "libx264".
            audio_codec (str, optional): The codec to use for the audio stream. Defaults to "aac".
        """
        ...

    def render_video(
        self,
        image_path: str,
        audio_path: str,
        output_video_path: str,
        intro_video_path: Optional[str] = None,
    ) -> None:
        """
        Renders a video by combining a static image with an audio track.

        Args:
            image_path (str): The file path to the static image.
            audio_path (str): The file path to the audio file.
            output_video_path (str): The file path to save the output video.
            intro_video_path (Optional[str], optional): The file path to an optional intro video clip.
                                                        Defaults to None.
        """
        ...

# --- Implmentation Classes ---

class AudiobookVideoRenderer(VideoRenderer):
    """
    A VideoRenderer implementation that uses the moviepy library to create
    a video from an image and an audio file, with an optional intro.
    """
    def __init__(
        self,
        fps: int = 24,
        video_codec: str = "libx264",
        audio_codec: str = "aac"
    ):
        """
        Initializes the renderer with video and audio settings.

        Args:
            fps (int, optional): The frames per second for the output video. Defaults to 24.
            video_codec (str, optional): The codec to use for the video stream. Defaults to "libx264".
            audio_codec (str, optional): The codec to use for the audio stream. Defaults to "aac".
        """
        self.fps = fps
        self.video_codec = video_codec
        self.audio_codec = audio_codec

    def render_video(
        self,
        image_path: str,
        audio_path: str,
        output_video_path: str,
        intro_video_path: Optional[str] = None,
    ) -> None:
        """
        Renders a video by combining a static image with an audio track.

        Args:
            image_path (str): The file path to the static image.
            audio_path (str): The file path to the audio file.
            output_video_path (str): The file path to save the output video.
            intro_video_path (Optional[str], optional): The file path to an optional intro video clip.
                                                        Defaults to None.
        
        Raises:
            RenderingError: If a required file is not found or an error occurs during rendering.
        """
        if not os.path.exists(image_path):
            msg = f"Error: Image file not found at '{image_path}'"
            logging.error(msg)
            raise RenderingError(msg)
        if not os.path.exists(audio_path):
            msg = f"Error: Audio file not found at '{audio_path}'"
            logging.error(msg)
            raise RenderingError(msg)
 
        try:
            logging.info("Starting video rendering process.")

            audio_clip = AudioFileClip(audio_path)
            image_clip = ImageClip(image_path, duration=audio_clip.duration)
            image_clip.audio = audio_clip
            clips_to_concatenate = []

            if intro_video_path:
                if not os.path.exists(intro_video_path):
                    logging.warning("Intro video file not found at '%s'. Skipping intro.", intro_video_path)
                else:
                    intro_clip = VideoFileClip(intro_video_path)
                    clips_to_concatenate.append(intro_clip)
                    logging.info("Intro video clip loaded successfully.")

            clips_to_concatenate.append(image_clip)
            
            final_video_clip = concatenate_videoclips(clips_to_concatenate, method="compose")

            logging.info("Writing final video file to '%s'", output_video_path)
            final_video_clip.write_videofile(
                output_video_path,
                fps=self.fps,
                codec=self.video_codec,
                audio_codec=self.audio_codec,
                logger='bar'
            )

            logging.info("Video created successfully.")

        except (IOError, FileNotFoundError, ValueError) as e:
            # Catch standard I/O and value-related exceptions raised by moviepy
            msg = f"A moviepy or I/O error occurred during video rendering: {e}"
            logging.error(msg, exc_info=True)
            raise RenderingError(msg) from e
        except Exception as e:
            # A final, generic catch-all for unexpected issues
            msg = f"An unexpected error occurred during video rendering: {e}"
            logging.error(msg, exc_info=True)
            raise RenderingError(msg) from e

# --- High-level Service  ---

class AudiobookVideoService:
    """
    A service that orchestrates the end-to-end process of creating an audiobook video.
    
    This service is responsible for calling the video renderer with the necessary
    input files.
    """
    def __init__(self, renderer: VideoRenderer) -> None:
        """
        Initializes the service with a concrete video renderer implementation.
        
        Args:
            renderer (VideoRenderer): An object that handles the video rendering process.
        """
        self.renderer = renderer

    def create_video(
            self,
            image_path: str,
            audio_path: str,
            output_video_path: str,
            intro_video_path: Optional[str] = None
    ) -> None:
        """
        Creates an audiobook video by combining an image and an audio file.

        Args:
            image_path (str): The file path to the static image.
            audio_path (str): The file path to the audio file.
            output_video_path (str): The file path to save the output video.
            intro_video_path (Optional[str], optional): The file path to an optional intro video clip.
                                                        Defaults to None.
        """
        logging.info("Audiobook video creation service starting...")
        self.renderer.render_video(
            image_path,
            audio_path,
            output_video_path,
            intro_video_path
        )
        logging.info("Audiobook video creation service complete.")
