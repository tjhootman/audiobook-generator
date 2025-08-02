"""
This module provides functions for analyzing text content to inform Text-to-Speech (TTS)
voice selection and speech parameters. It leverages Google Cloud Natural Language API
for language detection, sentiment analysis, content categorization, and syntax complexity,
as well as Google Cloud Text-to-Speech API for voice management and synthesis.
Additionally, it includes functionality for detecting regional English variations
and dynamic voice parameter adjustment based on text characteristics.
"""
import random
import time
import os
from typing import List, Optional, Dict, Any, Tuple
from abc import ABC, abstractmethod
import nltk
from pydub import AudioSegment
from google.cloud import language_v1
from google.cloud import texttospeech
from google.api_core.exceptions import ResourceExhausted, InternalServerError, ServiceUnavailable


# --- Interface Definitions ---

class LanguageAnalyzer:
    def analyze_language(self, text: str) -> str: ...
    def analyze_sentiment(self, text: str) -> Tuple[float, float]: ...
    def analyze_category(self, text: str) -> List[str]: ...
    def analyze_syntax_complexity(self, text: str) -> Dict[str, Any]: ...
    def analyze_regional_context(self, text: str, detected_code: str) -> Optional[str]: ...

class TTSVoiceSelector:
    def get_available_voices(self, code: Optional[str] = None) -> List[Any]: ...
    def get_contextual_voice_parameters(self, detected_language_code: str, sentiment_score: float, categories: Optional[List[str]] = None,
                                        syntax_info: Optional[Dict[str, Any]] = None, user_gender_preference: Optional[int] = None,
                                        regional_code_from_text: Optional[str] = None) -> Dict[str, Any]: ...

class TTSSynthesizer:
    def synthesize(self, text: str, voice_params: Dict[str, Any], output_filename: str, pitch: float = 0.0, speaking_rate: float = 1.0) -> bool: ...

class UserPreferenceProvider:
    def get_gender_preference(self) -> Optional[int]: ...


# --- Abstractions ---

class TextChunker(ABC):
    @abstractmethod
    def chunk(self, text: str, max_chars_per_chunk: int = 4800) -> List[str]:
        pass


# --- Implementation Classes ---

class NLTKRegionalWordLists:
    # --- Regional Word Lists for English ---
    # These sets contain words typically associated with US English.
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
    # These sets contain words typically associated with British English.
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

class GoogleLanguageAnalyzer(LanguageAnalyzer):
    # Minimum text length required for performing sentiment, category, and syntax analysis.
    # Very short texts often don't provide meaningful results for these analyses.
    MIN_LENGTH = 50
    # Proactive delay added before each API call to help prevent hitting rate limits.
    PROACTIVE_DELAY = 0.1

    def __init__(self):
        # Ensure 'punkt' and 'punkt_tab' tokenizers are downloaded for NLTK.
        # These tokenizers are used for sentence and word segmentation.
        # A LookupError is caught if the resource is not found, triggering a download.
        ensure_nltk_resource('tokenizers/punkt')
        ensure_nltk_resource('tokenizers/punkt_tab')

    def analyze_language(self, text: str) -> str:
        """ 
        Detects the dominant language of the input text using Google Natural Language API.

        Args:
            text_content (str): The text content to analyze.

        Returns:
            str: The detected language code (e.g., "en", "fr"). Defaults to "en"
                if detection fails or text is too short.
        """
        if not text or len(text) < self.MIN_LENGTH:
            print(f"  Skipping language analysis due to short text length (< {self.MIN_LENGTH} chars). Defaulting to 'en'.")
            return "en" # Default to English for very short texts

        client = language_v1.LanguageServiceClient()
        document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)
        try:
            time.sleep(self.PROACTIVE_DELAY) # Proactive delay to mitigate API rate limits
            # analyze_sentiment also returns language information
            response = client.analyze_sentiment(request={'document': document})
            # Return the detected language, or "en" if it's undefined ('und') or empty.
            return response.language if response.language and response.language != 'und' else "en"
        except Exception as e:
            print(f"Warning: Could not detect language. Error: {e}. Defaulting to 'en'.")
            return "en"
        
    def analyze_sentiment(self, text: str) -> Tuple[float, float]:
        """
        Analyzes the sentiment (emotional tone) of the input text using Google Natural Language API.

        Args:
            text_content (str): The text content to analyze.

        Returns:
            tuple: A tuple containing (score, magnitude).
                Score ranges from -1.0 (negative) to 1.0 (positive).
                Magnitude indicates the overall emotional force (0.0 to +infinity).
                Defaults to (0.0, 0.0) if analysis is skipped or fails.
        """
        if not text or len(text) < self.MIN_LENGTH:
            print(f"  Skipping sentiment analysis due to short text length (< {self.MIN_LENGTH} chars). Defaulting to neutral (0.0, 0.0).")
            return 0.0, 0.0 # Default to neutral sentiment
        client = language_v1.LanguageServiceClient()
        document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)
        try:
            time.sleep(self.PROACTIVE_DELAY) # Proactive delay
            sentiment = client.analyze_sentiment(request={'document': document}).document_sentiment
            return sentiment.score, sentiment.magnitude
        except Exception as e:
            print(f"Warning: Could not analyze sentiment. Error: {e}. Defaulting to neutral (0.0, 0.0).")
            return 0.0, 0.0
        
    def analyze_category(self, text: str) -> List[str]:
        """
        Classifies the content into predefined categories using Google Natural Language API.

        Args:
            text_content (str): The text content to classify.

        Returns:
            list: A list of strings, where each string is a category name (e.g., "/Arts & Entertainment/Books & Literature").
                Returns an empty list if analysis is skipped or fails.
        """
        if not text or len(text) < self.MIN_LENGTH:
            print(f"  Skipping category analysis due to short text length (< {self.MIN_LENGTH} chars). Returning empty list.")
            return []
        client = language_v1.LanguageServiceClient()
        document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)
        try:
            time.sleep(self.PROACTIVE_DELAY) # Proactive delay
            response = client.classify_text(request={'document': document})
            return [category.name for category in response.categories]
        except Exception as e:
            print(f"Warning: Could not classify text content. Error: {e}. Returning empty list.")
            return []
    
    def analyze_syntax_complexity(self, text: str) -> Dict[str, Any]:
        """
        Analyzes sentence structure complexity using Google Natural Language API's syntax analysis.
        This function provides basic metrics that can hint at text complexity, such as:
        - Number of sentences
        - Total number of tokens (words, punctuation)
        - Average tokens per sentence
        - Number of complex clauses (e.g., adverbial clauses, complement clauses).

        Args:
            text_content (str): The text content to analyze.

        Returns:
            dict: A dictionary containing syntax complexity metrics.
                Returns default zero values if analysis is skipped or fails.
        """
        if not text or len(text) < self.MIN_LENGTH:
            print(f"  Skipping syntax analysis due to short text length (< {self.MIN_LENGTH} chars). Returning default metrics.")
            return {
                "num_sentences": 0,
                "num_tokens": 0,
                "avg_tokens_per_sentence": 0,
                "num_complex_clauses": 0
            }
        client = language_v1.LanguageServiceClient()
        document = language_v1.Document(
            content=text, type_=language_v1.Document.Type.PLAIN_TEXT
        )
        try:
            time.sleep(self.PROACTIVE_DELAY) # Proactive delay
            response = client.analyze_syntax(request={'document': document})
            num_sentences = len(response.sentences)
            num_tokens = len(response.tokens)
            avg_tokens_per_sentence = num_tokens / num_sentences if num_sentences > 0 else 0

            # Define dependency labels typically associated with subordinate or complex clauses.
            # These labels indicate a grammatical relationship where one clause depends on another.
            clause_labels = ['acl', 'advcl', 'ccomp', 'csubj', 'xcomp', 'csubjpass', 'auxpass']

            # Count tokens that are roots of such clauses.
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

    def analyze_regional_context(self, text: str, detected_code: str) -> Optional[str]:
        # Only perform regional analysis for English texts of sufficient length.
        if not text or detected_code != "en" or len(text) < self.MIN_LENGTH:
            if detected_code != "en":
                print(f"  Skipping regional analysis: Not English (detected: {detected_code}).")
            elif len(text) < self.MIN_LENGTH:
                print(f"  Skipping regional analysis due to short text length (< {self.MIN_LENGTH} chars).")
            return None
        text_lower = text.lower()
        # Count occurrences of US-specific words.
        us_score = sum(text_lower.count(us_word) for us_word in NLTKRegionalWordLists.US_ENGLISH_WORDS)
        # Count occurrences of GB-specific words.
        gb_score = sum(text_lower.count(gb_word) for gb_word in NLTKRegionalWordLists.GB_ENGLISH_WORDS)
        
        print(f"  Regional Analysis (English): US score = {us_score}, GB score = {gb_score}")

        # Determine regional bias based on the scores.
        # A threshold of 1.5 times more common is used to indicate a "strong" bias.
        if us_score > 0 and us_score >= gb_score * 1.5: # US words significantly more common
            return "en-US"
        elif gb_score > 0 and gb_score >= us_score * 1.5: # GB words significantly more common
            return "en-GB"
        else:
            # If scores are close or both are low, no strong regional bias is detected.
            print("  No strong regional bias detected, or scores are too close.")
            return None

    
class GoogleTTSVoiceSelector(TTSVoiceSelector):
    # Map generic language codes to common regional variants for broader voice search.
    # This helps in finding suitable voices when only a generic language code (e.g., 'en') is detected.
    GENERIC_TO_REGIONAL_MAP = {
        "en": ["en-US", "en-GB", "en-AU", "en-IN"],
        "fr": ["fr-FR", "fr-CA"],
        "de": ["de-DE"],
        "es": ["es-ES", "es-US", "es-MX"],
        "zh": ["zh-CN", "zh-TW", "zh-HK"],
    }
    # --- Global Cache for available voices ---
    # Stores the list of available Text-to-Speech voices to avoid repeated API calls.
    available_voices: List[Any] = []

    def get_available_voices(self, language_code: Optional[str] = None) -> List[Any]:
        """
        Fetches and caches the list of available Text-to-Speech voices from Google Cloud.

        Args:
            language_code (str, optional): A specific language code (e.g., "en-US", "fr")
                                        to filter the voices. If None, all available voices
                                        are returned. Generic language codes (e.g., "en")
                                        are expanded to common regional variants.

        Returns:
            list: A list of `texttospeech.Voice` objects matching the criteria.
        """
        # Fetch voices only if the cache is empty
        if not self.available_voices:
            client = texttospeech.TextToSpeechClient()
            response = client.list_voices()
            self.available_voices = response.voices
        if not language_code:
            return self.available_voices
        # Create a list of language codes to check, prioritizing exact match,
        # then regional variants for generic codes, and generic for regional codes.
        codes_to_check = [language_code]
        if len(language_code) == 2 and language_code in self.GENERIC_TO_REGIONAL_MAP:
            codes_to_check.extend(self.GENERIC_TO_REGIONAL_MAP[language_code])
        elif len(language_code) == 5 and language_code[:2] in self.GENERIC_TO_REGIONAL_MAP:
            # If a regional code is given, also try its generic form if not already included
            if language_code[:2] not in codes_to_check:
                codes_to_check.append(language_code[:2])
        # Use a set to avoid duplicate language codes in the search list.
        codes_to_check = list(set(codes_to_check))
        return [
            v for v in self.available_voices
            for voice_lang_code in v.language_codes
            if voice_lang_code in codes_to_check
        ]

    def get_contextual_voice_parameters(self, detected_language_code, sentiment_score, 
                                        categories = None, syntax_info = None,
                                        user_gender_preference = None, regional_code_from_text = None):
        """
        Selects suitable Google Cloud Text-to-Speech voice parameters (name, pitch, speaking rate, gender)
        based on various contextual factors:
        - Detected language and regional variations.
        - Sentiment score of the text.
        - Categories identified in the text.
        - Syntax complexity analysis.
        - Optional user-specified gender preference.

        Voice selection prioritizes higher-quality voice types (Chirp > Neural2/Studio > Wavenet > Standard).
        It also attempts to match gender preferences and adjusts pitch/speaking rate dynamically
        based on the text's characteristics.

        Args:
            detected_language_code (str): The primary language code detected by Natural Language API.
            sentiment_score (float): The sentiment score of the text (from -1.0 to 1.0).
            categories (list, optional): A list of category names for the text. Defaults to an empty list.
            syntax_info (dict, optional): A dictionary containing syntax complexity metrics. Defaults to None.
            user_gender_preference (texttospeech.SsmlVoiceGender | None, optional): User's preferred
                                                                                    gender for the narrator.
                                                                                    None for automatic selection.
            regional_code_from_text (str | None, optional): A more specific regional language code
                                                        derived from text analysis (e.g., 'en-US').

        Returns:
            dict: A dictionary containing the selected voice parameters:
                "name" (str): The name of the chosen TTS voice.
                "pitch" (float): The adjusted speaking pitch.
                "speaking_rate" (float): The adjusted speaking rate.
                "language_code" (str): The language code of the chosen voice.
                "voice_gender" (texttospeech.SsmlVoiceGender): The gender of the chosen voice.
        """
        categories = categories or [] # Ensure categories is a list, default to empty if None

        # Determine the effective language code to search for voices.
        # User's preferred regional code from text analysis takes precedence over generic detection.
        effective_language_search_code = regional_code_from_text if regional_code_from_text else detected_language_code

        voices_for_lang = self.get_available_voices(effective_language_search_code)
        
        # Fallback mechanism if no voices are found for the specific or generic language code.
        if not voices_for_lang:
            # If a regional code was tried and failed, try the generic form.
            if regional_code_from_text and regional_code_from_text != detected_language_code:
                print(f"  No voices found for specific regional code '{regional_code_from_text}'. Trying generic code '{detected_language_code}'.")
                voices_for_lang = self.get_available_voices(detected_language_code)
            
            # If still no voices, provide a hardcoded default fallback.
            if not voices_for_lang:
                print(f"Warning: Still no suitable voices found for '{detected_language_code}' after all attempts. Falling back to hardcoded 'en-US-Wavenet-B'.")
                return {
                    "name": "en-US-Wavenet-B",
                    "pitch": 0.0,
                    "speaking_rate": 1.0,
                    "language_code": "en-US", # Use a common regional code for fallback
                    "voice_gender": texttospeech.SsmlVoiceGender.NEUTRAL
                }

        # Prioritize voices by quality and capabilities: Chirp > Neural2/Studio > Wavenet > Standard.
        chirp_voices = [v for v in voices_for_lang if "Chirp" in v.name]
        neural2_studio_voices = [v for v in voices_for_lang if "Neural2" in v.name or ("Studio" in v.name and "Chirp" not in v.name)]
        wavenet_voices = [v for v in voices_for_lang if "Wavenet" in v.name and "Neural2" not in v.name and "Studio" not in v.name and "Chirp" not in v.name]
        standard_voices = [v for v in voices_for_lang if "Wavenet" not in v.name and "Neural2" not in v.name and "Studio" not in v.name and "Chirp" not in v.name]
        
        # Create a list of voice type lists in desired preference order.
        preferred_voices_list_order = []
        if chirp_voices:
            preferred_voices_list_order.append(chirp_voices)
        if neural2_studio_voices:
            preferred_voices_list_order.append(neural2_studio_voices)
        if wavenet_voices:
            preferred_voices_list_order.append(wavenet_voices)
        if standard_voices:
            preferred_voices_list_order.append(standard_voices)
        
        # If no voices fit into the preferred categories (unlikely but for robustness),
        # just use all available voices as the primary list.
        if not preferred_voices_list_order:
            preferred_voices_list_order.append(voices_for_lang)

        selected_voice = None
        pitch = 0.0
        speaking_rate = 1.0
        
        target_gender = user_gender_preference
        # If no explicit user preference, infer gender based on sentiment and categories.
        if target_gender is None:
            target_gender = texttospeech.SsmlVoiceGender.NEUTRAL # Default
            if sentiment_score > 0.5: # More strongly positive sentiment
                target_gender = texttospeech.SsmlVoiceGender.FEMALE
            elif sentiment_score < -0.5: # More strongly negative sentiment
                target_gender = texttospeech.SsmlVoiceGender.MALE
            
            # Category-based gender inference (overrides sentiment if applicable).
            if any("Romance" in c for c in categories):
                target_gender = texttospeech.SsmlVoiceGender.FEMALE
            elif any("News" in c for c in categories) or any("Business & Industrial" in c for c in categories) or any("Science" in c for c in categories):
                target_gender = texttospeech.SsmlVoiceGender.NEUTRAL # Professional/informative tone often neutral

        # Iterate through preferred voice types to find a voice matching the target gender.
        for voice_type_list in preferred_voices_list_order:
            candidates_by_gender = [v for v in voice_type_list if v.ssml_gender == target_gender]
            if candidates_by_gender:
                selected_voice = random.choice(candidates_by_gender)
                break # Found a suitable voice, stop searching
        
        # Fallback: If no voice with the exact target gender is found in preferred types,
        # try to find a Neutral voice.
        if selected_voice is None:
            for voice_type_list in preferred_voices_list_order:
                neutral_candidates = [v for v in voice_type_list if v.ssml_gender == texttospeech.SsmlVoiceGender.NEUTRAL]
                if neutral_candidates:
                    selected_voice = random.choice(neutral_candidates)
                    print(f"  Note: Could not find a voice for preferred gender {target_gender.name}. Falling back to a Neutral voice.")
                    break
        
        # Final fallback: If no specific or neutral gender voice is found, pick any available voice
        # from the highest quality list (the first list in `preferred_voices_list_order`).
        if selected_voice is None:
            selected_voice = random.choice(preferred_voices_list_order[0])
            print(f"  Note: Could not find a voice for preferred gender {target_gender.name} or Neutral. Falling back to any available voice ({selected_voice.name}).")


        # Adjust pitch and speaking rate based on sentiment, categories, and syntax complexity.
        # Sensitivity factors control the maximum adjustment range.
        PITCH_SENSITIVITY = 4.0 # Max +/- 4 semitones for sentiment
        RATE_SENSITIVITY = 0.1 # Max +/- 10% speaking rate for sentiment

        if sentiment_score > 0:
            pitch += sentiment_score * PITCH_SENSITIVITY
            speaking_rate += sentiment_score * (RATE_SENSITIVITY / 2) # Less impact on rate for positive
        elif sentiment_score < 0:
            pitch += sentiment_score * PITCH_SENSITIVITY # sentiment_score is negative, so this subtracts
            speaking_rate += sentiment_score * (RATE_SENSITIVITY / 2) # This would slow it down for negative

        # Category-specific adjustments for pitch and speaking rate.
        for cat in categories:
            if "Science Fiction" in cat or "Fantasy" in cat:
                pitch -= 1.0 # Slightly deeper tone for genre
                speaking_rate *= 0.95 # Slightly slower, more deliberate
            elif "Romance" in cat:
                pitch += 1.5 # Slightly higher, softer, more engaging
                speaking_rate *= 1.03 # Slightly faster
            elif "News" in cat or "Business & Industrial" in cat or "Education" in cat:
                pitch = 0.0 # Neutral, clear pitch for factual content
                speaking_rate = 1.0 # Standard rate
            elif "Poetry" in cat or "Literature" in cat:
                pitch -= 0.5 # A bit more resonant/contemplative
                speaking_rate *= 0.90 # Slower, more contemplative
            elif "Mystery" in cat or "Thriller" in cat:
                pitch -= 0.8 # Slightly lower, more serious/suspenseful
                speaking_rate *= 0.97 # A bit slower

        # Syntax complexity adjustments.
        if syntax_info and syntax_info["num_sentences"] > 0:
            avg_tokens = syntax_info["avg_tokens_per_sentence"]
            num_complex_clauses = syntax_info["num_complex_clauses"]

            # If average sentence length is high or a significant portion of clauses are complex,
            # slow down the speaking rate and slightly lower the pitch for better comprehension.
            if avg_tokens > 20 or (syntax_info["num_sentences"] > 0 and num_complex_clauses / syntax_info["num_sentences"] > 0.3):
                speaking_rate *= 0.90
                pitch -= 0.5
            elif avg_tokens < 10: # Shorter, simpler sentences can be read slightly faster.
                speaking_rate *= 1.05

        # Clamp pitch and speaking_rate to valid ranges supported by Google Cloud TTS API.
        pitch = max(-20.0, min(20.0, pitch))
        speaking_rate = max(0.25, min(4.0, speaking_rate))

        # Voice-specific parameter limitations: Chirp and Studio voices often don't support
        # custom pitch/speaking rate adjustments. Reset to defaults if such a voice is selected.
        if "Chirp" in selected_voice.name or "Studio" in selected_voice.name:
            if pitch != 0.0 or speaking_rate != 1.0:
                print(f"  Note: Selected voice '{selected_voice.name}' (Chirp/Studio) does not fully support pitch/speaking_rate adjustments. Setting to defaults (pitch=0, rate=1).")
                pitch = 0.0
                speaking_rate = 1.0

        # Extract the final language code and gender from the selected voice object.
        final_voice_language_code = selected_voice.language_codes[0]
        final_voice_gender = selected_voice.ssml_gender

        return {
            "name": selected_voice.name,
            "pitch": pitch,
            "speaking_rate": speaking_rate,
            "language_code": final_voice_language_code,
            "voice_gender": final_voice_gender
        }

class GoogleTTSSynthesizer(TTSSynthesizer):
    # Initial delay for retry attempts in case of API errors.
    INITIAL_RETRY_DELAY = 1
    # Maximum number of retries for API calls.
    MAX_API_RETRIES = 5
    # Proactive delay added before each API call to help prevent hitting rate limits.
    PROACTIVE_DELAY = 0.1

    def synthesize(self, text, voice_params, output_filename, pitch = 0.0, speaking_rate = 1.0):
        """
        Synthesizes speech from the input text using a specified Google Cloud Text-to-Speech voice,
        including its explicit gender. Implements retry logic for transient API errors
        (ResourceExhausted, InternalServerError, ServiceUnavailable).

        Args:
            text_content (str): The text content to convert to speech.
            voice_name (str): The name of the TTS voice to use (e.g., "en-US-Wavenet-A").
            language_code (str): The BCP-47 language code for the voice (e.g., "en-US").
            voice_gender (texttospeech.SsmlVoiceGender): The SSML gender of the voice.
            output_filename (str): The path to save the generated audio file (MP3).
            pitch (float, optional): The speaking pitch of the voice, in semitones
                                    (from -20.0 to 20.0). Defaults to 0.0.
            speaking_rate (float, optional): The speaking rate relative to the normal
                                            speed (0.25 to 4.0). Defaults to 1.0.
            max_retries (int, optional): Maximum number of times to retry the API call. Defaults to MAX_API_RETRIES.
            initial_delay (int, optional): Initial delay in seconds before the first retry. Defaults to INITIAL_RETRY_DELAY.

        Returns:
            bool: True if speech synthesis was successful and the file was saved, False otherwise.
        """
        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice_params = texttospeech.VoiceSelectionParams(
            language_code=voice_params["language_code"],
            name=voice_params["name"],
            ssml_gender=voice_params["voice_gender"]
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            pitch=pitch,
            speaking_rate=speaking_rate
        )

        for attempt in range(self.MAX_API_RETRIES + 1):
            try:
                time.sleep(self.PROACTIVE_DELAY) # Proactive delay before each attempt
                response = client.synthesize_speech(
                    input=synthesis_input, voice=voice_params, audio_config=audio_config
                )

                # Write the audio content to a file
                with open(output_filename, "wb") as out:
                    out.write(response.audio_content)
                return True # Synthesis successful

            except ResourceExhausted as e:
                # Handle rate limit errors with exponential backoff and jitter
                if attempt < self.MAX_API_RETRIES:
                    delay = self.INITIAL_RETRY_DELAY * (2 ** attempt) + random.uniform(0, 1)
                    print(f"  Rate limit hit for chunk. Retrying in {delay:.2f}s (Attempt {attempt + 1}/{self.MAX_API_RETRIES})... Error: {e}")
                    time.sleep(delay)
                else:
                    print(f"  Max retries reached for rate limit on chunk. Failed to synthesize: {output_filename}. Error: {e}")
                    return False
            except (InternalServerError, ServiceUnavailable) as e:
                # Handle server-side errors with exponential backoff and jitter
                if attempt < self.MAX_API_RETRIES:
                    delay = self.INITIAL_RETRY_DELAY * (2 ** attempt) + random.uniform(0, 1)
                    print(f"  Server error for chunk. Retrying in {delay:.2f}s (Attempt {attempt + 1}/{self.MAX_API_RETRIES})... Error: {e}")
                    time.sleep(delay)
                else:
                    print(f"  Max retries reached for server error on chunk. Failed to synthesize: {output_filename}. Error: {e}")
                    return False
            except Exception as e:
                # Catch any other unexpected errors
                print(f"  An unexpected error occurred during TTS synthesis for chunk '{output_filename}': {e}")
                return False
        return False # Should not be reached if max_retries is handled correctly

class UserPreference(UserPreferenceProvider):
    def get_gender_preference(self) -> Optional[int]:
        """
        Prompts the user to select a preferred narrator gender for the synthesized speech.

        Returns:
            texttospeech.SsmlVoiceGender | None: The selected SSML voice gender enum
                                                (MALE, FEMALE, NEUTRAL) or None if the
                                                user chooses automatic selection (presses Enter).
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
                return None # User chose automatic
            else:
                print("Invalid input. Please type 'Male', 'Female', 'Neutral', or press Enter.")

class DefaultTextChunker(TextChunker):
    def chunk(self, text: str, max_chars_per_chunk: int = 4800) -> List[str]:
        # Ensure NLTK punkt is available before tokenizing
        ensure_nltk_resource('tokenizers/punkt')
        chunks = []
        paragraphs = text.split('\n\n')
        current_chunk = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(current_chunk) + len(para) + 2 > max_chars_per_chunk and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            if len(para) > max_chars_per_chunk:
                sentences = nltk.sent_tokenize(para)
                sentence_chunk = ""
                for sentence in sentences:
                    if len(sentence_chunk) + len(sentence) + 1 > max_chars_per_chunk and sentence_chunk:
                        chunks.append(sentence_chunk.strip())
                        sentence_chunk = ""
                    sentence_chunk += sentence + " "
                if sentence_chunk:
                    chunks.append(sentence_chunk.strip())
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
        if current_chunk:
            chunks.append(current_chunk.strip())
        return chunks


# --- NLTK resource helper ---

def ensure_nltk_resource(resource: str, download_if_missing: bool = True, quiet: bool = True):
    """
    Checks if the given NLTK resource is available, and downloads it if missing.

    Args:
        resource (str): The resource path, e.g. 'tokenizers/punkt'
        download_if_missing (bool): Whether to download if missing.
        quiet (bool): Whether to suppress download output.
    """
    try:
        nltk.data.find(resource)
    except LookupError:
        if download_if_missing:
            print(f"NLTK resource '{resource}' not found. Downloading...")
            nltk.download(resource.split('/')[-1], quiet=quiet)


# -- High-level Service ---

class AudioSynthesisService:
    """
    High-level service for analyzing text, selecting contextual voice parameters, chunking for TTS API, and synthesizing audio.
    """
    
    MAX_CHARS_PER_TTS_CHUNK = 4800 # Google TTS limit

    def __init__(
        self,
        language_analyzer,
        voice_selector,
        tts_synthesizer,
        user_pref_provider,
        chunker = None
    ):
        self.language_analyzer = language_analyzer
        self.voice_selector = voice_selector
        self.tts_synthesizer = tts_synthesizer
        self.user_pref_provider = user_pref_provider
        self.chunker = chunker if chunker else DefaultTextChunker()

    def synthesize_audio(
        self,
        text: str,
        output_audio_path: str,
        temp_audio_dir: str = None,
        user_gender_preference: Optional[int] = None
    ) -> Optional[str]:
        """
        Chunk text, analyze, select TTS parameters, synthesize, and combine audio.

        Args:
            text (str): Text content to analyze and synthesize.
            output_audio_path (str): Path where the output audio file will be saved.
            temp_audio_dir (str, optional): Directory for intermediate audio chunks. 
            user_gender_preference (int, optional): Gender enum for voice (or None for auto).

        Returns:
            str: Path to final audiobook MP3 if sucessful, else None.
        """

        # Chunking
        chunks = self.chunker.chunk(text, max_chars_per_chunk=self.MAX_CHARS_PER_TTS_CHUNK)
        if not chunks:
            print("No text chunks generated for audiobook.")
            return None
        

        # Analysis (use full text for consistent parameters)
        lang_code = self.language_analyzer.analyze_language(text)
        sentiment_score, sentiment_magnitude = self.language_analyzer.analyze_sentiment(text)
        categories = self.language_analyzer.analyze_category(text)
        syntax_info = self.language_analyzer.analyze_syntax_complexity(text)
        regional_code = self.language_analyzer.analyze_regional_context(text, lang_code)

        if user_gender_preference is None:
            user_gender_preference = self.user_pref_provider.get_gender_preference()

        voice_params = self.voice_selector.get_contextual_voice_parameters(
            detected_language_code=lang_code,
            sentiment_score=sentiment_score,
            categories=categories,
            syntax_info=syntax_info,
            user_gender_preference=user_gender_preference,
            regional_code_from_text=regional_code,
        )

        # Prepare temp dir
        if not temp_audio_dir:
            temp_audio_dir = os.path.join(os.path.dirname(output_audio_path), "temp_audio_chunks")
        os.makedirs(temp_audio_dir, exist_ok=True)

        audio_segments = []
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            temp_audio_file = os.path.join(temp_audio_dir, f"chunk_{i:04d}.mp3")
            success = self.tts_synthesizer.synthesize(
                text=chunk, 
                voice_params=voice_params,
                output_filename=temp_audio_file,
                pitch=voice_params["pitch"],
                speaking_rate=voice_params["speaking rate"]
            )
            if success:
                try:
                    audio_segments.append(AudioSegment.from_mp3(temp_audio_file))
                except Exception as e:
                    print(f"Error loading chunk {i}: {e}")
            else:
                with open(os.path.join(temp_audio_dir, f"failed_chunk_{i:04d}.txt"), "w", encoding="utf-8") as err_f:
                    err_f.write(chunk)

        if not audio_segments:
            print("No audio segments were successfully generated for the audiobook. Exiting.")
            return None

        # Combine audio
        combined_audio = AudioSegment.empty()
        for segment in audio_segments:
            combined_audio += segment
        combined_audio.export(output_audio_path, format="mp3")
        
        # Clean up
        for file_name in os.listdir(temp_audio_dir):
            os.remove(os.path.join(temp_audio_dir, file_name))
        os.rmdir(temp_audio_dir)

        print(f"Audiobook created successfully: '{output_audio_path}'")
        return output_audio_path
