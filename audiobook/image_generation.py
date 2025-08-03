"""Module contains function for generating audiobook image for video."""

from io import BytesIO
from typing import Protocol
import os
import logging
from PIL import Image, UnidentifiedImageError
from google import genai
from google.genai import types
from google.cloud import aiplatform
import google
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

# --- Custom exceptions ---

class ImageGenerationError(Exception):
    """Custom exception raised for errors during image generation."""
    pass

class ImageSaveError(Exception):
    """Custom exception raised for errors during image saving."""
    pass

# --- Interface Definitions ---

class Authenticator(Protocol):
    """Protocol for classes that perform authentication."""
    def authenticate(self) -> None:
        """Performs an authentication process.

        This method is expected to handle the authentication state internally.
        """
        ...

class ImageGenerator(Protocol):
    """Protocol for classes that generate an image from a text prompt."""
    def generate_image(self, prompt: str) -> bytes:
        """
        Generates an image based on a given text prompt.

        Args:
            prompt (str): The text description of the image to generate.

        Returns:
            bytes: The binary data of the generated image.
        """
        ...

class ImageSaver(Protocol):
    """Protocol for classes that save an image to a file."""
    def save_image(self, image_bytes: bytes, output_directory: str, output_filename: str) -> str:
        """
        Saves image data to a file.

        Args:
            image_bytes (bytes): The binary data of the image to save.
            output_directory (str): The directory where the file should be saved.
            output_filename (str): The name of the output file.

        Returns:
            str: The full path to the saved image file.
        """
        ...


# --- Implementation Classes ---

# debugging print statements may eventually be removed in production
class GoogleAuthenticator(Authenticator):
    """
    An Authenticator implementation for Google Cloud, specifically for Vertex AI.
    It uses Application Default Credentials for flexible authentication.
    """
    def __init__(self, project: str, location: str):
            """
            Initializes the authenticator with a Google Cloud project and location.

            Args:
                project (str): The Google Cloud Project ID.
                location (str): The Google Cloud region for the Vertex AI endpoint.
            """
            self.project = project
            self.location = location
    def authenticate(self) -> None:
        """
        Initializes the authenticator with a Google Cloud project and location.

        Args:
            project (str): The Google Cloud Project ID.
            location (str): The Google Cloud region for the Vertex AI endpoint.
        """
        try:
            credentials, detected_project = google.auth.default()
            logging.info("Authenticating as %s for project %s",
                         getattr(credentials, 'service_account_email', getattr(credentials, 'quota_project_id', None)),
                         detected_project)
            logging.debug("Credentials type: %s", type(credentials))
            logging.debug("Credentials scopes: %s", getattr(credentials, 'scopes', 'N/A'))

            # Initialize the Vertex AI client with the configured project and location.
            aiplatform.init(project=self.project, location=self.location)
            logging.info("Vertex AI client initialized for project '%s' in location '%s'", self.project, self.location)

        except Exception as e:
            # Log the error with the traceback for better debugging
            logging.error("Authentication or Vertex AI initialization failed: %s", e, exc_info=True)
            # Re-raise the exception to signal a fatal error to the calling service
            raise

class VertexAIImageGenerator(ImageGenerator):
    """
    An ImageGenerator implementation for Google's Vertex AI Imagen model.
    It generates an image from a text prompt using the Vertex AI SDK.
    """
    def __init__(self, project_id: str, location: str, model_name: str = 'imagen-4.0-generate-preview-06-06'):
        """
        Initializes the image generator with project, location, and model details.

        Args:
            project_id (str): The Google Cloud Project ID.
            location (str): The Google Cloud region for the Vertex AI endpoint.
            model_name (str, optional): The name of the Imagen model to use.
                                        Defaults to 'imagen-4.0-generate-preview-06-06'.
        """
        self.project_id = project_id
        self.location = location
        self.model_name = model_name
        self._client = None

    def _get_client(self):
        """Initializes the Vertex AI client if it's not already initialized (lazy loading)."""
        if self._client is None:
            try:
                # The Vertex AI SDK uses google.auth.default() for authentication
                logging.info(
                    "Initializing Vertex AI client for project '%s' in location '%s'.",
                    self.project_id, self.location
                )
                self._client = genai.Client(
                    vertexai=True,
                    project=self.project_id,
                    location=self.location
                )
            except Exception as e:
                msg = (
                    f"Failed to initialize Vertex AI client. Ensure `gcloud auth application-default login` "
                    f"has been run and Vertex AI API is enabled for project '{self.project_id}'. Error: {e}"
                )
                logging.error(msg, exc_info=True)
                raise ConnectionError(msg) from e
        return self._client

    def generate_image(self, prompt: str) -> bytes:
        """
        Generates an image from a text prompt using the Vertex AI Imagen API.

        Args:
            prompt (str): The text description of the image to generate.

        Returns:
            bytes: The binary data of the generated image.

        Raises:
            ImageGenerationError: If the API fails to return a valid image.
        """
        logging.info("Generating image with prompt: '%s'", prompt)

        try:
            client = self._get_client()
            
            response = client.models.generate_images(
                model=self.model_name,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,  # Explicitly set to 1, though it was already 1
                    aspect_ratio="16:9",  # Supported: "1:1", "3:4", "4:3", "9:16", "16:9"
                    # safety_filter_level="BLOCK_MEDIUM_AND_ABOVE", # Adjust as needed
                    person_generation="ALLOW_ADULT", # Adjust as needed if generating people
                    # add_watermark=True # Default is True, set to False if you don't want watermarks (requires specific model support)
                ),
            )

            if response.generated_images:
                # Since number_of_images is 1, we can directly access the first (and only) image
                logging.info("Image successfully generated.")
                return response.generated_images[0].image.image_bytes
            
            else:
                msg = "Imagen generation failed: no image returned by API."
                logging.warning(msg)

                if response.safety_ratings:
                    logging.warning("Safety ratings for prompt: %s", response.safety_ratings)
                if response.filtered_reason: # Imagen has this for filtered content
                    logging.warning("Safety ratings for prompt: %s", response.filtered_reason)
                
                raise ImageGenerationError(msg)

        except Exception as e:
            msg = f"An error occurred during Imagen generation: {e}"
            logging.error(msg, exc_info=True)
            raise ImageGenerationError(msg) from e

class PILImageSaver(ImageSaver):
    """An ImageSaver implementation that uses the Pillow library to save image bytes."""
    def save_image(self, image_bytes: bytes, output_directory: str, output_filename: str) -> str:
        """
        Saves image data to a file using the Pillow library.

        Args:
            image_bytes (bytes): The binary data of the image to save.
            output_directory (str): The directory where the file should be saved.
            output_filename (str): The name of the output file.

        Returns:
            str: The full path to the saved image file.

        Raises:
            ImageSaveError: If an error occurs during the saving process.
        """

        # Create the output directory if it doesn't exist
        # Ensure the output directory exists.
        try:
            os.makedirs(output_directory, exist_ok=True)
            logging.info("Output directory '%s' ensured.", output_directory)
        except OSError as e:
            logging.error("Error creating directory '%s': %s", output_directory, e)
            raise ImageSaveError(f"Failed to create directory {output_directory}") from e

        try:
            image_stream = BytesIO(image_bytes)
            image = Image.open(image_stream)

            # Automatically detect the image format and determine the correct extension
            extension = image.format.lower() if image.format else 'png'
            if extension == 'jpeg':
                extension = 'jpg'
            
            base_name, _ = os.path.splitext(output_filename)
            full_output_path = os.path.join(output_directory, f"{base_name}.{extension}")

            image.save(full_output_path)
            logging.info("Saved generated image to %s", full_output_path)
            return full_output_path
        except (UnidentifiedImageError, OSError, ValueError) as e:
            # Catch specific Pillow and file system errors
            logging.error("Error saving image to %s: %s", full_output_path, e, exc_info=True)
            raise ImageSaveError(f"Failed to save image to {full_output_path}") from e
        except Exception as e:
            # Catch any other unexpected errors
            logging.error("An unexpected error occurred in saving text: %s", e, exc_info=True)
            raise ImageSaveError(f"An unexpected error occurred: {e}") from e

# --- Utility Functions ---

def get_env_or_raise(var: str, friendly: str):
    """
    Retrieves an environment variable and raises an error if it is not set.

    This function is a defensive utility for ensuring that required
    configuration variables are present in the environment.

    Args:
        var (str): The name of the environment variable to retrieve.
        friendly (str): A user-friendly description of the variable, used in
                        the error message.

    Returns:
        str: The value of the environment variable.

    Raises:
        ValueError: If the environment variable is not set or is an empty string.
    """
    val = os.environ.get(var)
    if not val:
        raise ValueError(f"Please set the '{var}' environment variable ({friendly}).")
    return val

# --- High-level Service ---

class CoverImageService:
    """
    A service that orchestrates the end-to-end process of creating and saving a cover image.
    
    This class handles authentication, image generation, and saving by
    delegating tasks to its injected dependencies.
    """
    def __init__(
        self,
        authenticator: Authenticator,
        image_generator: ImageGenerator,
        image_saver: ImageSaver,
    ) -> None:
        """
        Initializes the service with its dependencies.
        
        Args:
            authenticator (Authenticator): An object to handle authentication.
            image_generator (ImageGenerator): An object to generate the image.
            image_saver (ImageSaver): An object to save the generated image.
        """
        self.authenticator = authenticator
        self.image_generator = image_generator
        self.image_saver = image_saver

    def create_cover_image(self, prompt: str, output_directory: str, output_filename: str) -> str:
        """
        Executes the full pipeline to create and save a cover image.

        Args:
            prompt (str): The text description for the cover image.
            output_directory (str): The directory to save the image to.
            output_filename (str): The filename for the saved image.

        Returns:
            str: The full path to the saved image file.

        Raises:
            Any exceptions raised by the underlying components (e.g., authentication,
            image generation, or saving errors).
        """
        logging.info("Starting cover image creation process.")
 
        # Step 1: Authenticate with the necessary service
        self.authenticator.authenticate()
        logging.info("Authentication complete.")
 
        # Step 2: Generate the image using the given prompt
        image_bytes = self.image_generator.generate_image(prompt)
        logging.info("Image generation complete.")

        # Step 3: Save the image to the specified location
        output_path = self.image_saver.save_image(image_bytes, output_directory, output_filename)
        logging.info("Cover image saved to: %s", output_path)
 
        return output_path
