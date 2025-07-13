import os
import random
import time
from google.cloud import language_v1
from google.cloud import texttospeech
from google.api_core.exceptions import ResourceExhausted, InternalServerError, ServiceUnavailable

import nltk

# Ensure 'punkt' and 'punkt_tab' tokenizers are downloaded
# Catch LookupError, as that's what nltk.data.find() raises when resource is not found.
try:
    nltk.data.find('tokenizers/punkt')
except LookupError: # Corrected exception type
    print("Downloading NLTK 'punkt' tokenizer data...")
    nltk.download('punkt')

try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError: # Corrected exception type
    print("Downloading NLTK 'punkt_tab' tokenizer data...")
    nltk.download('punkt_tab') # This is the download that was explicitly requested by NLTK's error message

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
MIN_TEXT_LENGTH_FOR_ANALYSIS = 50 # Minimum characters for sentiment/category/syntax analysis

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
        # Improvement: Explicitly search for exact match first, then regional variants
        codes_to_check = [language_code]
        if len(language_code) == 2 and language_code in GENERIC_TO_REGIONAL_MAP:
            codes_to_check.extend(GENERIC_TO_REGIONAL_MAP[language_code])
        elif len(language_code) == 5 and language_code[:2] in GENERIC_TO_REGIONAL_MAP:
            # If a regional code is given, also try its generic form if not already included
            if language_code[:2] not in codes_to_check:
                codes_to_check.append(language_code[:2])

        # Use a set to avoid duplicate codes if a generic and regional are both requested
        codes_to_check = list(set(codes_to_check))

        for voice in AVAILABLE_VOICES:
            for voice_lang_code in voice.language_codes:
                if voice_lang_code in codes_to_check:
                    matching_voices.append(voice)
                    break
        return matching_voices
    return AVAILABLE_VOICES

def analyze_language(text_content):
    """Detects the language of the input text using Natural Language API."""
    if not text_content or len(text_content) < MIN_TEXT_LENGTH_FOR_ANALYSIS:
        print(f"  Skipping language analysis due to short text length (< {MIN_TEXT_LENGTH_FOR_ANALYSIS} chars). Defaulting to 'en'.")
        return "en" # Default to English for very short texts

    client = language_v1.LanguageServiceClient()
    document = language_v1.Document(
        content=text_content, type_=language_v1.Document.Type.PLAIN_TEXT
    )
    try:
        time.sleep(PROACTIVE_DELAY_SECONDS)
        response = client.analyze_sentiment(request={'document': document}) # Language is also in this response
        return response.language if response.language and response.language != 'und' else "en"
    except Exception as e:
        print(f"Warning: Could not detect language. Error: {e}. Defaulting to 'en'.")
        return "en"


def analyze_sentiment(text_content):
    """Analyzes the sentiment of the input text."""
    if not text_content or len(text_content) < MIN_TEXT_LENGTH_FOR_ANALYSIS:
        print(f"  Skipping sentiment analysis due to short text length (< {MIN_TEXT_LENGTH_FOR_ANALYSIS} chars). Defaulting to neutral (0.0, 0.0).")
        return 0.0, 0.0 # Default to neutral sentiment

    client = language_v1.LanguageServiceClient()
    document = language_v1.Document(
        content=text_content, type_=language_v1.Document.Type.PLAIN_TEXT
    )
    try:
        time.sleep(PROACTIVE_DELAY_SECONDS)
        sentiment = client.analyze_sentiment(request={'document': document}).document_sentiment
        return sentiment.score, sentiment.magnitude
    except Exception as e:
        print(f"Warning: Could not analyze sentiment. Error: {e}. Defaulting to neutral (0.0, 0.0).")
        return 0.0, 0.0


def analyze_category(text_content):
    """Classifies the content into categories using Natural Language API."""
    if not text_content or len(text_content) < MIN_TEXT_LENGTH_FOR_ANALYSIS:
        print(f"  Skipping category analysis due to short text length (< {MIN_TEXT_LENGTH_FOR_ANALYSIS} chars). Returning empty list.")
        return []

    client = language_v1.LanguageServiceClient()
    document = language_v1.Document(
        content=text_content, type_=language_v1.Document.Type.PLAIN_TEXT
    )
    try:
        time.sleep(PROACTIVE_DELAY_SECONDS)
        response = client.classify_text(request={'document': document})
        return [category.name for category in response.categories]
    except Exception as e:
        print(f"Warning: Could not classify text content. Error: {e}. Returning empty list.")
        return []

def analyze_syntax_complexity(text_content):
    """
    Analyzes sentence structure complexity using Natural Language API's syntax analysis.
    Returns basic metrics that can hint at complexity.
    """
    if not text_content or len(text_content) < MIN_TEXT_LENGTH_FOR_ANALYSIS:
        print(f"  Skipping syntax analysis due to short text length (< {MIN_TEXT_LENGTH_FOR_ANALYSIS} chars). Returning default metrics.")
        return {
            "num_sentences": 0,
            "num_tokens": 0,
            "avg_tokens_per_sentence": 0,
            "num_complex_clauses": 0
        }

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

        # Define labels typically associated with subordinate or complex clauses
        clause_labels = ['acl', 'advcl', 'ccomp', 'csubj', 'xcomp', 'csubjpass', 'auxpass']

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
                print(f"  Max retries reached for rate limit on chunk. Failed to synthesize: {output_filename}. Error: {e}")
                return False
        except (InternalServerError, ServiceUnavailable) as e:
            if attempt < max_retries:
                delay = initial_delay * (2 ** attempt) + random.uniform(0, 1)
                print(f"  Server error for chunk. Retrying in {delay:.2f}s (Attempt {attempt + 1}/{max_retries})... Error: {e}")
                time.sleep(delay)
            else:
                print(f"  Max retries reached for server error on chunk. Failed to synthesize: {output_filename}. Error: {e}")
                return False
        except Exception as e:
            print(f"  An unexpected error occurred during TTS synthesis for chunk '{output_filename}': {e}")
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
    if not text_content or detected_language_code != "en" or len(text_content) < MIN_TEXT_LENGTH_FOR_ANALYSIS:
        if detected_language_code != "en":
            print(f"  Skipping regional analysis: Not English (detected: {detected_language_code}).")
        elif len(text_content) < MIN_TEXT_LENGTH_FOR_ANALYSIS:
            print(f"  Skipping regional analysis due to short text length (< {MIN_TEXT_LENGTH_FOR_ANALYSIS} chars).")
        return None

    text_lower = text_content.lower()
    
    us_score = 0
    gb_score = 0

    # Tokenize the text to count words effectively
    words = nltk.word_tokenize(text_lower)
    word_set = set(words) # Use a set for faster lookup

    # Count occurrences of US-specific words
    for us_word in US_ENGLISH_WORDS:
        us_score += text_lower.count(us_word) # Count occurrences, not just presence

    # Count occurrences of GB-specific words
    for gb_word in GB_ENGLISH_WORDS:
        gb_score += text_lower.count(gb_word) # Count occurrences

    print(f"  Regional Analysis (English): US score = {us_score}, GB score = {gb_score}")

    # Determine regional bias based on scores
    # Adjusted thresholds for more robustness
    if us_score > 0 and us_score >= gb_score * 1.5: # US words significantly more common
        return "en-US"
    elif gb_score > 0 and gb_score >= us_score * 1.5: # GB words significantly more common
        return "en-GB"
    else:
        # If scores are close or low, no strong regional bias detected
        print("  No strong regional bias detected, or scores are too close.")
        return None


def get_contextual_voice_parameters(detected_language_code, sentiment_score, categories=None, syntax_info=None, user_gender_preference=None, regional_code_from_text=None):
    """
    Selects voice parameters based on detected language, regional context, sentiment score,
    text categories, syntax complexity, and optional user gender preference.
    Prioritizes Chirp voices first.
    Handles voice-specific parameter limitations (e.g., pitch not supported for Chirp voices).
    """
    categories = categories or [] # Ensure categories is a list

    # Determine the *effective* language code to search for voices
    # User's preferred regional code from text analysis takes precedence, then generic detection
    effective_language_search_code = regional_code_from_text if regional_code_from_text else detected_language_code

    voices_for_lang = get_available_tts_voices(effective_language_search_code)
    
    if not voices_for_lang:
        # Fallback to generic if regional code failed, or if initial generic failed
        if regional_code_from_text and regional_code_from_text != detected_language_code:
            print(f"  No voices found for specific regional code '{regional_code_from_text}'. Trying generic code '{detected_language_code}'.")
            voices_for_lang = get_available_tts_voices(detected_language_code)
        
        if not voices_for_lang:
            print(f"Warning: Still no suitable voices found for '{detected_language_code}' after all attempts. Falling back to hardcoded 'en-US-Wavenet-B'.")
            return {
                "name": "en-US-Wavenet-B",
                "pitch": 0.0,
                "speaking_rate": 1.0,
                "language_code": "en-US", # Use a common regional code for fallback
                "voice_gender": texttospeech.SsmlVoiceGender.NEUTRAL
            }

    # Prioritize voices: Chirp > Neural2/Studio > Wavenet > Standard
    chirp_voices = [v for v in voices_for_lang if "Chirp" in v.name]
    neural2_studio_voices = [v for v in voices_for_lang if "Neural2" in v.name or ("Studio" in v.name and "Chirp" not in v.name)]
    wavenet_voices = [v for v in voices_for_lang if "Wavenet" in v.name and "Neural2" not in v.name and "Studio" not in v.name and "Chirp" not in v.name]
    standard_voices = [v for v in voices_for_lang if "Wavenet" not in v.name and "Neural2" not in v.name and "Studio" not in v.name and "Chirp" not in v.name]
    
    preferred_voices_list_order = []
    if chirp_voices:
        preferred_voices_list_order.append(chirp_voices)
    if neural2_studio_voices:
        preferred_voices_list_order.append(neural2_studio_voices)
    if wavenet_voices: # Wavenet is generally higher quality than standard
        preferred_voices_list_order.append(wavenet_voices)
    if standard_voices:
        preferred_voices_list_order.append(standard_voices)
    
    # If no preferred types, just use all available
    if not preferred_voices_list_order:
        preferred_voices_list_order.append(voices_for_lang)

    selected_voice = None
    pitch = 0.0
    speaking_rate = 1.0
    
    target_gender = user_gender_preference
    if target_gender is None:
        target_gender = texttospeech.SsmlVoiceGender.NEUTRAL
        # Infer gender based on sentiment and categories
        if sentiment_score > 0.5: # More strongly positive
            target_gender = texttospeech.SsmlVoiceGender.FEMALE
        elif sentiment_score < -0.5: # More strongly negative
            target_gender = texttospeech.SsmlVoiceGender.MALE
        
        # Category overrides sentiment for gender
        if any("Romance" in c for c in categories):
            target_gender = texttospeech.SsmlVoiceGender.FEMALE
        elif any("News" in c for c in categories) or any("Business & Industrial" in c for c in categories) or any("Science" in c for c in categories):
            target_gender = texttospeech.SsmlVoiceGender.NEUTRAL # Often professional for news/business/science

    # Try to find a voice matching the target gender from the most preferred type down
    for voice_type_list in preferred_voices_list_order:
        candidates_by_gender = [v for v in voice_type_list if v.ssml_gender == target_gender]
        if candidates_by_gender:
            selected_voice = random.choice(candidates_by_gender)
            break
    
    # Fallback if specific gender not found in preferred types
    if selected_voice is None:
        for voice_type_list in preferred_voices_list_order:
            neutral_candidates = [v for v in voice_type_list if v.ssml_gender == texttospeech.SsmlVoiceGender.NEUTRAL]
            if neutral_candidates:
                selected_voice = random.choice(neutral_candidates)
                print(f"  Note: Could not find a voice for preferred gender {target_gender.name}. Falling back to a Neutral voice.")
                break
    
    # Final fallback to any voice if no neutral found either
    if selected_voice is None:
        # Take from the first preferred list (highest quality)
        selected_voice = random.choice(preferred_voices_list_order[0])
        print(f"  Note: Could not find a voice for preferred gender {target_gender.name} or Neutral. Falling back to any available voice ({selected_voice.name}).")


    # Adjust pitch and speaking rate based on sentiment, categories, and syntax
    # Use a sensitivity factor for more dynamic adjustments
    PITCH_SENSITIVITY = 4.0 # Max +/- 4 semitones for sentiment
    RATE_SENSITIVITY = 0.1 # Max +/- 10% speaking rate for sentiment

    if sentiment_score > 0:
        pitch += sentiment_score * PITCH_SENSITIVITY
        speaking_rate += sentiment_score * (RATE_SENSITIVITY / 2) # Less impact on rate
    elif sentiment_score < 0:
        pitch += sentiment_score * PITCH_SENSITIVITY # sentiment_score is negative, so this subtracts
        speaking_rate += sentiment_score * (RATE_SENSITIVITY / 2) # This would slow it down for negative

    for cat in categories:
        if "Science Fiction" in cat or "Fantasy" in cat:
            pitch -= 1.0 # Slightly deeper
            speaking_rate *= 0.95 # Slightly slower
        elif "Romance" in cat:
            pitch += 1.5 # Slightly higher, softer
            speaking_rate *= 1.03 # Slightly faster, more engaging
        elif "News" in cat or "Business & Industrial" in cat or "Education" in cat:
            pitch = 0.0 # Neutral pitch
            speaking_rate = 1.0 # Standard rate
        elif "Poetry" in cat or "Literature" in cat:
            pitch -= 0.5 # A bit more resonant
            speaking_rate *= 0.90 # Slower, more contemplative
        elif "Mystery" in cat or "Thriller" in cat:
            pitch -= 0.8 # Slightly lower
            speaking_rate *= 0.97 # A bit slower

    if syntax_info and syntax_info["num_sentences"] > 0:
        avg_tokens = syntax_info["avg_tokens_per_sentence"]
        num_complex_clauses = syntax_info["num_complex_clauses"]

        # Adjust based on complexity: longer sentences, more complex clauses -> slower rate, slightly lower pitch
        # Heuristic: if average sentence length is high OR a significant portion of clauses are complex
        if avg_tokens > 20 or (syntax_info["num_sentences"] > 0 and num_complex_clauses / syntax_info["num_sentences"] > 0.3):
            speaking_rate *= 0.90
            pitch -= 0.5
        elif avg_tokens < 10: # Shorter, simpler sentences -> slightly faster
            speaking_rate *= 1.05

    # Clamp pitch and speaking_rate to valid ranges (Google Cloud TTS limits)
    pitch = max(-20.0, min(20.0, pitch))
    speaking_rate = max(0.25, min(4.0, speaking_rate))

    # Improvement: Voice-specific parameter limitations
    # Chirp and Studio voices typically don't support pitch/speaking_rate adjustments.
    if "Chirp" in selected_voice.name or "Studio" in selected_voice.name:
        if pitch != 0.0 or speaking_rate != 1.0:
            print(f"  Note: Selected voice '{selected_voice.name}' (Chirp/Studio) does not fully support pitch/speaking_rate adjustments. Setting to defaults (pitch=0, rate=1).")
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