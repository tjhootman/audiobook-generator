import os
import random # For random voice selection if multiple options
from google.cloud import language_v1
from google.cloud import texttospeech
from pydub import AudioSegment
from pydub.playback import play # For playing audio (optional)
from dotenv import load_dotenv

load_dotenv()

# Set your Google Cloud Project ID
os.environ["GOOGLE_CLOUD_PROJECT"] = os.getenv("GOOGLE_CLOUD_PROJECT_ID")

# --- Global Cache for available voices ---
# Store available voices to avoid repeated API calls
# This will be populated once.
AVAILABLE_VOICES = []

# Map generic language codes to common regional variants for voice search
# This list can be expanded based on your needs
GENERIC_TO_REGIONAL_MAP = {
    "en": ["en-US", "en-GB", "en-AU", "en-IN"],
    "fr": ["fr-FR", "fr-CA"],
    "de": ["de-DE"],
    "es": ["es-ES", "es-US", "es-MX"],
    "zh": ["zh-CN", "zh-TW", "zh-HK"], # Simplified Chinese, Traditional Taiwanese, Traditional Hong Kong
    # Add more as needed
}

def get_available_tts_voices(language_code=None):
    """
    Fetches and caches the list of available Text-to-Speech voices.
    Can filter by language_code.
    Handles generic language codes by expanding to common regional variants.
    """
    global AVAILABLE_VOICES
    if not AVAILABLE_VOICES:
        client = texttospeech.TextToSpeechClient()
        response = client.list_voices()
        AVAILABLE_VOICES = response.voices

    if language_code:
        matching_voices = []
        if len(language_code) == 2 and language_code in GENERIC_TO_REGIONAL_MAP:
            regional_codes_to_try = [language_code] + GENERIC_TO_REGIONAL_MAP.get(language_code, [])
        else:
            regional_codes_to_try = [language_code]

        for voice in AVAILABLE_VOICES:
            for voice_lang_code in voice.language_codes:
                if voice_lang_code in regional_codes_to_try:
                    matching_voices.append(voice)
                    break
        return matching_voices
    return AVAILABLE_VOICES

def analyze_language(text_content):
    """Detects the language of the input text using Natural Language API."""
    client = language_v1.LanguageServiceClient()
    document = language_v1.Document(
        content=text_content, type_=language_v1.Document.Type.PLAIN_TEXT
    )
    response = client.analyze_sentiment(request={'document': document})
    return response.language if response.language and response.language != 'und' else "en"

def analyze_sentiment(text_content):
    """Analyzes the sentiment of the input text."""
    client = language_v1.LanguageServiceClient()
    document = language_v1.Document(
        content=text_content, type_=language_v1.Document.Type.PLAIN_TEXT
    )
    sentiment = client.analyze_sentiment(request={'document': document}).document_sentiment
    return sentiment.score, sentiment.magnitude

def analyze_category(text_content):
    """Classifies the content into categories using Natural Language API."""
    client = language_v1.LanguageServiceClient()
    document = language_v1.Document(
        content=text_content, type_=language_v1.Document.Type.PLAIN_TEXT
    )
    try:
        response = client.classify_text(request={'document': document})
        return [category.name for category in response.categories]
    except Exception as e:
        print(f"Warning: Could not classify text content. Error: {e}")
        return []

def analyze_syntax_complexity(text_content):
    """
    Analyzes sentence structure complexity using Natural Language API's syntax analysis.
    Returns basic metrics that can hint at complexity.
    """
    client = language_v1.LanguageServiceClient()
    document = language_v1.Document(
        content=text_content, type_=language_v1.Document.Type.PLAIN_TEXT
    )
    try:
        response = client.analyze_syntax(request={'document': document})
        num_sentences = len(response.sentences)
        num_tokens = len(response.tokens)
        avg_tokens_per_sentence = num_tokens / num_sentences if num_sentences > 0 else 0

        clause_labels = ['acl', 'advcl', 'ccomp', 'csubj', 'xcomp']

        num_complex_clauses = sum(
            1 for token in response.tokens
            if token.dependency_edge.label.name.lower() in clause_labels
        )

        return {
            "num_sentences": num_sentences,
            "num_tokens": num_tokens,
            "avg_tokens_per_sentence": avg_tokens_per_sentence,
            "num_complex_clauses": num_complex_clauses
        }
    except Exception as e:
        print(f"Warning: Could not analyze syntax complexity. Error: {e}")
        print(f"  Error details: {e}")
        return {
            "num_sentences": 0,
            "num_tokens": 0,
            "avg_tokens_per_sentence": 0,
            "num_complex_clauses": 0
        }

def synthesize_text_to_speech(text_content, voice_name, language_code, voice_gender, output_filename, pitch=0.0, speaking_rate=1.0):
    """
    Synthesizes speech from the input text using a specified voice,
    including its explicit gender.
    """
    client = texttospeech.TextToSpeechClient()

    synthesis_input = texttospeech.SynthesisInput(text=text_content)

    voice_params = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=voice_name,
        ssml_gender=voice_gender
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        pitch=pitch,
        speaking_rate=speaking_rate
    )

    response = client.synthesize_speech(
        input=synthesis_input, voice=voice_params, audio_config=audio_config
    )

    with open(output_filename, "wb") as out:
        out.write(response.audio_content)
    print(f"Audio content written to file: {output_filename}")

def get_user_gender_preference():
    """
    Asks the user to select a gender and returns the corresponding SsmlVoiceGender enum.
    Returns None if the user does not provide a valid input.
    """
    while True:
        gender_input = input("Choose narrator gender (Male, Female, Neutral, or press Enter for automatic): ").strip().lower()
        if gender_input == "male":
            return texttospeech.SsmlVoiceGender.MALE
        elif gender_input == "female":
            return texttospeech.SsmlVoiceGender.FEMALE
        elif gender_input == "neutral":
            return texttospeech.SsmlVoiceGender.NEUTRAL
        elif gender_input == "":
            return None # User wants automatic selection
        else:
            print("Invalid input. Please type 'Male', 'Female', 'Neutral', or press Enter.")

def get_contextual_voice_parameters(detected_language_code, sentiment_score, categories=None, syntax_info=None, user_gender_preference=None):
    """
    Selects voice parameters based on detected language, sentiment score,
    text categories, syntax complexity, and optional user gender preference.
    Prioritizes Chirp voices first.
    Handles voice-specific parameter limitations (e.g., pitch not supported for Chirp voices).
    """
    voices_for_lang = []
    if len(detected_language_code) == 2 and detected_language_code in GENERIC_TO_REGIONAL_MAP:
        for regional_code in GENERIC_TO_REGIONAL_MAP[detected_language_code]:
            voices_for_lang.extend(get_available_tts_voices(regional_code))
            voices_for_lang = list({v.name: v for v in voices_for_lang}.values()) # Remove duplicates
            if voices_for_lang:
                break
    
    if not voices_for_lang:
        voices_for_lang = get_available_tts_voices(detected_language_code)

    # --- VOICE PRIORITIZATION (Chirp > Neural2/Studio > Standard > WaveNet) ---
    chirp_voices = [v for v in voices_for_lang if "Chirp" in v.name]
    neural2_studio_voices = [v for v in voices_for_lang if "Neural2" in v.name or ("Studio" in v.name and "Chirp" not in v.name)]
    standard_voices = [v for v in voices_for_lang if "Wavenet" not in v.name and "Neural2" not in v.name and "Studio" not in v.name and "Chirp" not in v.name]
    wavenet_voices = [v for v in voices_for_lang if "Wavenet" in v.name and "Neural2" not in v.name and "Studio" not in v.name and "Chirp" not in v.name]

    preferred_voices = []
    if chirp_voices:
        preferred_voices = chirp_voices
    elif neural2_studio_voices:
        preferred_voices = neural2_studio_voices
    elif standard_voices:
        preferred_voices = standard_voices
    elif wavenet_voices:
        preferred_voices = wavenet_voices
    else:
        preferred_voices = voices_for_lang

    if not preferred_voices:
        print(f"Warning: Still no suitable voices found for '{detected_language_code}' after all attempts. Falling back to hardcoded 'en-US-Wavenet-B'.")
        return {
            "name": "en-US-Wavenet-B",
            "pitch": 0.0,
            "speaking_rate": 1.0,
            "language_code": "en-US",
            "voice_gender": texttospeech.SsmlVoiceGender.NEUTRAL
        }

    selected_voice = None
    pitch = 0.0
    speaking_rate = 1.0
    
    # --- Determine target_gender: User preference overrides analysis ---
    target_gender = user_gender_preference # Start with user's choice
    if target_gender is None: # If user didn't specify, use analysis
        target_gender = texttospeech.SsmlVoiceGender.NEUTRAL # Default if no strong sentiment/category
        if sentiment_score > 0.5:
            target_gender = texttospeech.SsmlVoiceGender.FEMALE
        elif sentiment_score < -0.5:
            target_gender = texttospeech.SsmlVoiceGender.MALE
        # Category influence on target_gender (if applicable)
        if categories:
            if any("Romance" in c for c in categories):
                target_gender = texttospeech.SsmlVoiceGender.FEMALE
            elif any("News" in c for c in categories) or any("Business & Industrial" in c for c in categories):
                # For news/business, could be neutral or slightly male-biased if that's desired for authority
                target_gender = texttospeech.SsmlVoiceGender.NEUTRAL


    # --- Remaining parameter influences (pitch, speaking_rate) ---
    # These are influenced by sentiment, categories, and syntax, regardless of user-selected gender
    if sentiment_score > 0.1:
        pitch += 2.0
    elif sentiment_score < -0.1:
        pitch -= 2.0

    if categories:
        if any("Science Fiction" in c for c in categories) or \
           any("Fantasy" in c for c in categories):
            pitch -= 1.0
            speaking_rate *= 0.95
        elif any("Romance" in c for c in categories):
            pitch += 1.0
            speaking_rate *= 1.02
        elif any("News" in c for c in categories) or \
             any("Business & Industrial" in c for c in categories) or \
             any("Education" in c for c in categories):
            pitch = 0.0 # Reset for neutral/authoritative
            speaking_rate = 1.0 # Reset for neutral/authoritative

    if syntax_info and syntax_info["num_sentences"] > 0:
        avg_tokens = syntax_info["avg_tokens_per_sentence"]
        num_complex_clauses = syntax_info["num_complex_clauses"]

        if avg_tokens > 20 or num_complex_clauses > (syntax_info["num_sentences"] / 3):
            speaking_rate *= 0.90
            pitch -= 0.5
        elif avg_tokens < 10:
            speaking_rate *= 1.05

    # --- Voice Selection based on the (potentially user-defined) target_gender ---
    candidates_by_gender = [v for v in preferred_voices if v.ssml_gender == target_gender]
    if candidates_by_gender:
        selected_voice = random.choice(candidates_by_gender)
    else:
        # If specific gender preference cannot be met with preferred voices, try neutral
        neutral_candidates = [v for v in preferred_voices if v.ssml_gender == texttospeech.SsmlVoiceGender.NEUTRAL]
        if neutral_candidates:
            selected_voice = random.choice(neutral_candidates)
            print(f"  Note: Could not find a voice for preferred gender {target_gender.name}. Falling back to a Neutral voice.")
        else:
            selected_voice = random.choice(preferred_voices) # Fallback to any voice
            print(f"  Note: Could not find a voice for preferred gender {target_gender.name} or Neutral. Falling back to any available voice.")

    # --- CRITICAL LOGIC: Adjust parameters if voice doesn't support them ---
    if "Chirp" in selected_voice.name or "Studio" in selected_voice.name:
        print(f"  Note: Selected voice '{selected_voice.name}' is a high-quality (Chirp/Studio) voice. Pitch and speaking_rate adjustments might not be supported. Setting to defaults.")
        pitch = 0.0
        speaking_rate = 1.0

    final_voice_language_code = selected_voice.language_codes[0]
    final_voice_gender = selected_voice.ssml_gender # Get the actual gender of the selected voice

    return {
        "name": selected_voice.name,
        "pitch": pitch,
        "speaking_rate": speaking_rate,
        "language_code": final_voice_language_code,
        "voice_gender": final_voice_gender
    }


def text_to_audiobook_contextual_voice(input_filepath, output_audiobook_filepath):
    """
    Converts a text file to an audiobook with voice selection based on
    overall text sentiment, detected language/locale, content categories,
    syntax complexity, and user's gender preference. Prioritizes Chirp voices.
    """
    with open(input_filepath, "r", encoding="utf-8") as f:
        full_text = f.read()

    print("Fetching available Text-to-Speech voices...")
    get_available_tts_voices()

    # --- Ask user for gender preference ---
    user_gender_preference = get_user_gender_preference()
    if user_gender_preference:
        print(f"User selected narrator gender: {user_gender_preference.name}")
    else:
        print("User opted for automatic gender selection.")

    print("Detecting overall language of the text...")
    detected_language_code = analyze_language(full_text)
    print(f"Overall Detected Language: {detected_language_code}")

    print("Analyzing overall sentiment of the text...")
    overall_score, overall_magnitude = analyze_sentiment(full_text)
    print(f"Overall Sentiment Score: {overall_score:.2f}, Magnitude: {overall_magnitude:.2f}")

    print("Classifying content categories...")
    classified_categories = []
    if len(full_text.split()) >= 20:
        classified_categories = analyze_category(full_text)
        print(f"Content Categories: {', '.join(classified_categories) if classified_categories else 'None detected'}")
    else:
        print(f"Text too short ({len(full_text.split())} words) for category classification. Skipping.")

    print("Analyzing syntax complexity...")
    syntax_analysis_info = analyze_syntax_complexity(full_text)
    print(f"Syntax Info: Sentences={syntax_analysis_info['num_sentences']}, "
          f"Avg Tokens/Sentence={syntax_analysis_info['avg_tokens_per_sentence']:.2f}, "
          f"Complex Clauses={syntax_analysis_info['num_complex_clauses']}")

    voice_params = get_contextual_voice_parameters(
        detected_language_code=detected_language_code,
        sentiment_score=overall_score,
        categories=classified_categories,
        syntax_info=syntax_analysis_info,
        user_gender_preference=user_gender_preference # Pass user preference here
    )
    final_voice_name = voice_params["name"]
    final_pitch = voice_params["pitch"]
    final_speaking_rate = voice_params["speaking_rate"]
    final_language_code = voice_params["language_code"]
    final_voice_gender = voice_params["voice_gender"]

    print(f"\nSelected Fixed Voice based on context: {final_voice_name} ({final_language_code}, Gender: {final_voice_gender.name}), Pitch: {final_pitch}, Speaking Rate: {final_speaking_rate}")


    text_chunks = [chunk.strip() for chunk in full_text.split("\n\n") if chunk.strip()]

    audio_segments = []
    temp_audio_dir = "temp_audio_chunks"
    os.makedirs(temp_audio_dir, exist_ok=True)

    for i, chunk in enumerate(text_chunks):
        if not chunk:
            continue

        print(f"\nProcessing chunk {i+1}/{len(text_chunks)}: '{chunk[:50]}...'")
        print(f"  Using fixed voice: {final_voice_name}, Pitch: {final_pitch}, Speaking Rate: {final_speaking_rate}, Gender: {final_voice_gender.name}")

        temp_audio_file = os.path.join(temp_audio_dir, f"chunk_{i:04d}.mp3")
        try:
            synthesize_text_to_speech(chunk, final_voice_name, final_language_code, final_voice_gender, temp_audio_file, final_pitch, final_speaking_rate)
            audio_segments.append(AudioSegment.from_mp3(temp_audio_file))
        except Exception as e:
            print(f"Error generating audio for chunk {i}: {e}. Skipping this chunk.")
            continue

    if not audio_segments:
        print("No audio segments were generated. Exiting.")
        return

    print("\nCombining audio segments...")
    combined_audio = audio_segments[0]
    for segment in audio_segments[1:]:
        combined_audio += segment

    combined_audio.export(output_audiobook_filepath, format="mp3")
    print(f"Audiobook created successfully: {output_audiobook_filepath}")

    for file_name in os.listdir(temp_audio_dir):
        os.remove(os.path.join(temp_audio_dir, file_name))
    os.rmdir(temp_audio_dir)
    print("Cleaned up temporary audio files.")


if __name__ == "__main__":
    input_text_file = "my_story.txt"
    output_audio_file = "my_audiobook_user_gender_preference.mp3" # New output name

    text_to_audiobook_contextual_voice(input_text_file, output_audio_file)

    # Optional: Play the generated audiobook
    # try:
    #     print(f"Playing {output_audio_file}...")
    #     play(AudioSegment.from_mp3(output_audio_file))
    # except Exception as e:
    #     print(f"Could not play audio (requires ffplay): {e}")