"""Module contains function for generating audiobook image for video."""

from io import BytesIO
import os
from PIL import Image
from google import genai
from google.genai import types
import google
from google.cloud import aiplatform
from dotenv import load_dotenv

load_dotenv()

# this try-except block can eventually be removed in production
try:
    credentials, project = google.auth.default()
    print(f"DEBUG: Authenticating as {credentials.service_account_email if hasattr(credentials, 'service_account_email') else credentials.quota_project_id} for project {project}")
    print(f"DEBUG: Credentials type: {type(credentials)}")
    print(f"DEBUG: Credentials scopes: {credentials.scopes if hasattr(credentials, 'scopes') else 'N/A'}")
    # Ensure the project passed to the client matches the detected project
    aiplatform.init(project=project, location='us-east5')
    # ... rest of your image generation code
except Exception as e:
    print(f"Authentication/Initialization error: {e}")
    raise # Re-raise to see the full traceback

def create_cover_image(prompt: str, output_directory: str, output_filename: str):
    """
    Generates a single cover image using Vertex AI Imagen and saves it to a specified directory.

    Args:
        prompt (str): The text description for the image to be generated.
        output_directory (str): The path to the directory where the image will be saved.
        output_filename (str): The name of the file (e.g., "my_image.png") for the saved image.
    """

    # --- Configuration for Vertex AI Imagen ---
    # IMPORTANT: Replace with your actual Google Cloud Project ID and Location.
    # Ensure Vertex AI API is enabled in your Google Cloud Project.
    # Authenticate by running `gcloud auth application-default login` in your terminal.
    # It's good practice to get these from environment variables.
    PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT_ID')
    LOCATION = os.environ.get('GOOGLE_CLOUD_LOCATION')

    if not PROJECT_ID:
        raise ValueError(
            "Please set the 'GOOGLE_CLOUD_PROJECT_ID' environment variable "
            "or hardcode your project ID."
        )
    if not LOCATION:
        raise ValueError(
            "Please set the 'GOOGLE_CLOUD_LOCATION' environment variable "
            "or hardcode your location (e.g., 'us-central1')."
        )

    # Initialize the generative AI client for Vertex AI
    try:
        client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location=LOCATION
        )
        print(f"Initialized Vertex AI client for project '{PROJECT_ID}' in location '{LOCATION}'.")
    except Exception as e:
        raise ConnectionError(
            f"Failed to initialize Vertex AI client. Ensure `gcloud auth application-default login` "
            f"has been run and Vertex AI API is enabled for project '{PROJECT_ID}'. Error: {e}"
        ) from e


    # Use a dedicated Imagen model for generation.
    # Check Google Cloud Vertex AI documentation for the latest available models.
    # 'imagen-4.0-generate-preview-06-06' or 'imagen-3.0-generate-002' are common choices.
    IMAGE_GEN_MODEL_NAME = 'imagen-4.0-generate-preview-06-06'

    # Define the output directory
    OUTPUT_DIR = output_directory

    # --- Create the output directory if it doesn't exist ---
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created output directory: {OUTPUT_DIR}")

    # --- Image Generation ---
    try:
        print(f"Generating image with Imagen model: '{IMAGE_GEN_MODEL_NAME}' and prompt: '{prompt}'")

        response = client.models.generate_images(
            model=IMAGE_GEN_MODEL_NAME,
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
            generated_image = response.generated_images[0]
            image_bytes = generated_image.image.image_bytes
            
            # Determine file extension. Imagen often outputs PNG by default,
            # but you can specify `output_mime_type` in GenerateImagesConfig if needed.
            file_extension = "png" 
            # You could add logic here to derive from `generated_image.image.mime_type` if available.

            image = Image.open(BytesIO(image_bytes))

            # Construct the full output path
            # Ensure the output_filename has an extension, or append default
            base_name, ext = os.path.splitext(output_filename)
            if not ext: # If no extension was provided in output_filename
                ext = '.' + file_extension
            
            full_output_path = os.path.join(OUTPUT_DIR, f"{base_name}{ext}")
            image.save(full_output_path)
            print(f"Saved generated image to {full_output_path}")
        else:
            print("No image was generated by Imagen.")
            if response.safety_ratings:
                print("Safety ratings for prompt:", response.safety_ratings)
            if response.filtered_reason: # Imagen has this for filtered content
                print("Filtered reason:", response.filtered_reason)

    except Exception as e:
        print(f"An error occurred during Imagen generation: {e}")
        print("\nEnsure you have enabled the Vertex AI API in your Google Cloud project,")
        print("and that your `gcloud` authentication is set up correctly (`gcloud auth application-default login`).")
