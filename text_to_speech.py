from dotenv import load_dotenv
load_dotenv() # This loads the variables from .env into your script's environment

from google.cloud import texttospeech

def synthesize_text(text, output_filename="output.mp3"):
    """Synthesizes speech from the input string of text and saves it to a file.

    Args:
        text (str): The text content to be synthesized.
        output_filename (str): The name of the output audio file (e.g., "output.mp3").
    """
    client = texttospeech.TextToSpeechClient()

    # Set the text input to be synthesized
    synthesis_input = texttospeech.SynthesisInput(text=text)

    # Build the voice request, select the language code ("en-US") and the ssml
    # voice gender ("neutral")
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-AU",
        name="en-AU-Chirp3-HD-Sadaltager"
        # You can specify a specific voice name for more control, e.g.,
        # name="en-US-Wavenet-D"
    )

    # Select the type of audio file you want returned
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    # Perform the text-to-speech request
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    # The audio_content contains the binary audio data
    with open(f"./output/{output_filename}", "wb") as out:
        out.write(response.audio_content)
        print(f'Audio content written to file "{output_filename}"')

# Example usage:
long_text = """
Chapter 1: The Old Mill. The wind howled mournfully across the moor,
whipping the ancient timbers of the old mill. Inside, the miller, a man
of grizzled beard and weary eyes, tended to his lonely duties. He had lived
in this remote place all his life, and the creak of the grinding stones
was as familiar to him as his own heartbeat. Tonight, however, there was
an unusual chill in the air, a silence that felt heavier than usual between
the gusts of wind. He shivered, pulling his woolen cloak tighter, and cast
a nervous glance towards the darkened windows.
"""

synthesize_text(long_text, "audiobook_chapter1.mp3")
