import os
import random
import time
from google.cloud import language_v1
from google.cloud import texttospeech
from google.api_core.exceptions import ResourceExhausted, InternalServerError, ServiceUnavailable

import nltk

nltk.download('punkt')

# Map generic language codes to common regional variants for voice search
GENERIC_TO_REGIONAL_MAP = {
    "en": ["en-US", "en-GB", "en-AU", "en-IN"],
    "fr": ["fr-FR", "fr-CA"],
    "de": ["de-DE"],
    "es": ["es-ES", "es-US", "es-MX"],
    "zh": ["zh-CN", "zh-TW", "zh-HK"],
}

# --- Global Cache for available voices ---
AVAILABLE_VOICES = []

# --- Configuration for API calls ---
INITIAL_RETRY_DELAY = 1
MAX_API_RETRIES = 5
PROACTIVE_DELAY_SECONDS = 0.1

# --- Regional Word Lists for English ---
US_ENGLISH_WORDS = {
    "color", "honor", "flavor", "labor", "neighbor", "humor", "favor", "splendor", "tumor", "rumor", "valour",
    "center", "meter", "liter", "theater", "fiber",
    "organize", "realize", "recognize", "apologize", "airplane", "truck", "elevator", "sidewalk", "trunk", "fall",
    "gasoline", "subway", "restroom", "bathroom", "french fries", "cookie", "candy", "garbage", "trash",
    "faucet", "schedule", "vacation", "movie", "soccer", "period", "parentheses", "brackets", "dash",
    "mail", "mailbox", "drugstore", "vest", "pants", "diaper", "flashlight", "college", "grades",
    "gotten", "jelly", "suspenders", "zucchini", "check" # banking
    # ... add more as you find them ...
}

GB_ENGLISH_WORDS = {
    "colour", "honour", "flavour", "labour", "neighbour", "humour", "favour", "splendour", "tumour", "rumour", "valour",
    "centre", "metre", "litre", "theatre", "fibre",
    "organise", "realise", "recognise", "apologise", "analyse", "paralyse", "aeroplane", "lorry", "lift", "pavement", "boot", "autumn",
    "petrol", "underground", "tube", "loo", "toilet", "chips", "crisps", "biscuit", "sweets", "rubbish", "dustbin",
    "tap", "timetable", "holiday", "film", "football", "full stop", "brackets", "square brackets", "hyphen",
    "post", "postbox", "chemist's", "waistcoat", "trousers", "nappy", "torch", "university", "marks",
    "got", "jam", "braces", "courgette", "cheque" # banking
    # ... add more as you find them ...
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
    time.sleep(PROACTIVE_DELAY_SECONDS)
    response = client.analyze_sentiment(request={'document': document})
    return response.language if response.language and response.language != 'und' else "en"

def analyze_sentiment(text_content):
    """Analyzes the sentiment of the input text."""
    client = language_v1.LanguageServiceClient()
    document = language_v1.Document(
        content=text_content, type_=language_v1.Document.Type.PLAIN_TEXT
    )
    time.sleep(PROACTIVE_DELAY_SECONDS)
    sentiment = client.analyze_sentiment(request={'document': document}).document_sentiment
    return sentiment.score, sentiment.magnitude

def analyze_category(text_content):
    """Classifies the content into categories using Natural Language API."""
    client = language_v1.LanguageServiceClient()
    document = language_v1.Document(
        content=text_content, type_=language_v1.Document.Type.PLAIN_TEXT
    )
    try:
        time.sleep(PROACTIVE_DELAY_SECONDS)
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
        time.sleep(PROACTIVE_DELAY_SECONDS)
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

def synthesize_text_to_speech(text_content, voice_name, language_code, voice_gender, output_filename, pitch=0.0, speaking_rate=1.0, max_retries=MAX_API_RETRIES, initial_delay=INITIAL_RETRY_DELAY):
    """
    Synthesizes speech from the input text using a specified voice,
    including its explicit gender, with retry logic for API errors.
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

    for attempt in range(max_retries + 1):
        try:
            time.sleep(PROACTIVE_DELAY_SECONDS)
            response = client.synthesize_speech(
                input=synthesis_input, voice=voice_params, audio_config=audio_config
            )

            with open(output_filename, "wb") as out:
                out.write(response.audio_content)
            return True

        except ResourceExhausted as e:
            if attempt < max_retries:
                delay = initial_delay * (2 ** attempt) + random.uniform(0, 1)
                print(f"  Rate limit hit for chunk. Retrying in {delay:.2f}s (Attempt {attempt + 1}/{max_retries})... Error: {e}")
                time.sleep(delay)
            else:
                print(f"  Max retries reached for rate limit on chunk. Error: {e}")
                return False
        except (InternalServerError, ServiceUnavailable) as e:
            if attempt < max_retries:
                delay = initial_delay * (2 ** attempt) + random.uniform(0, 1)
                print(f"  Server error for chunk. Retrying in {delay:.2f}s (Attempt {attempt + 1}/{max_retries})... Error: {e}")
                time.sleep(delay)
            else:
                print(f"  Max retries reached for server error on chunk. Error: {e}")
                return False
        except Exception as e:
            print(f"  An unexpected error occurred during TTS synthesis for chunk: {e}")
            return False
    return False

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
            return None
        else:
            print("Invalid input. Please type 'Male', 'Female', 'Neutral', or press Enter.")

def analyze_regional_context(text_content, detected_language_code):
    """
    Analyzes the text content for regional linguistic markers (e.g., spelling differences).
    Currently supports English (en-US vs. en-GB).

    Args:
        text_content (str): The full text content of the book.
        detected_language_code (str): The primary language code detected by NL API (e.g., 'en', 'fr').

    Returns:
        str | None: A more specific regional language code (e.g., 'en-US', 'en-GB')
                    if a strong regional bias is detected, otherwise None.
    """
    if not text_content or detected_language_code != "en":
        return None # Only analyze for English for now

    text_lower = text_content.lower()
    
    us_score = 0
    gb_score = 0

    # Tokenize the text to count words effectively
    words = nltk.word_tokenize(text_lower)
    word_set = set(words) # Use a set for faster lookup

    # Count occurrences of US-specific words
    for us_word in US_ENGLISH_WORDS:
        if us_word in word_set:
            us_score += text_lower.count(us_word) # Count occurrences, not just presence

    # Count occurrences of GB-specific words
    for gb_word in GB_ENGLISH_WORDS:
        if gb_word in word_set:
            gb_score += text_lower.count(gb_word) # Count occurrences

    print(f"  Regional Analysis (English): US score = {us_score}, GB score = {gb_score}")

    # Determine regional bias based on scores
    if us_score > gb_score * 1.5: # US words significantly more common
        return "en-US"
    elif gb_score > us_score * 1.5: # GB words significantly more common
        return "en-GB"
    else:
        # If scores are close or low, no strong regional bias detected
        return None


def get_contextual_voice_parameters(detected_language_code, sentiment_score, categories=None, syntax_info=None, user_gender_preference=None, regional_code_from_text=None):
    """
    Selects voice parameters based on detected language, regional context, sentiment score,
    text categories, syntax complexity, and optional user gender preference.
    Prioritizes Chirp voices first.
    Handles voice-specific parameter limitations (e.g., pitch not supported for Chirp voices).
    """
    # Determine the *effective* language code to search for voices
    # User's preferred regional code from text analysis takes precedence, then generic detection
    effective_language_search_code = regional_code_from_text if regional_code_from_text else detected_language_code

    voices_for_lang = []
    if len(effective_language_search_code) == 2 and effective_language_search_code in GENERIC_TO_REGIONAL_MAP:
        for regional_code in GENERIC_TO_REGIONAL_MAP[effective_language_search_code]:
            voices_for_lang.extend(get_available_tts_voices(regional_code))
            voices_for_lang = list({v.name: v for v in voices_for_lang}.values())
            if voices_for_lang:
                break
    
    if not voices_for_lang:
        voices_for_lang = get_available_tts_voices(effective_language_search_code)

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
    
    target_gender = user_gender_preference
    if target_gender is None:
        target_gender = texttospeech.SsmlVoiceGender.NEUTRAL
        if sentiment_score > 0.5:
            target_gender = texttospeech.SsmlVoiceGender.FEMALE
        elif sentiment_score < -0.5:
            target_gender = texttospeech.SsmlVoiceGender.MALE
        if categories:
            if any("Romance" in c for c in categories):
                target_gender = texttospeech.SsmlVoiceGender.FEMALE
            elif any("News" in c for c in categories) or any("Business & Industrial" in c for c in categories):
                target_gender = texttospeech.SsmlVoiceGender.NEUTRAL


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
            pitch = 0.0
            speaking_rate = 1.0

    if syntax_info and syntax_info["num_sentences"] > 0:
        avg_tokens = syntax_info["avg_tokens_per_sentence"]
        num_complex_clauses = syntax_info["num_complex_clauses"]

        if avg_tokens > 20 or num_complex_clauses > (syntax_info["num_sentences"] / 3):
            speaking_rate *= 0.90
            pitch -= 0.5
        elif avg_tokens < 10:
            speaking_rate *= 1.05

    candidates_by_gender = [v for v in preferred_voices if v.ssml_gender == target_gender]
    if candidates_by_gender:
        selected_voice = random.choice(candidates_by_gender)
    else:
        neutral_candidates = [v for v in preferred_voices if v.ssml_gender == texttospeech.SsmlVoiceGender.NEUTRAL]
        if neutral_candidates:
            selected_voice = random.choice(neutral_candidates)
            print(f"  Note: Could not find a voice for preferred gender {target_gender.name}. Falling back to a Neutral voice.")
        else:
            selected_voice = random.choice(preferred_voices)
            print(f"  Note: Could not find a voice for preferred gender {target_gender.name} or Neutral. Falling back to any available voice.")

    if "Chirp" in selected_voice.name or "Studio" in selected_voice.name:
        print(f"  Note: Selected voice '{selected_voice.name}' is a high-quality (Chirp/Studio) voice. Pitch and speaking_rate adjustments might not be supported. Setting to defaults.")
        pitch = 0.0
        speaking_rate = 1.0

    final_voice_language_code = selected_voice.language_codes[0]
    final_voice_gender = selected_voice.ssml_gender

    return {
        "name": selected_voice.name,
        "pitch": pitch,
        "speaking_rate": speaking_rate,
        "language_code": final_voice_language_code,
        "voice_gender": final_voice_gender
    }
